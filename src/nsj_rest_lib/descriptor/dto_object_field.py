import typing

from nsj_rest_lib.descriptor.dto_field import DTOFieldFilter
from nsj_rest_lib.descriptor.dto_left_join_field import EntityRelationOwner
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.util.type_validator_util import TypeValidatorUtil


# TODO Adicionar suporte ao search
# TODO Implementar o filters comentado no construtor
# TODO Pensar em como ordenar os joins (quando tiver um left no meio, pode ser útil)
# TODO Pensar em como passar mais condições dentro do ON
# TODO Pensar em como usar um só entity (e não precisar de um com os campos que vem da outra entidade)
# TODO Verificar se ficou boa a abstração pelo DTO (porque o join ficou bem distante do natural em SQL)


class DTOObjectField:
    _ref_counter = 0

    def __init__(
        self,
        # dto_type: DTOBase,
        entity_type: EntityBase = None,
        relation_field: str = None,
        entity_relation_owner: EntityRelationOwner = EntityRelationOwner.SELF,
        not_null: bool = False,
        resume: bool = False,
        convert_from_entity: typing.Callable = None,
        validator: typing.Callable = None,
    ):
        """
        -----------
        Parameters:
        -----------
        dto_type: Expected type for the related DTO (must be subclasse from DTOBase).
        entity_type: Expected entity type for the related DTO (must be subclasse from EntityBase).
        related_dto_field: Nome do campo, no DTO relacionado, a ser copiado para esse campo.
        relation_field: Nome do campo, usado na query, para correlacionar as entidades (correspondete
            ao campo usado no "on" de um "join").
        entity_relation_owner: Indica qual entidade contém o campo que aponta o relacionamento (
            se for EntityRelationField.OTHER, implica que a entidade apontada pela classe de DTO
            passada no decorator, é que contem o campo; se for o EntityRelationField.SELF, indica
            que o próprio DTO que contém o campo).
        join_type: Indica o tipo de Join a ser realizado na query (LEFT, INNER ou FULL).
        type: Tipo esperado para a propriedade. Se for do tipo enum.Enum, o valor recebido, para atribuição à propriedade, será convertido para o enumerado.
        not_null: O campo não poderá ser None, ou vazio, no caso de strings.
        resume: O campo será usado como resumo, isto é, será sempre rotornado num HTTP GET que liste os dados (mesmo que não seja solicitado por meio da query string "fields").
        # filters: Lista de filtros adicionais suportados para esta propriedade (adicionais, porque todos as propriedades, por padrão, suportam filtros de igualdade, que podem ser passados por meio de uma query string, com mesmo nome da proriedade, e um valor qualquer a ser comparado).
        #   Essa lista de filtros consiste em objetos do DTOFieldFilter (veja a documentação da classe para enteder a estrutura de declaração dos filtros).
        convert_from_entity: Função para converter o valor contido na Entity, para o(s) valor(es) a serem gravados no objeto DTO (durante a conversão). É útil para casos onde não há equivalência um para um entre um campo do DTO e um da entidade
          (por exemplo, uma chave de cnpj que pode ser guardada em mais de um campo do BD). Outro caso de uso, é quando um campo tem formatação diferente entre o DTO e a entidade, carecendo de conversão customizada.
          A função recebida deve suportar os parâmetros (entity_value: Any, entity_fields: Dict[str, Any]), e retornar um Dict[str, Any], como uma coleção de chaves e valores a serem atribuídos no DTO.
        validator: Função que recebe o valor (a ser atribuído), e retorna o mesmo valor após algum
            tipo de tratamento (como adição ou remoção, automática, de formatação).
        # search: Indica que esse campo é passível de busca, por meio do argumento "search" passado num GET List, como query string (por hora, apenas pesquisas simples, por meio de operador like, estão implementadas).
        """
        self.name = None
        # self.dto_type = dto_type
        self.entity_type = entity_type
        self.relation_field = relation_field
        self.entity_relation_owner = entity_relation_owner
        self.expected_type = type
        self.not_null = not_null
        self.resume = resume
        self.convert_from_entity = convert_from_entity
        self.validator = validator

        self.storage_name = f"_{self.__class__.__name__}#{self.__class__._ref_counter}"
        self.__class__._ref_counter += 1

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            return instance.__dict__[self.storage_name]

    def __set__(self, instance, value):
        try:
            # Checking not null constraint
            if self.not_null and value is None:
                raise ValueError(
                    f"{self.storage_name} deve estar preenchido. Valor recebido: {value}."
                )

            if self.validator is None and value is not None:
                if not isinstance(value, self.expected_type):
                    raise ValueError(
                        f"O Objeto não é do tipo informado. Valor recebido: {value}."
                    )
            else:
                value = self.validator(self, value)
        except ValueError as e:
            if not (
                "escape_validator" in instance.__dict__
                and instance.__dict__["escape_validator"] == True
            ):
                raise

        instance.__dict__[self.storage_name] = value
