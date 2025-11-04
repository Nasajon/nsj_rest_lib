import copy
import functools
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set, Type

from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.descriptor import (
    DTOAggregator,
    DTOOneToOneField, OTORelationType
)
from nsj_rest_lib.descriptor.conjunto_type import ConjuntoType
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.descriptor.dto_list_field import DTOListField
from nsj_rest_lib.descriptor.dto_left_join_field import DTOLeftJoinField, LeftJoinQuery
from nsj_rest_lib.descriptor.dto_object_field import DTOObjectField
from nsj_rest_lib.descriptor.dto_sql_join_field import DTOSQLJoinField, SQLJoinQuery
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.settings import ENV_MULTIDB


@dataclass
class PartialDTOConfig:
    parent_dto: Type[DTOBase]
    relation_field: str
    related_entity_field: str
    parent_fields: Set[str]
    extension_fields: Set[str]


class DTO:
    def __init__(
        self,
        fixed_filters: Dict[str, Any] = None,
        conjunto_type: ConjuntoType = None,
        conjunto_field: str = None,
        filter_aliases: Dict[str, Any] = None,
        data_override: dict[str, list[str]] = None,
        partial_of: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        -----------
        Parâmetros:
        -----------

        - fixed_filters: Filtros fixos a serem usados numa rota de GET. A ideia é que, se não for dito em contrário,
            o retorno do GET será filtrado de acordo com o valor aqui passado.
            O formato esperado é de um dict, onde as chaves são os nomes dos fields, e os valores, o valor que seria
            passado na URL, para realizar o mesmo filtro. Exemplo:

            fixed_filters={"cliente": True}

            No exemplo, o GET normal só trará dados onde a propriedade "cliente" seja igual a "true".

        - conjunto_type: Tipo do conjunto, se usado, de acordo com os padrões do BD do ERP (conjunto de produto, unidade,
            rubrica, etc).

        - conjunto_field: Nome do campo onde o grupo_empresarial, referente ao conjunto do registro, será carregado.
            A ideia é que os conjuntos são resolvidos de acordo com a PK da entidade, e retornados como "grupo_empresarial_pk",
            e "grupo_empresarial_codigo" nas queries. Assim, se o nome do campo conscidir com um desses nomes, o grupo_empresarial
            é retornado no objeto. Mas, mesmo que não seja, será possível filtrar a entidade pelo grupo_empresarial, passando um
            query arg com o mesmo nome do campo escolhido como "conjunto_field" (filtrando assim uma entidade pelo grupo_empsarial
            referente ao conjunto da mesma).

        - filter_aliases: Permite especificar nome alternativos para os filtros, suportando, inclusive, que um mesmo nome de filtro
            (query arg) aponte para diversos campos da entidade, de acordo com o tipo do dado recebido no filtro. Exemplo de uso:

            filter_aliases={
                "id": {
                    uuid.UUID: "pk",
                    str: "id"
                }
            }

            No exemplo, o filtro "id" (passado como query_args), será aplicado sobre a propriedade "pk", se o dado recebido for UUID,
            ou sobre a propriedade "id", se o dado recebido for string.

        - data_override: Permite fazer override ao nível dos dados. Normalmente é útil para configurações que tenham um padrão para
            a empresa, mas que possam ser sobrescritas por tenant, grupo empresarial, etc. Forma de uso:

            data_override={
                "group": ["escopo", "codigo"],
                "fields": ["tenant", "grupo_empresarial"],
            }

            Onde "group" se refere aos campos utilizados para agrupar dados (isso é, os campos que indicam quando um dado equivale
            ao outro). E, "fields" se refere aos campos que, na ordem passada, serão considerados para especificação da configuração.

            No exemplo, os dados com mesmo "escopo" e "codigo" são equivalentes, e, podem ser especificados de maneira a ter um padrão
            global, o qual pode ser especializado para um tenant, e, dentro de um tenant, especializado ainda mais para um grupo_empresarial.
        """
        super().__init__()

        self._fixed_filters = fixed_filters
        self._conjunto_type = conjunto_type
        self._conjunto_field = conjunto_field
        self._filter_aliases = filter_aliases
        self._partial_of_config = partial_of

        # Validando os parâmetros de data_override
        self._validate_data_override(data_override)

        self._data_override_group = (
            data_override["group"]
            if data_override is not None and "group" in data_override
            else None
        )
        self._data_override_fields = (
            data_override["fields"]
            if data_override is not None and "fields" in data_override
            else []
        )

        if (self._conjunto_type is None and self._conjunto_field is not None) or (
            self._conjunto_type is not None and self._conjunto_field is None
        ):
            raise Exception(
                "Os parâmetros conjunto_type e conjunto_field devem ser preenchidos juntos (se um for não nulo, ambos devem ser preenchidos)."
            )

    def _validate_data_override(self, data_override):
        """
        Valida os parâmetros de data_override.
        :param data_override: Parâmetro de data_override
        :type data_override: dict
        :raises Exception: Se o parâmetro de data_override não for um dicionário ou não contiver as chaves 'group' e 'fields'.
        """

        if data_override is not None:
            if not isinstance(data_override, dict):
                raise Exception(
                    "O parâmetro data_override deve ser um dicionário com as chaves 'group' e 'fields'."
                )
            if "group" not in data_override or "fields" not in data_override:
                raise Exception(
                    "O parâmetro data_override deve conter as chaves 'group' e 'fields'."
                )
            if not isinstance(data_override["group"], list) or not all(
                isinstance(item, str) for item in data_override["group"]
            ):
                raise Exception(
                    "O parâmetro data_override deve conter a chave 'group' com uma lista de strings."
                )
            if not isinstance(data_override["fields"], list) or not all(
                isinstance(field, str) for field in data_override["fields"]
            ):
                raise Exception(
                    "O parâmetro data_override deve conter a chave 'fields' com uma lista de strings."
                )
            if len(data_override["group"]) <= 0:
                raise Exception(
                    "O parâmetro data_override deve conter a chave 'group' com ao menos uma propriedade para agrupamento."
                )
            if len(data_override["fields"]) <= 0:
                raise Exception(
                    "O parâmetro data_override deve conter a chave 'fields' com ao menos uma propriedade que permita override das configurações."
                )
                
    def ignore_tenant_field_on_desktop(self, cls):
        """
        Remove all tenant-related fields if the ENV_MULTIDB environment variable is true.
        If ENV_MULTIDB is not setted or is "false", do nothing.
        """        
        if ENV_MULTIDB == "true":            
            tenant_columns = ["tenant", "tenant_id", "tenantid", "id_tenant", "idtenant"]            
            for col in tenant_columns:
                if col in cls.__dict__:
                    delattr(cls, col)
                if col in getattr(cls, "__annotations__", {}):
                    del cls.__annotations__[col]


    def __call__(self, cls):
        """
        Iterating DTO class to handle DTOFields descriptors.
        """
        
        #Ignore tenant field on desktop environment (for JobManager)
        self.ignore_tenant_field_on_desktop(cls)

        # Mantém metadados da classe original
        functools.update_wrapper(self, cls)

        # Creating resume_fields in cls, if needed
        self._check_class_attribute(cls, "resume_fields", set())

        # Creating fields_map in cls, if needed
        self._check_class_attribute(cls, "fields_map", {})

        # Creating list_fields_map in cls, if needed
        self._check_class_attribute(cls, "list_fields_map", {})

        # Creating integrity_check_fields_map in cls, if needed
        self._check_class_attribute(cls, "integrity_check_fields_map", {})

        # Creating left_join_fields_map in cls, if needed
        self._check_class_attribute(cls, "left_join_fields_map", {})

        # Creating left_join_fields_map_to_query in cls, if needed
        self._check_class_attribute(cls, "left_join_fields_map_to_query", {})

        # Creating sql_join_fields_map in cls, if needed
        self._check_class_attribute(cls, "sql_join_fields_map", {})

        # Creating sql_join_fields_map_to_query in cls, if needed
        self._check_class_attribute(cls, "sql_join_fields_map_to_query", {})

        # Creating sql_read_only_fields in cls, if needed
        self._check_class_attribute(cls, "sql_read_only_fields", [])

        self._check_class_attribute(cls, "sql_no_update_fields", set())

        # Creating object_fields_map in cls, if needed
        self._check_class_attribute(cls, "object_fields_map", {})

        self._check_class_attribute(cls, 'one_to_one_fields_map', {})

        # Creating field_filters_map in cls, if needed
        self._check_class_attribute(cls, "field_filters_map", {})

        self._check_class_attribute(cls, "aggregator_fields_map", {})

        # Creating pk_field in cls, if needed
        # TODO Refatorar para suportar PKs compostas
        self._check_class_attribute(cls, "pk_field", None)

        # Criando a propriedade "partition_fields" na classe "cls", se necessário
        self._check_class_attribute(cls, "partition_fields", set())

        # Criando a propriedade "uniques" na classe "cls", se necessário
        self._check_class_attribute(cls, "uniques", {})

        # Criando a propriedade "candidate_keys" na classe "cls", se necessário
        self._check_class_attribute(cls, "candidate_keys", [])

        # Criando a propriedade "search_fields" na classe "cls", se necessário
        self._check_class_attribute(cls, "search_fields", set())

        # Criando a propriedade "metric_fields" na classe "cls", se necessário
        self._check_class_attribute(cls, "metric_fields", set())

        # Criando a propriedade "data_override_group"
        self._check_class_attribute(
            cls, "data_override_group", self._data_override_group
        )

        # Criando a propriedade "data_override_fields"
        self._check_class_attribute(
            cls, "data_override_fields", self._data_override_fields
        )

        # Criando a propriedade "auto_increment_fields"
        self._check_class_attribute(cls, "auto_increment_fields", set())

        # Tratando das propriedades das extensões parciais
        partial_parent_fields: Set[str] = set()
        partial_extension_fields: Set[str] = set()
        partial_parent_dto: Optional[Type[DTOBase]] = None
        partial_relation_field: Optional[str] = None
        partial_related_entity_field: Optional[str] = None

        if self._partial_of_config is not None:
            partial_parent_dto = self._partial_of_config.get("dto")
            if partial_parent_dto is None or not isinstance(partial_parent_dto, type):
                raise ValueError(
                    "Configuração partial_of inválida: parâmetro 'dto' deve ser uma classe."
                )
            if not issubclass(partial_parent_dto, DTOBase):
                raise ValueError(
                    "Configuração partial_of inválida: parâmetro 'dto' deve ser subclasse de DTOBase."
                )

            partial_relation_field = self._partial_of_config.get("relation_field")
            if partial_relation_field is None or not isinstance(
                partial_relation_field, str
            ):
                raise ValueError(
                    "Configuração partial_of inválida: parâmetro 'relation_field' deve ser informado e ser uma string."
                )

            partial_related_entity_field = self._partial_of_config.get(
                "related_entity_field"
            )
            if partial_related_entity_field is not None and not isinstance(
                partial_related_entity_field, str
            ):
                raise ValueError(
                    "Configuração partial_of inválida: parâmetro 'related_entity_field' deve ser uma string."
                )

            if partial_related_entity_field is None:
                partial_related_entity_field = getattr(
                    partial_parent_dto, "pk_field", None
                )

            if partial_related_entity_field is None:
                raise ValueError(
                    "Não foi possível determinar o campo relacionado na entidade principal para a configuração partial_of."
                )

            partial_parent_fields = set(
                getattr(partial_parent_dto, "fields_map", {}).keys()
            )

            for key, attr in partial_parent_dto.__dict__.items():
                if key in cls.__dict__:
                    continue

                if isinstance(
                    attr,
                    (
                        DTOField,
                        DTOListField,
                        DTOLeftJoinField,
                        DTOSQLJoinField,
                        DTOObjectField,
                        DTOAggregator,
                    ),
                ):
                    setattr(cls, key, copy.deepcopy(attr))
                    if isinstance(attr, DTOField):
                        partial_parent_fields.add(key)

        # Iterating for the class attributes
        for key, attr in cls.__dict__.items():
            # Test if the attribute uses the DTOFiel descriptor
            if isinstance(attr, DTOField):
                # Storing field in fields_map
                getattr(cls, "fields_map")[key] = attr

                # Setting a better name to storage_name
                attr.storage_name = f"{key}"
                attr.name = f"{key}"

                # Checking filters name
                self._check_filters(cls, key, attr)

                # Copying type from annotation (if exists)
                if key in cls.__annotations__:
                    attr.expected_type = cls.__annotations__[key]

                # Checking if it is a resume field (to store)
                if attr.resume:
                    resume_fields = getattr(cls, "resume_fields")
                    if key not in resume_fields:
                        resume_fields.add(key)

                # TODO Refatorar para suportar PKs compostas
                # Setting PK info
                if attr.pk:
                    setattr(cls, "pk_field", f"{key}")

                # Verifica se é um campo de particionamento, e o guarda em caso positivo
                if attr.partition_data:
                    partition_fields = getattr(cls, "partition_fields")
                    if key not in partition_fields:
                        partition_fields.add(key)

                # Verifica se é um campo pertencente a uma unique, a populando o dicionário de uniques
                if attr.unique:
                    uniques = getattr(cls, "uniques")
                    fields_unique = uniques.setdefault(attr.unique, set())
                    fields_unique.add(key)

                # Verifica se é uma chave candidata
                if attr.candidate_key:
                    getattr(cls, "candidate_keys").append(key)

                # Verifica se é um campo passível de busca
                if attr.search:
                    getattr(cls, "search_fields").add(key)

                # Verifica se um campo é somente para leitura
                if attr.read_only and key != "atualizado_em":
                    getattr(cls, "sql_read_only_fields").append(
                        attr.entity_field or key
                    )

                if attr.no_update is True:
                    cls.sql_no_update_fields.add(attr.entity_field or key)
                    pass

                # Verifica se o campo é uma métrica do opentelemetry
                if attr.metric_label:
                    getattr(cls, "metric_fields").add(key)

                # Verifica se tem a propriedade auto_increment habilitada
                if attr.auto_increment:
                    getattr(cls, "auto_increment_fields").add(key)

                # Verifica se um campo é usado para verificação de integridade
                if attr.use_integrity_check:
                    getattr(cls, "integrity_check_fields_map")[key] = attr

            elif isinstance(attr, DTOAggregator):
                attr.storage_name = key
                attr.name = key

                if key in cls.__annotations__:
                    attr.expected_type = cls.__annotations__[key]
                    pass

                attr.not_null = False
                for _, field in attr.expected_type.fields_map.items():
                    if field.pk is True or field.not_null is True:
                        attr.not_null = True
                        break
                    pass

                cls.aggregator_fields_map[key] = attr

            elif isinstance(attr, DTOListField):
                # Storing field in fields_map
                getattr(cls, "list_fields_map")[key] = attr

                # Setting a better name to storage_name
                attr.storage_name = f"{key}"
                attr.name = f"{key}"

                # Verifica se um campo é usado para verificação de integridade
                if attr.use_integrity_check:
                    getattr(cls, "integrity_check_fields_map")[key] = attr

                if len(attr.resume_fields_tree.get("root", set())) > 0:
                    resume_fields = getattr(cls, "resume_fields")
                    if key not in resume_fields:
                        resume_fields.add(key)

            elif isinstance(attr, DTOLeftJoinField):
                # Storing field in fields_map
                getattr(cls, "left_join_fields_map")[key] = attr

                # Setting a better name to storage_name
                attr.storage_name = f"{key}"
                attr.name = f"{key}"

                # Copying type from annotation (if exists)
                if key in cls.__annotations__:
                    attr.expected_type = cls.__annotations__[key]

                # Checking if it is a resume field (to store)
                if attr.resume:
                    resume_fields = getattr(cls, "resume_fields")
                    if key not in resume_fields:
                        resume_fields.add(key)

                # Montando o mapa de controle das queries (para o service_base)
                self.set_left_join_fields_map_to_query(key, attr, cls)

            elif isinstance(attr, DTOSQLJoinField):
                # Storing field in fields_map
                getattr(cls, "sql_join_fields_map")[key] = attr

                # Setting a better name to storage_name
                attr.storage_name = f"{key}"
                attr.name = f"{key}"

                # Copying type from annotation (if exists)
                if key in cls.__annotations__:
                    attr.expected_type = cls.__annotations__[key]

                # Checking if it is a resume field (to store)
                if attr.resume:
                    resume_fields = getattr(cls, "resume_fields")
                    if key not in resume_fields:
                        resume_fields.add(key)

                if attr.partition_data is True:
                    cls.partition_fields.add(key)
                    pass

                # Montando o mapa de controle das queries (para o service_base)
                self.set_sql_join_fields_map_to_query(key, attr, cls)

            elif isinstance(attr, DTOObjectField):
                # Storing field in fields_map
                getattr(cls, "object_fields_map")[key] = attr

                # Setting a better name to storage_name
                attr.storage_name = f"{key}"
                attr.name = f"{key}"

                # Copying type from annotation (if exists)
                if key in cls.__annotations__:
                    attr.expected_type = cls.__annotations__[key]

                # Checking if it is a resume field (to store)
                if attr.resume or len(attr.resume_fields) > 0:
                    resume_fields = getattr(cls, "resume_fields")
                    if key not in resume_fields:
                        resume_fields.add(key)

            elif isinstance(attr, DTOOneToOneField):
                cls.one_to_one_fields_map[key] = attr

                attr.storage_name = str(key)
                attr.name = str(key)

                assert key in cls.__annotations__, \
                    f"`DTOOneToOneField` with name `{key}` HAS to have an" \
                    f" annotation."

                assert issubclass(cls.__annotations__[key], DTOBase), \
                    f"`DTOOneToOneField` with name `{key}` annotation's MUST" \
                    f" be a subclass of `DTOBase`." \
                    f" Is `{repr(cls.__annotations__[key])}`."

                attr.expected_type = cls.__annotations__[key]
                attr.entity_field = key

                if attr.relation_field is None:
                    attr.relation_field = key
                    cls.fields_map[key] = attr.field
                    if attr.field.entity_field is not None:
                        attr.entity_field = attr.field.entity_field
                        pass
                    pass

                if attr.resume:
                    cls.resume_fields.add(key)
                    pass
                pass

        # Setting fixed filters
        setattr(cls, "fixed_filters", self._fixed_filters)

        # Setting tipo de Conjunto
        setattr(cls, "conjunto_type", self._conjunto_type)
        setattr(cls, "conjunto_field", self._conjunto_field)

        # Setting filter aliases
        setattr(cls, "filter_aliases", self._filter_aliases)

        # Checking data_override properties exists as DTOFields
        self._validate_data_override_properties(cls)

        if partial_parent_dto is not None:
            partial_extension_fields = {
                field_name
                for field_name in getattr(cls, "fields_map").keys()
                if field_name not in partial_parent_fields
            }

            setattr(
                cls,
                "partial_dto_config",
                PartialDTOConfig(
                    parent_dto=partial_parent_dto,
                    relation_field=partial_relation_field,
                    related_entity_field=partial_related_entity_field,
                    parent_fields=partial_parent_fields,
                    extension_fields=partial_extension_fields,
                ),
            )
        else:
            setattr(cls, "partial_dto_config", None)

        return cls

    def _validate_data_override_properties(self, cls):
        for field in self._data_override_fields:
            if field not in cls.fields_map:
                raise Exception(
                    f"A propriedade '{field}', apontada como campo de sobrescrita (no 'data_override' do decorator DTO) deve existit como DTOField na classe '{cls.__name__}'."
                )

        if self._data_override_group is not None:
            for field in self._data_override_group:
                if field not in cls.fields_map:
                    raise Exception(
                        f"A propriedade '{field}', apontada como campo de agrupamento (no 'data_override' do decorator DTO) deve existit como DTOField na classe '{cls.__name__}'."
                    )

    def _check_filters(self, cls: object, field_name: str, dto_field: DTOField):
        """
        Check filters (if exists), and setting default filter name.
        """

        if dto_field.filters is None:
            return

        # Handling each filter
        for filter in dto_field.filters:
            # Resolving filter name
            filter_name = field_name
            if filter.name is not None:
                filter_name = filter.name

            # Storing field filter name
            filter.field_name = field_name

            # Adding into field filters map
            field_filters_map = getattr(cls, "field_filters_map")
            field_filters_map[filter_name] = filter

    def _check_class_attribute(self, cls: object, attr_name: str, default_value: Any):
        """
        Add attribute "attr_name" in class "cls", if not exists.
        """

        if attr_name not in cls.__dict__:
            setattr(cls, attr_name, default_value)

    def set_left_join_fields_map_to_query(
        self,
        field: str,
        attr: DTOLeftJoinField,
        cls: object,
    ):
        # Recuperando o map de facilitação das queries
        left_join_fields_map_to_query: dict[str, LeftJoinQuery] = getattr(
            cls, "left_join_fields_map_to_query"
        )

        # Verificando se o objeto de query, relativo a esse campo,
        # já estava no mapa (e colocando, caso negativo)
        map_key = (
            f"{attr.dto_type}____{attr.entity_type}____{attr.entity_relation_owner}"
        )
        left_join_query = left_join_fields_map_to_query.setdefault(
            map_key, LeftJoinQuery()
        )

        # Preenchendo as propriedades que serão úteis para as queries
        left_join_query.related_dto = attr.dto_type
        left_join_query.related_entity = attr.entity_type
        left_join_query.fields.append(field)
        left_join_query.left_join_fields.append(attr)
        left_join_query.entity_relation_owner = attr.entity_relation_owner

    def set_sql_join_fields_map_to_query(
        self,
        field: str,
        attr: DTOSQLJoinField,
        cls: object,
    ):
        # Recuperando o map de facilitação das queries
        sql_join_fields_map_to_query: dict[str, SQLJoinQuery] = getattr(
            cls, "sql_join_fields_map_to_query"
        )

        # Verificando se o objeto de query, relativo a esse campo,
        # já estava no mapa (e colocando, caso negativo)
        map_key = f"{attr.dto_type}____{attr.entity_type}____{attr.entity_relation_owner}____{attr.join_type}"
        sql_join_query = sql_join_fields_map_to_query.setdefault(
            map_key, SQLJoinQuery()
        )

        # Preenchendo as propriedades que serão úteis para as queries
        sql_join_query.related_dto = attr.dto_type
        sql_join_query.related_entity = attr.entity_type
        sql_join_query.fields.append(field)
        sql_join_query.related_fields.append(attr.related_dto_field)
        sql_join_query.join_fields.append(attr)
        sql_join_query.entity_relation_owner = attr.entity_relation_owner
        sql_join_query.join_type = attr.join_type
        sql_join_query.relation_field = attr.relation_field

        if sql_join_query.sql_alias is None:
            sql_join_query.sql_alias = f"join_table_{len(sql_join_fields_map_to_query)}"
