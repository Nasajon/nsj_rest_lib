import uuid
import copy

from typing import Any, Callable, Dict, List, Set, Tuple

from flask import g

from nsj_rest_lib.dao.dao_base import DAOBase
from nsj_rest_lib.descriptor.dto_field import DTOFieldFilter
from nsj_rest_lib.descriptor.filter_operator import FilterOperator
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.entity.filter import Filter
from nsj_rest_lib.exception import (
    DTOListFieldConfigException,
    ConflictException,
    NotFoundException,
)
from nsj_rest_lib.injector_factory_base import NsjInjectorFactoryBase
from nsj_rest_lib.validator.validate_data import validate_uuid


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

    def get(
        self,
        id: str,
        partition_fields: Dict[str, Any],
        fields: Dict[str, List[str]],
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

        # Recuperando a entity
        entity = self._dao.get(
            entity_key_field,
            entity_id_value,
            entity_fields,
            entity_filters,
            conjunto_type=self._dto_class.conjunto_type,
            conjunto_field=self._dto_class.conjunto_field,
        )

        # Convertendo para DTO
        dto = self._dto_class(entity, escape_validator=True)

        # Tratando das propriedades de lista
        if len(self._dto_class.list_fields_map) > 0:
            self._retrieve_related_lists([dto], fields)

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

    def _convert_to_entity_fields(self, fields: Set[str]) -> List[str]:
        """
        Convert a list of fields names to a list of entity fiedls names.
        """

        if fields is None:
            return None

        # TODO Refatorar para não precisar deste objeto só por conta das propriedades da classe
        # (um decorator na classe, poderia armazenar os fields na mesma, como é feito no DTO)
        entity = self._entity_class()

        entity_fields = []
        for field in fields:
            # Skipping not DTO fields
            if not (field in self._dto_class.fields_map):
                continue

            entity_field_name = self._convert_to_entity_field(field)
            # Skipping not Entity fields
            if not (entity_field_name in entity.__dict__):
                continue

            entity_fields.append(entity_field_name)

        return entity_fields

    def _convert_to_entity_field(self, field: str) -> str:
        """
        Convert a field name to a entity field name.
        """

        entity_field_name = field
        if self._dto_class.fields_map[field].entity_field is not None:
            entity_field_name = self._dto_class.fields_map[field].entity_field

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

        entity_filters = {}
        for filter in filters:
            is_entity_filter = False
            is_conjunto_filter = False
            dto_field = None

            if filter in self._dto_class.field_filters_map:
                # Retrieving filter config
                field_filter = self._dto_class.field_filters_map[filter]
                aux = self._dto_class.field_filters_map[filter].field_name
                dto_field = self._dto_class.fields_map[aux]
            elif filter == self._dto_class.conjunto_field:
                is_conjunto_filter = True
                dto_field = self._dto_class.fields_map[self._dto_class.conjunto_field]
            elif filter in self._dto_class.fields_map:
                # Creating filter config to a DTOField (equals operator)
                field_filter = DTOFieldFilter(filter)
                field_filter.set_field_name(filter)
                dto_field = self._dto_class.fields_map[filter]
            # TODO Refatorar para usar um mapa de fields do entity
            elif filter in self._entity_class().__dict__:
                is_entity_filter = True
            else:
                # Ignoring not declared filters (or filter for not existent DTOField)
                continue

            # Resolving entity field name (to filter)
            if not is_entity_filter and not is_conjunto_filter:
                entity_field_name = self._convert_to_entity_field(
                    field_filter.field_name
                )
            else:
                entity_field_name = filter

            # Creating entity filters (one for each value - separated by comma)
            if isinstance(filters[filter], str):
                values = filters[filter].split(",")
            else:
                values = [filters[filter]]

            for value in values:
                if isinstance(value, str):
                    value = value.strip()

                # Convertendo os valores para o formato esperado no entity
                if not is_entity_filter:
                    converted_values = self._dto_class.custom_convert_value_to_entity(
                        value,
                        dto_field,
                        entity_field_name,
                        False,
                        filters,
                    )
                    if len(converted_values) <= 0:
                        value = self._dto_class.convert_value_to_entity(
                            value,
                            dto_field,
                            False,
                            self._entity_class,
                        )
                        converted_values = {entity_field_name: value}
                else:
                    converted_values = {entity_field_name: value}

                # Tratando cada valor convertido
                for entity_field in converted_values:
                    converted_value = converted_values[entity_field]

                    if not is_entity_filter and not is_conjunto_filter:
                        entity_filter = Filter(field_filter.operator, converted_value)
                    else:
                        entity_filter = Filter(FilterOperator.EQUALS, converted_value)

                    # Storing filter in dict
                    filter_list = entity_filters.setdefault(entity_field, [])
                    filter_list.append(entity_filter)

        return entity_filters

    def _resolving_fields(self, fields: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        """
        Varifica os fields recebidos, garantindo que os campos de resumo serão considerados.
        """

        # Resolving fields
        if fields is None:
            result = {"root": set()}
        else:
            result = copy.deepcopy(fields)
            result["root"] = result["root"].union(self._dto_class.resume_fields)

        return result

    def list(
        self,
        after: uuid.UUID,
        limit: int,
        fields: Dict[str, Set[str]],
        order_fields: List[str],
        filters: Dict[str, Any],
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

        # Retrieving from DAO
        entity_list = self._dao.list(
            after,
            limit,
            entity_fields,
            order_fields,
            entity_filters,
            conjunto_type=self._dto_class.conjunto_type,
            conjunto_field=self._dto_class.conjunto_field,
        )

        # Convertendo para uma lista de DTOs
        dto_list = [
            self._dto_class(entity, escape_validator=True) for entity in entity_list
        ]

        # Retrieving related lists
        if len(self._dto_class.list_fields_map) > 0:
            self._retrieve_related_lists(dto_list, fields)

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
                    # TODO Refatorar para suportar services customizados
                    service = ServiceBase(
                        self._injector_factory,
                        DAOBase(
                            self._injector_factory.db_adapter(), list_field.entity_type
                        ),
                        list_field.dto_type,
                        list_field.entity_type,
                    )

                    # Checking if pk_field exists
                    if self._dto_class.pk_field is None:
                        raise DTOListFieldConfigException(
                            f"PK field not found in class: {self._dto_class}"
                        )

                    if not (self._dto_class.pk_field in dto.__dict__):
                        raise DTOListFieldConfigException(
                            f"PK field not found in DTO: {self._dto_class}"
                        )

                    # Making filter to relation
                    filters = {
                        # TODO Adicionar os campos de particionamento de dados
                        list_field.related_entity_field: getattr(
                            dto, self._dto_class.pk_field
                        )
                    }

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
        custom_after_insert: Callable = None,
        custom_after_update: Callable = None,
    ) -> DTOBase:
        return self._save(
            insert=True,
            dto=dto,
            manage_transaction=True,
            partial_update=False,
            aditional_filters=aditional_filters,
            custom_after_insert=custom_after_insert,
            custom_after_update=custom_after_update,
        )

    def update(
        self,
        dto: DTOBase,
        id: Any,
        aditional_filters: Dict[str, Any] = None,
        custom_after_insert: Callable = None,
        custom_after_update: Callable = None,
    ) -> DTOBase:
        return self._save(
            insert=False,
            dto=dto,
            manage_transaction=True,
            partial_update=False,
            id=id,
            aditional_filters=aditional_filters,
            custom_after_insert=custom_after_insert,
            custom_after_update=custom_after_update,
        )

    def partial_update(
        self, dto: DTOBase, id: Any, aditional_filters: Dict[str, Any] = None
    ) -> DTOBase:
        return self._save(
            insert=False,
            dto=dto,
            manage_transaction=True,
            partial_update=True,
            id=id,
            aditional_filters=aditional_filters,
        )

    def _make_fields_from_dto(self, dto: DTOBase, root_name: str = "root"):
        # Adicionando os campos normais do DTO
        fields = {root_name: set()}
        for field in self._dto_class.fields_map:
            if field in dto.__dict__ or self._dto_class.fields_map[field].pk:
                fields[root_name].add(field)

        # Adicionando os campos de lista, contidos no DTO
        for list_field in self._dto_class.list_fields_map:
            if field in dto.__dict__:
                list_dto = getattr(dto, list_field)
                if len(list_dto) < 0:
                    continue

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
        custom_after_insert: Callable = None,
        custom_after_update: Callable = None,
    ) -> DTOBase:
        try:
            if manage_transaction:
                self._dao.begin()

            # Recuperando o DTO antes da gravação (apenas se for update, e houver um custom_after_update)
            if not insert and custom_after_update is not None:
                old_dto = self._retrieve_old_dto(dto, id, aditional_filters)

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

            # Resolve o campo de chave sendo utilizado
            entity_key_field, entity_id_value = self._resolve_field_key(
                id,
                dto.__dict__,
            )

            # Validando as uniques declaradas
            for unique in self._dto_class.uniques:
                unique = self._dto_class.uniques[unique]
                self._check_unique(
                    dto,
                    entity,
                    aditional_entity_filters,
                    unique,
                    entity_key_field,
                    entity_id_value,
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
                entity = self._dao.insert(entity)

                # Inserindo os conjuntos (se necessário)
                if self._dto_class.conjunto_type is not None:
                    conjunto_field_value = getattr(dto, self._dto_class.conjunto_field)

                    self._dao.insert_relacionamento_conjunto(
                        id, conjunto_field_value, self._dto_class.conjunto_type
                    )
            else:
                # Executando o update pelo DAO
                entity = self._dao.update(
                    entity_key_field,
                    entity_id_value,
                    entity,
                    aditional_entity_filters,
                    partial_update,
                )

            # Convertendo a entity para o DTO de resposta (se houver um)
            if self._dto_post_response_class is not None:
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

                # Adicionando campo de conjunto
                if (
                    self._dto_class.conjunto_field is not None
                    and getattr(new_dto, self._dto_class.conjunto_field) is None
                ):
                    value_conjunto = getattr(dto, self._dto_class.conjunto_field)
                    setattr(new_dto, self._dto_class.conjunto_field, value_conjunto)

            if insert:
                if custom_after_insert is not None:
                    custom_after_insert(self._dao._db, new_dto)
            else:
                if custom_after_update is not None:
                    custom_after_update(self._dao._db, old_dto, new_dto)

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
            # TODO Refatorar para suportar services customizados
            detail_service = ServiceBase(
                self._injector_factory,
                detail_dao,
                list_field.dto_type,
                list_field.entity_type,
                list_field.dto_post_response_type,
            )

            # Recuperando o valor da PK da entidade principal
            entity_pk_field = entity.get_pk_field()
            pk_value = getattr(entity, entity_pk_field)

            # Montando um mapa com os campos de relacionamento (para gravar nas entidades relacionadas)
            relation_field_map = {
                list_field.related_entity_field: pk_value,
            }

            # Recuperando todos os IDs dos itens de lista já salvos no BD (se for um update)
            old_detail_ids = None
            if not insert:
                # Montando o filtro para recuperar os objetos detalhe pré-existentes
                relation_condiction = Filter(FilterOperator.EQUALS, pk_value)

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

                if not (self._dto_class.pk_field in dto.__dict__):
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

    def delete(self, id: Any, additional_filters: Dict[str, Any] = None) -> DTOBase:
        self._delete(id, manage_transaction=True, additional_filters=additional_filters)

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
        except NotFoundException as e:
            return False

        return True

    def _check_unique(
        self,
        dto: DTOBase,
        entity: EntityBase,
        entity_filters: Dict[str, List[Filter]],
        unique: Set[str],
        entity_key_field: str,
        entity_key_value: Any = None,
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
        if entity_key_field in unique_entity_filters:
            del unique_entity_filters[entity_key_field]

        # Se não há mais campos na unique, não há o que validar
        if len(unique_entity_filters) <= 0:
            return

        # Montando o entity filter final
        entity_filters = {**entity_filters, **unique_entity_filters}

        # Montando filtro de PK diferente (se necessário, isto é, se for update)
        if entity_key_value is not None:
            filters_pk = entity_filters.setdefault(entity_key_field, [])
            filters_pk.append(Filter(FilterOperator.DIFFERENT, entity_key_value))

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
    ) -> DTOBase:
        try:
            if manage_transaction:
                self._dao.begin()

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

            # Excluindo a entity principal
            self._dao.delete(entity_filters)

            # Excluindo os conjuntos (se necessário)
            if self._dto_class.conjunto_type is not None:
                self._dao.delete_relacionamento_conjunto(
                    id, self._dto_class.conjunto_type
                )

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
            # TODO Refatorar para suportar services customizados
            service = ServiceBase(
                self._injector_factory,
                DAOBase(self._injector_factory.db_adapter(), list_field.entity_type),
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

                if not (list_field.dto_type.pk_field in related_dto.__dict__):
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
