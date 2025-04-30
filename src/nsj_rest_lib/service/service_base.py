import copy
import uuid

from typing import Any, Callable, Dict, List, Set, Tuple

from flask import g

from nsj_rest_lib.dao.dao_base import DAOBase
from nsj_rest_lib.descriptor.dto_field import DTOFieldFilter
from nsj_rest_lib.descriptor.dto_left_join_field import (
    DTOLeftJoinField,
    EntityRelationOwner,
    LeftJoinQuery,
)
from nsj_rest_lib.descriptor.dto_object_field import DTOObjectField
from nsj_rest_lib.descriptor.filter_operator import FilterOperator
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.dto.after_insert_update_data import AfterInsertUpdateData
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.entity.filter import Filter
from nsj_rest_lib.exception import (
    DTOListFieldConfigException,
    ConflictException,
    NotFoundException,
)
from nsj_rest_lib.injector_factory_base import NsjInjectorFactoryBase
from nsj_rest_lib.validator.validate_data import validate_uuid
from nsj_rest_lib.util.join_aux import JoinAux
from nsj_rest_lib.util.type_validator_util import TypeValidatorUtil

from nsj_gcf_utils.db_adapter2 import DBAdapter2


class ServiceBase:
    _dao: DAOBase
    _dto_class: DTOBase

    def __init__(
        self,
        injector_factory: NsjInjectorFactoryBase,
        dao: DAOBase,
        dto_class: DTOBase,
        entity_class: EntityBase,
        dto_post_response_class: DTOBase = None,
    ):
        self._injector_factory = injector_factory
        self._dao = dao
        self._dto_class = dto_class
        self._entity_class = entity_class
        self._dto_post_response_class = dto_post_response_class
        self._created_by_property = "criado_por"
        self._updated_by_property = "atualizado_por"

    @staticmethod
    def construtor1(
        db_adapter: DBAdapter2,
        dao: DAOBase,
        dto_class: DTOBase,
        entity_class: EntityBase,
        dto_post_response_class: DTOBase = None,
    ):
        """
        Esse construtor alternativo, evita a necessidade de passar um InjectorFactory,
        pois esse só é usado (internamente) para recuperar um db_adapter.

        Foi feito para não gerar breaking change de imediato (a ideia porém é, no futuro,
        gerar um breaking change).
        """

        class FakeInjectorFactory:
            def db_adapter():
                return db_adapter

        return ServiceBase(
            FakeInjectorFactory(), dao, dto_class, entity_class, dto_post_response_class
        )

    def get(
        self,
        id: str,
        partition_fields: Dict[str, Any],
        fields: Dict[str, Set[str]],
    ) -> DTOBase:
        # Resolving fields
        fields = self._resolving_fields(fields)

        # Handling the fields to retrieve
        entity_fields = self._convert_to_entity_fields(fields["root"])

        # Tratando dos filtros
        all_filters = {}
        if self._dto_class.fixed_filters is not None:
            all_filters.update(self._dto_class.fixed_filters)
        if partition_fields is not None:
            all_filters.update(partition_fields)

        entity_filters = self._create_entity_filters(all_filters)

        # Resolve o campo de chave sendo utilizado
        entity_key_field, entity_id_value = self._resolve_field_key(
            id,
            partition_fields,
        )

        # Resolvendo os joins
        joins_aux = self._resolve_sql_join_fields(fields["root"], entity_filters)

        # Recuperando a entity
        entity = self._dao.get(
            entity_key_field,
            entity_id_value,
            entity_fields,
            entity_filters,
            conjunto_type=self._dto_class.conjunto_type,
            conjunto_field=self._dto_class.conjunto_field,
            joins_aux=joins_aux,
        )

        # Convertendo para DTO
        dto = self._dto_class(entity, escape_validator=True)

        # Tratando das propriedades de lista
        if len(self._dto_class.list_fields_map) > 0:
            self._retrieve_related_lists([dto], fields)

        # Tratando das propriedades de relacionamento left join
        if len(self._dto_class.left_join_fields_map) > 0:
            self._retrieve_left_join_fields(
                [dto],
                fields,
                partition_fields,
            )

        if len(self._dto_class.object_fields_map) > 0:
            self._retrieve_object_fields(
                [dto],
                fields,
                partition_fields,
            )

        return dto

    def _resolve_field_key(
        self,
        id_value: Any,
        partition_fields: Dict[str, Any],
    ) -> Tuple[str, Any]:
        """
        Verificando se o tipo de campo recebido bate com algum dos tipos dos campos chave,
        começando pela chave primária.

        Retorna uma tupla: (nome_campo_chave_na_entity, valor_chave_tratado_convertido_para_entity)
        """

        # Montando a lista de campos chave (começando pela chave primária)
        key_fields = [self._dto_class.pk_field]

        for key in self._dto_class.fields_map:
            if self._dto_class.fields_map[key].candidate_key:
                key_fields.append(key)

        # Verificando se ocorre o match em algum dos campos chave:
        retornar = False
        for candidate_key in key_fields:
            candidate_key_field = self._dto_class.fields_map[candidate_key]

            if isinstance(id_value, candidate_key_field.expected_type):
                retornar = True
            elif candidate_key_field.expected_type == uuid.UUID and validate_uuid(
                id_value
            ):
                retornar = True
                id_value = uuid.UUID(id_value)

            if retornar:
                if candidate_key_field.validator is not None:
                    id_value = candidate_key_field.validator(
                        candidate_key_field, id_value
                    )

                # Convertendo o valor para o correspoendente na entity
                entity_key_field = self._convert_to_entity_field(candidate_key)
                converted_values = self._dto_class.custom_convert_value_to_entity(
                    id_value,
                    candidate_key_field,
                    entity_key_field,
                    False,
                    partition_fields,
                )
                if len(converted_values) <= 0:
                    value = self._dto_class.convert_value_to_entity(
                        id_value,
                        candidate_key_field,
                        False,
                        self._entity_class,
                    )
                    converted_values = {entity_key_field: value}

                # Utilizando apenas o valor correspondente ao da chave selecionada
                id_value = converted_values[entity_key_field]

                return (entity_key_field, id_value)

        # Se não pode encontrar uma chave correspondente
        raise ValueError(
            f"Não foi possível identificar o ID recebido com qualquer das chaves candidatas reconhecidas. Valor recebido: {id_value}."
        )

    def _convert_to_entity_fields(
        self,
        fields: Set[str],
        dto_class=None,
        entity_class=None,
    ) -> List[str]:
        """
        Convert a list of fields names to a list of entity fields names.
        """

        if fields is None:
            return None

        # TODO Refatorar para não precisar deste objeto só por conta das propriedades da classe
        # (um decorator na classe, poderia armazenar os fields na mesma, como é feito no DTO)
        if entity_class is None:
            entity = self._entity_class()
        else:
            entity = entity_class()

        # Resolvendo a classe padrão de DTO
        if dto_class is None:
            dto_class = self._dto_class

        entity_fields = []
        for field in fields:
            # Skipping not DTO fields
            if field not in dto_class.fields_map:
                continue

            entity_field_name = self._convert_to_entity_field(field, dto_class)
            # Skipping not Entity fields
            if entity_field_name not in entity.__dict__:
                continue

            entity_fields.append(entity_field_name)

        return entity_fields

    def _convert_to_entity_field(
        self,
        field: str,
        dto_class=None,
    ) -> str:
        """
        Convert a field name to a entity field name.
        """

        # Resolvendo a classe padrão de DTO
        if dto_class is None:
            dto_class = self._dto_class

        entity_field_name = field
        if dto_class.fields_map[field].entity_field is not None:
            entity_field_name = dto_class.fields_map[field].entity_field

        return entity_field_name

    def _create_entity_filters(
        self, filters: Dict[str, Any]
    ) -> Dict[str, List[Filter]]:
        """
        Converting DTO filters to Entity filters.

        Returns a Dict (indexed by entity field name) of List of Filter.
        """
        if filters is None:
            return None

        # Construindo um novo dict de filtros para controle
        aux_filters = copy.deepcopy(filters)
        fist_run = True

        # Dicionário para guardar os filtros convertidos
        entity_filters = {}

        # Iterando enquanto houver filtros recebidos, ou derivalos a partir dos filter_aliases
        while len(aux_filters) > 0:
            new_filters = {}

            for filter in aux_filters:
                is_entity_filter = False
                is_conjunto_filter = False
                is_sql_join_filter = False
                dto_field = None
                dto_sql_join_field = None
                table_alias = None

                # Recuperando os valores passados nos filtros
                if isinstance(aux_filters[filter], str):
                    values = aux_filters[filter].split(",")
                else:
                    values = [aux_filters[filter]]

                if len(values) <= 0:
                    # Se não houver valor a filtrar, o filtro é apenas ignorado
                    continue

                # Identificando o tipo de filtro passado
                if (
                    self._dto_class.filter_aliases is not None
                    and filter in self._dto_class.filter_aliases
                    and fist_run
                ):
                    # Verificando se é um alias para outros filtros (o alias aponta para outros filtros,
                    # de acordo com o tipo do dado recebido)
                    filter_aliases = self._dto_class.filter_aliases[filter]

                    # Iterando os tipos definidos para o alias, e verificando se casam com o tipo recebido
                    for type_alias in filter_aliases:
                        relative_field = filter_aliases[type_alias]

                        # Esse obj abaixo é construído artificialmente, com os campos esperados no método validate
                        # Se o validate mudar, tem que refatorar aqui:
                        class OBJ:
                            def __init__(self) -> None:
                                self.expected_type = None
                                self.storage_name = None

                        obj = OBJ()
                        obj.expected_type = type_alias
                        obj.storage_name = filter

                        # Verificando se é possível converter o valor recebido para o tipo definido no alias do filtro
                        try:
                            TypeValidatorUtil.validate(obj, values[0])
                            convertido = True
                        except Exception:
                            convertido = False

                        if convertido:
                            # Se conseguiu converter para o tipo correspondente, se comportará exatamente como um novo
                            # filtro, porém como se tivesse sido passado para o campo correspondente ao tipo:
                            if relative_field not in new_filters:
                                new_filters[relative_field] = aux_filters[filter]
                            else:
                                new_filters[relative_field] = (
                                    f"{new_filters[relative_field]},{aux_filters[filter]}"
                                )
                            break

                        else:
                            # Se não encontrar conseguir converter (até o final, será apenas ignorado)
                            pass

                    continue

                elif filter in self._dto_class.field_filters_map:
                    # Retrieving filter config
                    field_filter = self._dto_class.field_filters_map[filter]
                    aux = self._dto_class.field_filters_map[filter].field_name
                    dto_field = self._dto_class.fields_map[aux]

                elif filter == self._dto_class.conjunto_field:
                    is_conjunto_filter = True
                    dto_field = self._dto_class.fields_map[
                        self._dto_class.conjunto_field
                    ]

                elif filter in self._dto_class.fields_map:
                    # Creating filter config to a DTOField (equals operator)
                    field_filter = DTOFieldFilter(filter)
                    field_filter.set_field_name(filter)
                    dto_field = self._dto_class.fields_map[filter]

                elif filter in self._dto_class.sql_join_fields_map:
                    # Creating filter config to a DTOSQLJoinField (equals operator)
                    is_sql_join_filter = True
                    field_filter = DTOFieldFilter(filter)
                    field_filter.set_field_name(filter)
                    dto_sql_join_field = self._dto_class.sql_join_fields_map[filter]
                    dto_field = dto_sql_join_field.dto_type.fields_map[
                        dto_sql_join_field.related_dto_field
                    ]

                    # Procurando o table alias
                    for join_query_key in self._dto_class.sql_join_fields_map_to_query:
                        join_query = self._dto_class.sql_join_fields_map_to_query[
                            join_query_key
                        ]
                        if filter in join_query.fields:
                            table_alias = join_query.sql_alias

                # TODO Refatorar para usar um mapa de fields do entity
                elif filter in self._entity_class().__dict__:
                    is_entity_filter = True

                else:
                    # Ignoring not declared filters (or filter for not existent DTOField)
                    continue

                # Resolving entity field name (to filter)
                if (
                    not is_entity_filter
                    and not is_conjunto_filter
                    and not is_sql_join_filter
                ):
                    entity_field_name = self._convert_to_entity_field(
                        field_filter.field_name
                    )
                elif is_sql_join_filter:
                    # TODO Verificar se precisa de um if dto_sql_join_field.related_dto_field in dto_sql_join_field.dto_type.fields_map
                    entity_field_name = dto_sql_join_field.dto_type.fields_map[
                        dto_sql_join_field.related_dto_field
                    ].get_entity_field_name()
                else:
                    entity_field_name = filter

                # Creating entity filters (one for each value - separated by comma)
                for value in values:
                    if isinstance(value, str):
                        value = value.strip()

                    # Resolvendo as classes de DTO e Entity
                    aux_dto_class = self._dto_class
                    aux_entity_class = self._entity_class

                    if is_sql_join_filter:
                        aux_dto_class = dto_sql_join_field.dto_type
                        aux_entity_class = dto_sql_join_field.entity_type

                    # Convertendo os valores para o formato esperado no entity
                    if not is_entity_filter and not is_sql_join_filter:
                        converted_values = aux_dto_class.custom_convert_value_to_entity(
                            value,
                            dto_field,
                            entity_field_name,
                            False,
                            aux_filters,
                        )
                        if len(converted_values) <= 0:
                            value = aux_dto_class.convert_value_to_entity(
                                value,
                                dto_field,
                                False,
                                aux_entity_class,
                            )
                            converted_values = {entity_field_name: value}

                    else:
                        converted_values = {entity_field_name: value}

                    # Tratando cada valor convertido
                    for entity_field in converted_values:
                        converted_value = converted_values[entity_field]

                        if (
                            not is_entity_filter
                            and not is_conjunto_filter
                            and not is_sql_join_filter
                        ):
                            entity_filter = Filter(
                                field_filter.operator, converted_value
                            )
                        elif is_sql_join_filter:
                            entity_filter = Filter(
                                field_filter.operator, converted_value, table_alias
                            )
                        else:
                            entity_filter = Filter(
                                FilterOperator.EQUALS, converted_value
                            )

                        # Storing filter in dict
                        filter_list = entity_filters.setdefault(entity_field, [])
                        filter_list.append(entity_filter)

            # Ajustando as variáveis de controle
            fist_run = False
            aux_filters = {}
            aux_filters.update(new_filters)

        return entity_filters

    def _resolving_fields(self, fields: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        """
        Verifica os fields recebidos, garantindo que os campos de resumo serão considerados.
        """

        # Resolving fields
        if fields is None:
            result = {"root": self._dto_class.resume_fields}
        else:
            result = copy.deepcopy(fields)
            result["root"] = result["root"].union(self._dto_class.resume_fields)

        return result

    def filter_list(self, filters: Dict[str, Any]):
        return self.list(
            None,
            None,
            {"root": set()},
            None,
            filters,
        )

    def _resolve_sql_join_fields(
        self,
        fields: Set[str],
        entity_filters: Dict[str, List[Filter]],
    ) -> List[JoinAux]:
        """
        Analisa os campos de jooin solicitados, e monta uma lista de objetos
        para auxiliar o DAO na construção da query
        """

        # Criando o objeto de retorno
        joins_aux: List[JoinAux] = []

        # Iterando os campos de join configurados, mas só considerando os solicitados (ou de resumo)
        for join_field_map_to_query_key in self._dto_class.sql_join_fields_map_to_query:
            join_field_map_to_query = self._dto_class.sql_join_fields_map_to_query[
                join_field_map_to_query_key
            ]

            used_join_fields = set()

            # Verificando se um dos campos desse join será usado
            for join_field in join_field_map_to_query.fields:
                # Recuperando o nome do campo, na entity
                entity_join_field = join_field_map_to_query.related_dto.fields_map[
                    self._dto_class.sql_join_fields_map[join_field].related_dto_field
                ].get_entity_field_name()

                if join_field in fields or entity_join_field in entity_filters:
                    relate_join_field = self._dto_class.sql_join_fields_map[
                        join_field
                    ].related_dto_field
                    used_join_fields.add(relate_join_field)

            # Pulando esse join (se não for usado)
            if len(used_join_fields) <= 0:
                continue

            # Construindo o objeto auxiliar do join
            join_aux = JoinAux()

            # Resolvendo os nomes dos fields da entidade relacionada
            join_entity_fields = self._convert_to_entity_fields(
                fields=used_join_fields,
                dto_class=join_field_map_to_query.related_dto,
                entity_class=join_field_map_to_query.related_entity,
            )

            join_aux.fields = join_entity_fields

            # Resolvendo tabela, tipo de join e alias
            other_entity = join_field_map_to_query.related_entity()
            join_aux.table = other_entity.get_table_name()
            join_aux.type = join_field_map_to_query.join_type
            join_aux.alias = join_field_map_to_query.sql_alias

            # Resovendo os campos usados no join
            if (
                join_field_map_to_query.entity_relation_owner
                == EntityRelationOwner.SELF
            ):
                join_aux.self_field = self._dto_class.fields_map[
                    join_field_map_to_query.relation_field
                ].get_entity_field_name()
                join_aux.other_field = other_entity.get_pk_field()
            else:
                join_aux.self_field = self._entity_class().get_pk_field()
                join_aux.other_field = join_field_map_to_query.related_dto.fields_map[
                    join_field_map_to_query.relation_field
                ].get_entity_field_name()

            joins_aux.append(join_aux)

        return joins_aux

    def list(
        self,
        after: uuid.UUID,
        limit: int,
        fields: Dict[str, Set[str]],
        order_fields: List[str],
        filters: Dict[str, Any],
        search_query: str = None,
    ) -> List[DTOBase]:
        # Resolving fields
        fields = self._resolving_fields(fields)

        # Handling the fields to retrieve
        entity_fields = self._convert_to_entity_fields(fields["root"])

        # Handling order fields
        order_fields = self._convert_to_entity_fields(order_fields)

        # Tratando dos filtros
        all_filters = {}
        if self._dto_class.fixed_filters is not None:
            all_filters.update(self._dto_class.fixed_filters)
        if filters is not None:
            all_filters.update(filters)

        entity_filters = self._create_entity_filters(all_filters)

        # Tratando dos campos a serem enviados ao DAO para uso do search (se necessário)
        search_fields = None
        if self._dto_class.search_fields is not None:
            search_fields = self._convert_to_entity_fields(
                self._dto_class.search_fields
            )

        # Resolve o campo de chave sendo utilizado
        entity_key_field, entity_id_value = (None, None)
        if after is not None:
            entity_key_field, entity_id_value = self._resolve_field_key(
                after,
                filters,
            )

        # Resolvendo os joins
        joins_aux = self._resolve_sql_join_fields(fields["root"], entity_filters)

        # Retrieving from DAO
        entity_list = self._dao.list(
            after,
            limit,
            entity_fields,
            order_fields,
            entity_filters,
            conjunto_type=self._dto_class.conjunto_type,
            conjunto_field=self._dto_class.conjunto_field,
            entity_key_field=entity_key_field,
            entity_id_value=entity_id_value,
            search_query=search_query,
            search_fields=search_fields,
            joins_aux=joins_aux,
        )

        # Convertendo para uma lista de DTOs
        dto_list = [
            self._dto_class(entity, escape_validator=True) for entity in entity_list
        ]

        # Retrieving related lists
        if len(self._dto_class.list_fields_map) > 0:
            self._retrieve_related_lists(dto_list, fields)

        # Tratando das propriedades de relacionamento left join
        # TODO Verificar se está certo passar os filtros como campos de partição
        if len(self._dto_class.left_join_fields_map) > 0:
            self._retrieve_left_join_fields(
                dto_list,
                fields,
                filters,
            )

        if len(self._dto_class.object_fields_map) > 0:
            self._retrieve_object_fields(
                dto_list,
                fields,
                filters,
            )

        # Returning
        return dto_list

    def _retrieve_related_lists(
        self, dto_list: List[DTOBase], fields: Dict[str, Set[str]]
    ):
        # TODO Controlar profundidade?!

        # Handling each dto
        for dto in dto_list:
            # Handling each related list
            for master_dto_attr, list_field in self._dto_class.list_fields_map.items():
                if master_dto_attr in fields["root"]:
                    # Getting service instance
                    if list_field.service_name is not None:
                        service = self._injector_factory.get_service_by_name(
                            list_field.service_name
                        )
                    else:
                        service = ServiceBase(
                            self._injector_factory,
                            DAOBase(
                                self._injector_factory.db_adapter(),
                                list_field.entity_type,
                            ),
                            list_field.dto_type,
                            list_field.entity_type,
                        )

                    # Checking if pk_field exists
                    if self._dto_class.pk_field is None:
                        raise DTOListFieldConfigException(
                            f"PK field not found in class: {self._dto_class}"
                        )

                    if self._dto_class.pk_field not in dto.__dict__:
                        raise DTOListFieldConfigException(
                            f"PK field not found in DTO: {self._dto_class}"
                        )

                    # Resolvendo a chave do relacionamento
                    relation_key_field = self._dto_class.pk_field
                    if list_field.relation_key_field is not None:
                        relation_key_field = list_field.relation_key_field

                    # Getting value to filter related list
                    relation_filter_value = getattr(dto, relation_key_field)
                    if relation_filter_value is None:
                        # If None, there is no related objects. So, set empty list and continue.
                        setattr(dto, master_dto_attr, [])
                        continue

                    # Making filter to relation
                    filters = {list_field.related_entity_field: relation_filter_value}

                    # Tratando campos de particionamento
                    for field in self._dto_class.partition_fields:
                        if field in list_field.dto_type.partition_fields:
                            filters[field] = getattr(dto, field)

                    # Resolvendo os fields da entidade aninhada
                    fields_to_list = copy.deepcopy(fields)
                    if master_dto_attr in fields:
                        fields_to_list["root"] = fields[master_dto_attr]
                        del fields_to_list[master_dto_attr]
                    else:
                        fields_to_list["root"] = set()

                    # Getting related data
                    related_dto_list = service.list(
                        None, None, fields_to_list, None, filters
                    )

                    # Setting dto property
                    setattr(dto, master_dto_attr, related_dto_list)

    def insert(
        self,
        dto: DTOBase,
        aditional_filters: Dict[str, Any] = None,
        custom_before_insert: Callable = None,
        custom_after_insert: Callable = None,
        retrieve_after_insert: bool = False,
    ) -> DTOBase:
        return self._save(
            insert=True,
            dto=dto,
            manage_transaction=True,
            partial_update=False,
            aditional_filters=aditional_filters,
            custom_before_insert=custom_before_insert,
            custom_after_insert=custom_after_insert,
            retrieve_after_insert=retrieve_after_insert,
        )

    def insert_list(
        self,
        dtos: List[DTOBase],
        aditional_filters: Dict[str, Any] = None,
        custom_before_insert: Callable = None,
        custom_after_insert: Callable = None,
        retrieve_after_insert: bool = False,
    ) -> List[DTOBase]:
        _lst_return = []
        try:
            self._dao.begin()

            for dto in dtos:
                _return_object = self._save(
                    insert=True,
                    dto=dto,
                    manage_transaction=False,
                    partial_update=False,
                    aditional_filters=aditional_filters,
                    custom_before_insert=custom_before_insert,
                    custom_after_insert=custom_after_insert,
                    retrieve_after_insert=retrieve_after_insert,
                )

                if _return_object is not None:
                    _lst_return.append(_return_object)

        except:
            self._dao.rollback()
            raise
        finally:
            self._dao.commit()

        return _lst_return

    def update(
        self,
        dto: DTOBase,
        id: Any,
        aditional_filters: Dict[str, Any] = None,
        custom_before_update: Callable = None,
        custom_after_update: Callable = None,
        upsert: bool = False,
    ) -> DTOBase:
        return self._save(
            insert=False,
            dto=dto,
            manage_transaction=True,
            partial_update=False,
            id=id,
            aditional_filters=aditional_filters,
            custom_before_update=custom_before_update,
            custom_after_update=custom_after_update,
            upsert=upsert,
        )

    def update_list(
        self,
        dtos: List[DTOBase],
        aditional_filters: Dict[str, Any] = None,
        custom_before_update: Callable = None,
        custom_after_update: Callable = None,
        upsert: bool = False,
    ) -> List[DTOBase]:
        _lst_return = []
        try:
            self._dao.begin()

            for dto in dtos:
                _return_object = self._save(
                    insert=False,
                    dto=dto,
                    manage_transaction=True,
                    partial_update=False,
                    id=getattr(dto, dto.pk_field),
                    aditional_filters=aditional_filters,
                    custom_before_update=custom_before_update,
                    custom_after_update=custom_after_update,
                    upsert=upsert,
                )

                if _return_object is not None:
                    _lst_return.append(_return_object)

        except:
            self._dao.rollback()
            raise
        finally:
            self._dao.commit()

        return _lst_return

    def partial_update(
        self,
        dto: DTOBase,
        id: Any,
        aditional_filters: Dict[str, Any] = None,
        custom_before_update: Callable = None,
        custom_after_update: Callable = None,
    ) -> DTOBase:
        return self._save(
            insert=False,
            dto=dto,
            manage_transaction=True,
            partial_update=True,
            id=id,
            aditional_filters=aditional_filters,
            custom_before_update=custom_before_update,
            custom_after_update=custom_after_update,
        )

    def _make_fields_from_dto(self, dto: DTOBase, root_name: str = "root"):
        # Adicionando os campos normais do DTO
        fields = {root_name: set()}
        for field in dto.fields_map:
            if field in dto.__dict__:
                fields[root_name].add(field)

        # Adicionando os campos de lista, contidos no DTO
        for list_field in dto.list_fields_map:
            if list_field in dto.__dict__:
                list_dto = getattr(dto, list_field)
                if not list_dto:
                    continue

                fields[root_name].add(list_field)
                list_fields = self._make_fields_from_dto(list_dto[0], list_field)
                fields = {**fields, **list_fields}

        return fields

    def _save(
        self,
        insert: bool,
        dto: DTOBase,
        manage_transaction: bool,
        partial_update: bool,
        relation_field_map: Dict[str, Any] = None,
        id: Any = None,
        aditional_filters: Dict[str, Any] = None,
        custom_before_insert: Callable = None,
        custom_before_update: Callable = None,
        custom_after_insert: Callable = None,
        custom_after_update: Callable = None,
        upsert: bool = False,
        retrieve_after_insert: bool = False,
    ) -> DTOBase:
        try:
            # Guardando um ponteiro para o DTO recebido
            received_dto = dto

            if manage_transaction:
                self._dao.begin()

            old_dto = None
            # Recuperando o DTO antes da gravação (apenas se for update, e houver um custom_after_update)
            if not insert and not upsert:
                old_dto = self._retrieve_old_dto(dto, id, aditional_filters)
                setattr(dto, dto.pk_field, getattr(old_dto, dto.pk_field))

            if not insert and upsert:
                old_dto = dto

            if custom_before_insert:
                received_dto = copy.deepcopy(dto)
                dto = custom_before_insert(self._dao._db, dto)

            if custom_before_update:
                if received_dto == dto:
                    received_dto = copy.deepcopy(dto)
                dto = custom_before_update(self._dao._db, old_dto, dto)

            # Convertendo o DTO para a Entity
            # TODO Refatorar para usar um construtor do EntityBase (ou algo assim, porque é preciso tratar das equivalências de nome dos campos)
            entity = dto.convert_to_entity(self._entity_class, partial_update)

            # Resolvendo o id
            if id is None:
                id = getattr(entity, entity.get_pk_field())

            # Tratando do valor do id no Entity
            entity_pk_field = self._entity_class().get_pk_field()
            if getattr(entity, entity_pk_field) is None and insert:
                setattr(entity, entity_pk_field, id)

            # Setando na Entity os campos de relacionamento recebidos
            if relation_field_map is not None:
                for entity_field, value in relation_field_map.items():
                    if hasattr(entity, entity_field):
                        setattr(entity, entity_field, value)
                        if entity_field not in entity._sql_fields:
                            entity._sql_fields.append(entity_field)

            # Setando campos criado_por e atualizado_por quando existirem
            if (insert and hasattr(entity, self._created_by_property)) or (
                hasattr(entity, self._updated_by_property)
            ):
                if hasattr(g, "profile") and g.profile is not None:
                    auth_type_is_api_key = g.profile["authentication_type"] == "api_key"
                    user = g.profile["email"]
                    if insert and hasattr(entity, self._created_by_property):
                        if not auth_type_is_api_key:
                            setattr(entity, self._created_by_property, user)
                        else:
                            value = getattr(entity, self._created_by_property)
                            if value is None or value == "":
                                raise ValueError(
                                    f"É necessário preencher o campo '{self._created_by_property}'."
                                )
                    if hasattr(entity, self._updated_by_property):
                        if not auth_type_is_api_key:
                            setattr(entity, self._updated_by_property, user)
                        else:
                            value = getattr(entity, self._updated_by_property)
                            if value is None or value == "":
                                raise ValueError(
                                    f"É necessário preencher o campo '{self._updated_by_property}'"
                                )

            # Montando os filtros recebidos (de partição, normalmente)
            if aditional_filters is not None:
                aditional_entity_filters = self._create_entity_filters(
                    aditional_filters
                )
            else:
                aditional_entity_filters = {}

            # Validando as uniques declaradas
            for unique in self._dto_class.uniques:
                unique = self._dto_class.uniques[unique]
                self._check_unique(
                    dto,
                    entity,
                    aditional_entity_filters,
                    unique,
                    old_dto,
                )

            # Invocando o DAO
            if insert:
                # Verificando se há outro registro com mesma PK
                # TODO Verificar a existência considerando os conjuntos
                if self.entity_exists(entity, aditional_entity_filters):
                    raise ConflictException(
                        f"Já existe um registro no banco com o identificador '{getattr(entity, entity_pk_field)}'"
                    )

                # Inserindo o registro no banco
                entity = self._dao.insert(entity, dto.sql_read_only_fields)

                # Inserindo os conjuntos (se necessário)
                if self._dto_class.conjunto_type is not None:
                    conjunto_field_value = getattr(dto, self._dto_class.conjunto_field)

                    aditional_filters[self._dto_class.conjunto_field] = conjunto_field_value

                    self._dao.insert_relacionamento_conjunto(
                        id, conjunto_field_value, self._dto_class.conjunto_type
                    )
            else:
                # Executando o update pelo DAO
                entity = self._dao.update(
                    entity.get_pk_field(),
                    getattr(old_dto, dto.pk_field),
                    entity,
                    aditional_entity_filters,
                    partial_update,
                    dto.sql_read_only_fields,
                    upsert,
                )

            # Convertendo a entity para o DTO de resposta (se houver um)
            if self._dto_post_response_class is not None and not retrieve_after_insert:
                response_dto = self._dto_post_response_class(
                    entity, escape_validator=True
                )
            else:
                # Retorna None, se não se espera um DTO de resposta
                response_dto = None

            # Salvando as lista de DTO detalhe
            if len(self._dto_class.list_fields_map) > 0:
                self._save_related_lists(
                    insert, dto, entity, partial_update, response_dto, aditional_filters
                )

            # Chamando os métodos customizados de after insert ou update
            if custom_after_insert is not None or custom_after_update is not None:
                new_dto = self._dto_class(entity, escape_validator=True)

                for list_field in dto.list_fields_map:
                    setattr(new_dto, list_field, getattr(dto, list_field))

                # Adicionando campo de conjunto
                if (
                    self._dto_class.conjunto_field is not None
                    and getattr(new_dto, self._dto_class.conjunto_field) is None
                ):
                    value_conjunto = getattr(dto, self._dto_class.conjunto_field)
                    setattr(new_dto, self._dto_class.conjunto_field, value_conjunto)

            # Montando um objeto de dados a serem passados para os códigos customizados
            # do tipo after insert ou update
            after_data = AfterInsertUpdateData()
            after_data.received_dto = received_dto

            # Invocando os códigos customizados do tipo after insert ou update
            if insert:
                if custom_after_insert is not None:
                    custom_after_insert(self._dao._db, new_dto, after_data)
            else:
                if custom_after_update is not None:
                    custom_after_update(self._dao._db, old_dto, new_dto, after_data)

            if retrieve_after_insert:
                response_dto = self.get(id, aditional_filters, None)

            # Retornando o DTO de resposta
            return response_dto

        except:
            if manage_transaction:
                self._dao.rollback()
            raise
        finally:
            if manage_transaction:
                self._dao.commit()

    def _retrieve_old_dto(self, dto, id, aditional_filters):
        fields = self._make_fields_from_dto(dto)
        get_filters = copy.deepcopy(aditional_filters)

        # Adicionando filtro de conjunto
        if (
            self._dto_class.conjunto_field is not None
            and self._dto_class.conjunto_field not in get_filters
        ):
            get_filters[self._dto_class.conjunto_field] = getattr(
                dto, self._dto_class.conjunto_field
            )

            # Adicionando filtros de partição de dados
        for pt_field in dto.partition_fields:
            pt_value = getattr(dto, pt_field, None)
            if pt_value is not None:
                get_filters[pt_field] = pt_value

                # Recuperando o DTO antigo
        old_dto = self.get(id, get_filters, fields)

        # Adicionando campo de conjunto
        if (
            self._dto_class.conjunto_field is not None
            and getattr(old_dto, self._dto_class.conjunto_field) is None
        ):
            value_conjunto = getattr(dto, self._dto_class.conjunto_field)
            setattr(old_dto, self._dto_class.conjunto_field, value_conjunto)
        return old_dto

    def _save_related_lists(
        self,
        insert: bool,
        dto: DTOBase,
        entity: EntityBase,
        partial_update: bool,
        response_dto: DTOBase,
        aditional_filters: Dict[str, Any] = None,
    ):
        # TODO Controlar profundidade?!

        # Handling each related list
        for master_dto_field, list_field in self._dto_class.list_fields_map.items():
            response_list = []

            # Recuperando a lista de DTOs a salvar
            detail_list = getattr(dto, master_dto_field)

            # Verificando se lista está preenchida
            if detail_list is None:
                continue

            # Recuperna uma instância do DAO da Entidade Detalhe
            detail_dao = DAOBase(
                self._injector_factory.db_adapter(), list_field.entity_type
            )

            # Getting service instance
            if list_field.service_name is not None:
                detail_service = self._injector_factory.get_service_by_name(
                    list_field.service_name
                )
            else:
                detail_service = ServiceBase(
                    self._injector_factory,
                    detail_dao,
                    list_field.dto_type,
                    list_field.entity_type,
                    list_field.dto_post_response_type,
                )

            # Resolvendo a chave do relacionamento
            relation_key_field = entity.get_pk_field()
            if list_field.relation_key_field is not None:
                relation_key_field = dto.get_entity_field_name(
                    list_field.relation_key_field
                )

            # Recuperando o valor da PK da entidade principal
            relation_key_value = getattr(entity, relation_key_field)

            # Montando um mapa com os campos de relacionamento (para gravar nas entidades relacionadas)
            relation_field_map = {
                list_field.related_entity_field: relation_key_value,
            }

            # Recuperando todos os IDs dos itens de lista já salvos no BD (se for um update)
            old_detail_ids = None
            if not insert:
                # Montando o filtro para recuperar os objetos detalhe pré-existentes
                relation_condiction = Filter(FilterOperator.EQUALS, relation_key_value)

                relation_filter = {
                    list_field.related_entity_field: [relation_condiction]
                }

                # Tratando campos de particionamento
                for field in self._dto_class.partition_fields:
                    if field in list_field.dto_type.partition_fields:
                        relation_filter[field] = [
                            Filter(FilterOperator.EQUALS, getattr(dto, field))
                        ]

                # Recuperando do BD
                old_detail_ids = detail_dao.list_ids(relation_filter)

            # Lista de DTOs detalhes a criar ou atualizar
            detail_upsert_list = []

            # Salvando cada DTO detalhe
            for detail_dto in detail_list:
                # Recuperando o ID da entidade relacionada
                detail_pk_field = detail_dto.__class__.pk_field
                detail_pk = getattr(detail_dto, detail_pk_field)

                # Verificando se é um update ou insert
                is_detail_insert = True
                if old_detail_ids is not None and detail_pk in old_detail_ids:
                    is_detail_insert = False
                    old_detail_ids.remove(detail_pk)

                # Checking if pk_field exists
                if self._dto_class.pk_field is None:
                    raise DTOListFieldConfigException(
                        f"PK field not found in class: {self._dto_class}"
                    )

                if self._dto_class.pk_field not in dto.__dict__:
                    raise DTOListFieldConfigException(
                        f"PK field not found in DTO: {self._dto_class}"
                    )

                # Salvando o dto dependende (detalhe) na lista
                detail_upsert_list.append(
                    {
                        "is_detail_insert": is_detail_insert,
                        "detail_dto": detail_dto,
                        "detail_pk": detail_pk,
                    }
                )

            # Verificando se sobraram relacionamentos anteriores para remover
            if (
                not partial_update
                and old_detail_ids is not None
                and len(old_detail_ids) > 0
            ):
                for old_id in old_detail_ids:
                    # Apagando cada relacionamento removido
                    detail_service.delete(old_id, aditional_filters)

            # Salvando cada DTO detalhe
            for item in detail_upsert_list:
                response_detail_dto = detail_service._save(
                    item["is_detail_insert"],
                    item["detail_dto"],
                    False,
                    partial_update,
                    relation_field_map,
                    item["detail_pk"],
                    aditional_filters=aditional_filters,
                )

                # Guardando o DTO na lista de retorno
                response_list.append(response_detail_dto)

            # Setting dto property
            if (
                response_dto is not None
                and master_dto_field in response_dto.list_fields_map
                and list_field.dto_post_response_type is not None
            ):
                setattr(response_dto, master_dto_field, response_list)

    def delete(
        self,
        id: Any,
        additional_filters: Dict[str, Any] = None,
        custom_before_delete=None,
    ) -> DTOBase:
        self._delete(
            id,
            manage_transaction=True,
            additional_filters=additional_filters,
            custom_before_delete=custom_before_delete,
        )

    def delete_list(self, ids: list, additional_filters: Dict[str, Any] = None):
        try:
            self._dao.begin()

            for _id in ids:
                self._delete(
                    _id, manage_transaction=True, additional_filters=additional_filters
                )

        except:
            self._dao.rollback()
            raise
        finally:
            self._dao.commit()

    def entity_exists(
        self,
        entity: EntityBase,
        entity_filters: Dict[str, List[Filter]],
    ):
        # Getting values
        entity_pk_field = entity.get_pk_field()
        entity_pk_value = getattr(entity, entity_pk_field)

        if entity_pk_value is None:
            return False

        # Searching entity in DB
        try:
            self._dao.get(
                entity_pk_field,
                entity_pk_value,
                [entity.get_pk_field()],
                entity_filters,
            )
        except NotFoundException:
            return False

        return True

    def _check_unique(
        self,
        dto: DTOBase,
        entity: EntityBase,
        entity_filters: Dict[str, List[Filter]],
        unique: Set[str],
        old_dto: DTOBase,
    ):
        # Tratando dos filtros recebidos (de partição), e adicionando os filtros da unique
        unique_filter = {}
        for field in unique:
            value = getattr(dto, field)
            # Se um dos campos for nulos, então a unique é falsa. Isso é baseado no postgres aonde null é sempre diferente de null para uniques
            if value is None:
                return
            unique_filter[field] = value

        # Convertendo o filtro para o formato de filtro de entidades
        unique_entity_filters = self._create_entity_filters(unique_filter)

        # Removendo o campo chave, se estiver no filtro
        if entity.get_pk_field() in unique_entity_filters:
            del unique_entity_filters[entity.get_pk_field()]

        # Se não há mais campos na unique, não há o que validar
        if len(unique_entity_filters) <= 0:
            return

        # Montando o entity filter final
        entity_filters = {**entity_filters, **unique_entity_filters}

        # Montando filtro de PK diferente (se necessário, isto é, se for update)
        filters_pk = entity_filters.setdefault(entity.get_pk_field(), [])
        filters_pk.append(
            Filter(
                FilterOperator.DIFFERENT,
                (
                    getattr(old_dto, dto.pk_field)
                    if old_dto is not None
                    else getattr(dto, dto.pk_field)
                ),
            )
        )

        # Searching entity in DB
        try:
            encontrados = self._dao.list(
                None,
                1,
                [entity.get_pk_field()],
                None,
                entity_filters,
            )

            if len(encontrados) >= 1:
                raise ConflictException(
                    f"Restrição de unicidade violada para a unique: {unique}"
                )
        except NotFoundException:
            return

    def _delete(
        self,
        id: str,
        manage_transaction: bool,
        additional_filters: Dict[str, Any] = None,
        custom_before_delete=None,
    ) -> DTOBase:
        try:
            if manage_transaction:
                self._dao.begin()

            # Função para validar ou fazer outras consultas antes de deletar
            if custom_before_delete is not None:
                dto = self.get(id, additional_filters, None)
                custom_before_delete(self._dao._db, dto)

            # Convertendo os filtros para os filtros de entidade
            entity_filters = {}
            if additional_filters is not None:
                entity_filters = self._create_entity_filters(additional_filters)

            # Adicionando o ID nos filtros
            id_condiction = Filter(FilterOperator.EQUALS, id)

            pk_field = self._entity_class().get_pk_field()
            entity_filters[pk_field] = [id_condiction]

            # Tratando das propriedades de lista
            if len(self._dto_class.list_fields_map) > 0:
                self._delete_related_lists(id, additional_filters)

            # Excluindo os conjuntos (se necessário)
            if self._dto_class.conjunto_type is not None:
                self._dao.delete_relacionamento_conjunto(
                    id, self._dto_class.conjunto_type
                )

            # Excluindo a entity principal
            self._dao.delete(entity_filters)
        except:
            if manage_transaction:
                self._dao.rollback()
            raise
        finally:
            if manage_transaction:
                self._dao.commit()

    def _delete_related_lists(self, id, additional_filters: Dict[str, Any] = None):
        # Handling each related list
        for _, list_field in self._dto_class.list_fields_map.items():
            # Getting service instance
            if list_field.service_name is not None:
                service = self._injector_factory.get_service_by_name(
                    list_field.service_name
                )
            else:
                service = ServiceBase(
                    self._injector_factory,
                    DAOBase(
                        self._injector_factory.db_adapter(), list_field.entity_type
                    ),
                    list_field.dto_type,
                    list_field.entity_type,
                )

            # Making filter to relation
            filters = {
                # TODO Adicionar os campos de particionamento de dados
                list_field.related_entity_field: id
            }

            # Getting related data
            related_dto_list = service.list(None, None, {"root": set()}, None, filters)

            # Excluindo cada entidade detalhe
            for related_dto in related_dto_list:
                # Checking if pk_field exists
                if list_field.dto_type.pk_field is None:
                    raise DTOListFieldConfigException(
                        f"PK field not found in class: {self._dto_class}"
                    )

                if list_field.dto_type.pk_field not in related_dto.__dict__:
                    raise DTOListFieldConfigException(
                        f"PK field not found in DTO: {self._dto_class}"
                    )

                # Recuperando o ID da entidade detalhe
                related_id = getattr(related_dto, list_field.dto_type.pk_field)

                # Chamando a exclusão recursivamente
                service._delete(
                    related_id,
                    manage_transaction=False,
                    additional_filters=additional_filters,
                )

    def _retrieve_left_join_fields(
        self,
        dto_list: List[DTOBase],
        fields: Dict[str, Set[str]],
        partition_fields: Dict[str, Any],
    ):
        # Tratando cada dto recebido
        for dto in dto_list:
            # Tratando cada tipo de entidade relacionada
            left_join_fields_map_to_query = getattr(
                dto.__class__, "left_join_fields_map_to_query", {}
            )
            for left_join_query_key in left_join_fields_map_to_query:
                left_join_query: LeftJoinQuery = left_join_fields_map_to_query[
                    left_join_query_key
                ]

                # Verificando os fields de interesse
                fields_necessarios = set()
                for field in left_join_query.fields:
                    if field in fields["root"]:
                        fields_necessarios.add(field)

                # Se nenhum dos fields registrados for pedido, ignora esse relacioanemtno
                if len(fields_necessarios) <= 0:
                    continue

                # Getting related service instance
                # TODO Refatorar para suportar services customizados
                service = ServiceBase(
                    self._injector_factory,
                    DAOBase(
                        self._injector_factory.db_adapter(),
                        left_join_query.related_entity,
                    ),
                    left_join_query.related_dto,
                    left_join_query.related_entity,
                )

                # Montando a lista de campos a serem recuperados na entidade relacionada
                related_fields = set()
                for left_join_field in left_join_query.left_join_fields:
                    # Ignorando os campos que não estejam no retorno da query
                    if left_join_field.name not in fields_necessarios:
                        continue

                    related_fields.add(left_join_field.related_dto_field)

                related_fields = {"root": related_fields}

                # Verificando quem é o dono do relacionamento, e recuperando o DTO relcaionado
                # da forma correspondente
                related_dto = None
                if left_join_query.entity_relation_owner == EntityRelationOwner.OTHER:
                    # Checking if pk_field exists
                    if self._dto_class.pk_field is None:
                        raise DTOListFieldConfigException(
                            f"PK field not found in class: {self._dto_class}"
                        )

                    # Montando os filtros para recuperar o objeto relacionado
                    related_filters = {
                        left_join_query.left_join_fields[0].relation_field: getattr(
                            dto, self._dto_class.pk_field
                        )
                    }

                    # Recuperando a lista de DTOs relacionados (com um único elemento; limit=1)
                    related_dto = service.list(
                        None,
                        1,
                        related_fields,
                        None,
                        related_filters,
                    )
                    if len(related_dto) > 0:
                        related_dto = related_dto[0]
                    else:
                        related_dto = None

                elif left_join_query.entity_relation_owner == EntityRelationOwner.SELF:
                    # Checking if pk_field exists
                    if getattr(left_join_query.related_dto, "pk_field") is None:
                        raise DTOListFieldConfigException(
                            f"PK field not found in class: {left_join_query.related_dto}"
                        )

                    # Recuperando a PK da entidade relacionada
                    related_pk = getattr(
                        dto, left_join_query.left_join_fields[0].relation_field
                    )

                    if related_pk is None:
                        continue

                    # Recuperando o DTO relacionado
                    related_dto = service.get(
                        related_pk, partition_fields, related_fields
                    )
                else:
                    raise Exception(
                        f"Tipo de relacionamento (left join) não identificado: {left_join_query.entity_relation_owner}."
                    )

                # Copiando os campos necessários
                for field in fields_necessarios:
                    # Recuperando a configuração do campo left join
                    left_join_field: DTOLeftJoinField = dto.left_join_fields_map[field]

                    if related_dto is not None:
                        # Recuperando o valor da propriedade no DTO relacionado
                        field_value = getattr(
                            related_dto, left_join_field.related_dto_field
                        )

                        # Gravando o valor no DTO de interesse
                        setattr(dto, field, field_value)

    def _retrieve_object_fields(
        self,
        dto_list: List[DTOBase],
        fields: Dict[str, Set[str]],
        partition_fields: Dict[str, Any],
    ):
        # Tratando cada dto recebido
        for dto in dto_list:
            for key in dto.object_fields_map:
                # Verificando se o campo está no retorno
                if key not in fields["root"]:
                    continue

                object_field: DTOObjectField = dto.object_fields_map[key]

                if object_field.entity_type is None:
                    continue

                service = ServiceBase(
                    self._injector_factory,
                    DAOBase(
                        self._injector_factory.db_adapter(),
                        object_field.entity_type,
                    ),
                    object_field.expected_type,
                    object_field.entity_type,
                )

                if object_field.entity_relation_owner == EntityRelationOwner.OTHER:
                    # Checking if pk_field exists
                    if self._dto_class.pk_field is None:
                        raise DTOListFieldConfigException(
                            f"PK field not found in class: {self._dto_class}"
                        )

                    # Montando os filtros para recuperar o objeto relacionado
                    related_filters = {
                        object_field.relation_field: getattr(
                            dto, self._dto_class.pk_field
                        )
                    }

                    # Recuperando a lista de DTOs relacionados (com um único elemento; limit=1)
                    related_dto = service.list(
                        None,
                        1,
                        {"root": fields[key]} if key in fields else None,
                        None,
                        related_filters,
                    )
                    if len(related_dto) > 0:
                        field = related_dto[0]
                    else:
                        field = None

                    setattr(dto, key, field)

                elif object_field.entity_relation_owner == EntityRelationOwner.SELF:
                    if getattr(dto, object_field.relation_field) is not None:
                        try:
                            field = service.get(
                                getattr(dto, object_field.relation_field),
                                partition_fields,
                                {"root": fields[key]} if key in fields else None,
                            )
                        except NotFoundException:
                            field = None

                        setattr(dto, key, field)
