import enum
import json
import openai
import os

from pydantic import BaseModel

from nsj_rest_lib.controller.route_recorder import RouteRecorder
from nsj_rest_lib.decorator.entity import Entity, EntityField
from nsj_rest_lib.descriptor.dto_list_field import DTOListField

ENTITY_CONTEXT_TEMPLATE = """
{entity_table}:
  table_name: {entity_table}
  pk_field: {entity_pk_field}
  default_order_fields: {entity_default_order_fields}
  fields:
{fields}
"""

ENTITY_FIELD_TEMPLATE = """
    - name: {field_name}
      type: {field_type}
"""

TEMPLATE_PROMPT = """
Você é um assistente de IA especializado em consultas a bancos de dados.
Você tem acesso a um conjunto de entidades e seus campos, conforme descrito abaixo:

{entities_context}

Também tem acesso as seguintes regras de relaciobamentos entre as entidades:

{relationships}

Você deve responder às perguntas do usuário com base nessas entidades.
Se a pergunta não puder ser respondida com as entidades disponíveis, informe que não é possível responder a pergunta.

O formato de resposta deve ser um JSON do tipo:
{{
    "status": "success" | "error",
    "query": "QUERY SQL",
    "message": "mensagem de erro, ou instruções a mais, se houver"
}}

E, no campo "query", deve conter a consulta SQL que pode ser executada no banco de dados.
Se a consulta não puder ser executada, informe o erro no campo "message" (mas, explique bem o erro. não pode dizer apenas "não é possível responder a pergunta").

Você deve retornar apenas o JSON, sem mais informações.

Você deve retornar os registros da entidade principal {entity_table} (ESSA É A ENTIDADE FOCO DA QUERY) que atendam aos critérios especificados na consulta. E deve retornar os seguintes campos:

{fields}

Você também deve considerar os seguintes filtros, se fornecidos:

{filters}

Você também deve considerar os seguintes campos para ordenação, se fornecidos:

{order_fields}

Você deve trazer, no máximo, {limit} registros, se fornecido (usando a cláusula LIMIT na consulta SQL).

Você deve considerar que a coluna de chave primária da entidade principal (foco do retorno) é {pk_field}.

NÃO TRAGA CAMPOS DE OUTRAS ENTIDADES, ALÉM DA PRINCIPAL. O RESTO DA BIBLIOTECA SE RESPONSABILIZA POR TRATAR OS DADOS A RETORNAR DAS ENTIDADES SELECIONADAS.

Instruções adicionais:
- Pode ser interessante, caso o usuário envie um texto para identificar um registro, usar o operador ilike na consulta SQL.
- Se o usuário enviar um texto de busca, você deve usar o operador LIKE na consulta SQL.
- Se o usuário falar de um código, normalmente, o nome do campo correspondente se chama "codigo".
- Se ele falar de um nome, normalmente, o nome do campo correspondente se chama "nome" ou "descricao".
- Para fazer uma consulta, facilmente será necessário fazer subqueries ou joins. Por exemplo, supondo que haja uma entidade chamada "cliente", que se relacione com outra chamada "pedido", onde a coluna "id_cliente" da tabela de "pedido" aponte para a coluna "id" da tabela de clientes; e supondo que o usuário peça todos os clientes cujo pedido tenha "valor" maior do "100", a query final gerada pode ser algo como: "select * from cliente as c where exists (select 1 from pedido as p where p.id_cliente=c.id and p.valor > 100). Isso é só um exemplo, você deve otimizar as queries ao máximo (e usar dos relacionamentos, para filtrar o desejo do usuário).

PERGUNTA REAL DO USUÁRIO:

{user_query}
"""


class AISearchException(Exception):
    pass


class ResponseStatusEnum(enum.Enum):
    SUCESSO = "success"
    ERRO = "error"


class ResponseFormat(BaseModel):
    status: ResponseStatusEnum
    query: str
    message: str


class AISerchService:
    """
    Service class for AI search functionality.
    """

    entities_context = None
    relationship_context = None

    def __init__(self):
        super().__init__()

    def search(
        self,
        entity_class: Entity,
        query: str,
        fields: list[str] = None,
        filters: dict = None,
        limit: int = None,
        order_fields: list[str] = None,
    ) -> ResponseFormat:
        """
        Perform an AI-based search with the given query and filters.
        """

        # Creating a entity instance
        entity = entity_class()

        # Garantindo a criação do contexto de conversa referente às entidades
        self._make_entities_context()

        # Garantindo a criação do contexto de conversa referente às relações entre entidades
        self._make_relationship_context()

        # Tratando dos campos de ordenação
        if order_fields is None:
            order_fields = entity.get_default_order_fields()
        order_fields = ", ".join(order_fields)

        # Formatando o prompt para a IA
        prompt = TEMPLATE_PROMPT.format(
            entities_context=AISerchService.entities_context,
            relationships=AISerchService.relationship_context,
            entity_table=entity_class.table_name,
            fields=", ".join(fields) if fields else "",
            # TODO Arrumar filtros
            # filters=json.dumps(filters, indent=4) if filters else "Nenhum filtro",
            filters="Nenhum filtro",
            order_fields=order_fields,
            limit=limit if limit else "Nenhum",
            pk_field=entity_class.pk_field,
            user_query=query,
        )

        # Chamando a API do modelo LLM para criação da query de consulta
        try:
            OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
            OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "1"))

            client = openai.OpenAI()
            response = client.beta.chat.completions.parse(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=OPENAI_TEMPERATURE,
                response_format=ResponseFormat,
            )

            if not (response and response.choices and len(response.choices) > 0):
                raise RuntimeError("Invalid response format from OpenAI API.")

            return response.choices[0].message.parsed
        except Exception as e:
            raise AISearchException(
                "Erro ao chamar a API do modelo LLM: {}".format(e), e
            )

    def _make_entities_context(self):
        """
        Formatando as entidades carregadas, em formato de string, para serem usadas no contexto da IA.
        """

        if AISerchService.entities_context is not None:
            return AISerchService.entities_context

        entities_context = []
        for list_route in RouteRecorder.list_routes:
            entity_class = list_route.route_obj._entity_class
            entity_table = entity_class.table_name
            entity_pk_field = entity_class.pk_field
            entity_default_order_fields = entity_class.default_order_fields

            fields_context = []
            fields_map: dict[str, EntityField] = getattr(entity_class, "fields_map", {})
            for field_name in fields_map:
                entity_field = fields_map[field_name]
                field_type = entity_field.expected_type

                fields_context.append(
                    {
                        "field_name": field_name,
                        "field_type": (
                            field_type.__name__
                            if hasattr(field_type, "__name__")
                            else str(field_type)
                        ),
                    }
                )

            entities_context.append(
                {
                    "entity_table": entity_table,
                    "entity_pk_field": entity_pk_field,
                    "entity_default_order_fields": entity_default_order_fields,
                    "fields": fields_context,
                }
            )

        AISerchService.entities_context = json.dumps(
            entities_context, ensure_ascii=True, indent=4
        )

    def _make_relationship_context(self):
        """
        Formatando as relações entre entidades, em formato de string, para serem usadas no contexto da IA.
        """

        if AISerchService.relationship_context is not None:
            return AISerchService.relationship_context

        relationships = []
        for list_route in RouteRecorder.list_routes:
            entity_class = list_route.route_obj._entity_class
            dto_class = list_route.route_obj._dto_class

            list_fields_map: dict[str, DTOListField] = getattr(
                dto_class, "list_fields_map", {}
            )
            for list_field_name in list_fields_map:
                list_field = list_fields_map[list_field_name]

                if list_field.relation_key_field is None:
                    field_to = entity_class.pk_field
                else:
                    field_to = list_field.relation_key_field
                    # TODO Refatorar para um local em comum com o service_base
                    field_to = dto_class.fields_map[field_to].entity_field or field_to

                # relationship = {
                #     "entity_from": list_field.entity_type.table_name,
                #     "field_from": list_field.related_entity_field,
                #     "entity_to": entity_class.table_name,
                #     "field_to": field_to,
                # }
                # relationships.append(relationship)
                relationships.append(
                    f"FOREIGN KEY {list_field.entity_type.table_name} COLUMN ({list_field.related_entity_field}) REFERENCES {entity_class.table_name} COLUMN ({field_to})"
                )

        AISerchService.relationship_context = json.dumps(
            relationships, ensure_ascii=True, indent=4
        )
