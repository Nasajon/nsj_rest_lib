from typing import Any, Dict, List

from nsj_rest_lib.dao.dao_base import DAOBase
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.filter import Filter
from nsj_rest_lib.exception import DTOListFieldConfigException
from nsj_rest_lib.descriptor.filter_operator import FilterOperator

from .service_base_partial_of import ServiceBasePartialOf


class ServiceBaseDelete(ServiceBasePartialOf):

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
        _returns = {}
        for _id in ids:
            try:
                self._delete(
                    _id, manage_transaction=True, additional_filters=additional_filters
                )
            except Exception as e:
                _returns[_id] = e

        return _returns

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

            # Resolve o campo de chave sendo utilizado
            entity_key_field, entity_id_value = self._resolve_field_key(
                id,
                additional_filters,
            )

            # Adicionando o ID nos filtros
            id_condiction = Filter(FilterOperator.EQUALS, entity_id_value)

            entity_filters[entity_key_field] = [id_condiction]

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

    def _delete_list(
        self,
        ids: List[str],
        manage_transaction: bool,
        additional_filters: Dict[str, Any] = None,
        custom_before_delete=None,
    ) -> DTOBase:

        if not ids:
            return

        try:
            if manage_transaction:
                self._dao.begin()

            # Convertendo os filtros para os filtros de entidade
            entity_filters = {}
            if additional_filters is not None:
                entity_filters = self._create_entity_filters(additional_filters)

            entity_id_values = []
            for _id in ids:
                # Função para validar ou fazer outras consultas antes de deletar
                if custom_before_delete is not None:
                    dto = self.get(_id, additional_filters, None)
                    custom_before_delete(self._dao._db, dto)

                # Resolve o campo de chave sendo utilizado
                entity_key_field, entity_id_value = self._resolve_field_key(
                    _id,
                    additional_filters,
                )

                entity_id_values.append(entity_id_value)

                # Tratando das propriedades de lista
                if len(self._dto_class.list_fields_map) > 0:
                    self._delete_related_lists(_id, additional_filters)

            # Adicionando o ID nos filtros
            id_condiction = Filter(FilterOperator.IN, entity_id_values)

            entity_filters[entity_key_field] = [id_condiction]

            # Excluindo os conjuntos (se necessário)
            if self._dto_class.conjunto_type is not None:
                self._dao.delete_relacionamentos_conjunto(
                    ids, self._dto_class.conjunto_type
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

    def _delete_related_lists_old(self, id, additional_filters: Dict[str, Any] = None):
        # Handling each related list
        from .service_base import ServiceBase

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

    def _delete_related_lists(self, id, additional_filters: Dict[str, Any] = None):
        # Handling each related list
        from .service_base import ServiceBase

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
            related_ids = []
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
                related_ids.append(getattr(related_dto, list_field.dto_type.pk_field))

            # Chamando a exclusão
            service._delete_list(
                related_ids,
                manage_transaction=False,
                additional_filters=additional_filters,
            )
