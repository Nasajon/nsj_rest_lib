import copy
import typing as ty

from typing import Any, Callable, Dict, List, Set

from flask import g

from nsj_rest_lib.dao.dao_base import DAOBase
from nsj_rest_lib.dto.after_insert_update_data import AfterInsertUpdateData
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.entity.filter import Filter
from nsj_rest_lib.exception import (
    ConflictException,
    DTOListFieldConfigException,
)
from nsj_rest_lib.util.fields_util import FieldsTree

from .service_base_partial_of import ServiceBasePartialOf, PartialExtensionWriteData


class ServiceBaseInsert(ServiceBasePartialOf):

    def insert(
        self,
        dto: DTOBase,
        aditional_filters: Dict[str, Any] = None,
        custom_before_insert: Callable = None,
        custom_after_insert: Callable = None,
        retrieve_after_insert: bool = False,
        manage_transaction: bool = True,
    ) -> DTOBase:
        return self._save(
            insert=True,
            dto=dto,
            manage_transaction=manage_transaction,
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
        manage_transaction: bool = True,
    ) -> List[DTOBase]:
        _lst_return = []
        try:
            if manage_transaction:
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
            if manage_transaction:
                self._dao.rollback()
            raise
        finally:
            if manage_transaction:
                self._dao.commit()

        return _lst_return

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

            # Tratando dos campos de auto-incremento
            self.fill_auto_increment_fields(insert, dto)

            # Iniciando a transação de controle
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

            # Preparando entidades/base e metadados para extensão parcial (se houver)
            partial_write_data: PartialExtensionWriteData | None = None
            if self._has_partial_support():
                entity, partial_write_data = self._prepare_partial_save_entities(
                    dto,
                    partial_update,
                    insert,
                )
            else:
                # TODO Refatorar para usar um construtor do EntityBase (ou algo assim, porque é preciso tratar das equivalências de nome dos campos)
                entity = dto.convert_to_entity(
                    self._entity_class,
                    partial_update,
                    insert,
                )

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
                if g and hasattr(g, "profile") and g.profile is not None:
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

                # Persistindo dados da extensão parcial (se houver)
                if partial_write_data is not None:
                    self._handle_partial_extension_insert(entity, partial_write_data)

                # Inserindo os conjuntos (se necessário)
                if self._dto_class.conjunto_type is not None:
                    conjunto_field_value = getattr(dto, self._dto_class.conjunto_field)

                    aditional_filters[self._dto_class.conjunto_field] = (
                        conjunto_field_value
                    )

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
                    dto.sql_no_update_fields,
                    upsert,
                )

                if partial_write_data is not None:
                    self._handle_partial_extension_update(
                        entity,
                        partial_write_data,
                        partial_update,
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
            custom_data = None
            if insert:
                if custom_after_insert is not None:
                    custom_data = custom_after_insert(
                        self._dao._db, new_dto, after_data
                    )
            else:
                if custom_after_update is not None:
                    custom_data = custom_after_update(
                        self._dao._db, old_dto, new_dto, after_data
                    )

            if retrieve_after_insert:
                response_dto = self.get(id, aditional_filters, None)

            if custom_data is not None:
                if isinstance(custom_data, dict):
                    if response_dto is not None:
                        for key in custom_data:
                            setattr(response_dto, key, custom_data[key])
                    else:
                        response_dto = custom_data
                else:
                    if response_dto is not None:
                        # Ignora o retorno, e prevalece ou o DTO de resposta, ou o retrieve configurado
                        pass
                    else:
                        response_dto = custom_data

            # Retornando o DTO de resposta
            return response_dto

        except:
            if manage_transaction:
                self._dao.rollback()
            raise
        finally:
            if manage_transaction:
                self._dao.commit()

    def fill_auto_increment_fields(self, insert, dto):
        if insert:
            auto_increment_fields = getattr(self._dto_class, "auto_increment_fields")

            # Preenchendo os campos de auto-incremento
            for field_key in auto_increment_fields:
                # Recuperando o field em questão
                field = self._dto_class.fields_map[field_key]

                # Se já recebeu um valor, não altera
                if dto.__dict__.get(field.name, None):
                    continue

                # Se for um campo gerenciado pelo bamco de dados, apenas ignora
                if field.auto_increment.db_managed:
                    continue

                # Resolvendo os nomes dos campos de agrupamento, e adicionando os campos de particionamento sempre
                group_fields = set(field.auto_increment.group)
                for partition_field in dto.partition_fields:
                    if partition_field not in group_fields:
                        group_fields.add(partition_field)
                group_fields = list(group_fields)
                group_fields.sort()

                # Considerando os valores dos campos de agrupamento
                group_values = []
                for group_field in group_fields:
                    group_values.append(str(getattr(dto, group_field, "----")))

                # Descobrindo o próximo valor da sequencia
                next_value = self._dao.next_val(
                    sequence_base_name=field.auto_increment.sequence_name,
                    group_fields=group_values,
                    start_value=field.auto_increment.start_value,
                )

                # Tratando do template
                obj_values = {}
                for f in dto.fields_map:
                    obj_values[f] = getattr(dto, f)

                value = field.auto_increment.template.format(
                    **obj_values, seq=next_value
                )

                # Escrevendo o valor gerado no DTO
                if field.expected_type == int:
                    setattr(dto, field.name, int(value))
                else:
                    setattr(dto, field.name, value)

    def _retrieve_old_dto(self, dto, id, aditional_filters):
        fields = self._make_fields_from_dto(dto)
        get_filters = (
            copy.deepcopy(aditional_filters) if aditional_filters is not None else {}
        )

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

        from .service_base import ServiceBase

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
