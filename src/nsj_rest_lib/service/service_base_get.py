import typing as ty

from typing import Any, Dict

from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.exception import ConflictException
from nsj_rest_lib.util.fields_util import FieldsTree

from .service_base_retrieve import ServiceBaseRetrieve


class ServiceBaseGet(ServiceBaseRetrieve):

    def get(
        self,
        id: str,
        partition_fields: Dict[str, Any],
        fields: FieldsTree,
        expands: ty.Optional[FieldsTree] = None,
        function_params: Dict[str, Any] | None = None,
        function_object=None,
    ) -> DTOBase:

        if expands is None:
            expands = {"root": set()}

        if (
            getattr(self, "_get_function_type_class", None) is not None
            or getattr(self, "_get_function_name", None) is not None
            or function_object is not None
        ):
            return self._get_by_function(
                id,
                partition_fields,
                fields,
                expands,
                function_params or {},
                function_object,
            )

        # Resolving fields
        fields = self._resolving_fields(fields)

        if self._has_partial_support():
            base_root_fields, partial_root_fields = self._split_partial_fields(
                fields["root"]
            )
        else:
            base_root_fields = set(fields["root"])
            partial_root_fields = set()

        # Handling the fields to retrieve
        entity_fields = self._convert_to_entity_fields(base_root_fields)
        partial_join_fields = self._convert_partial_fields_to_entity(
            partial_root_fields
        )

        # Tratando dos filtros
        all_filters = {}
        if self._dto_class.fixed_filters is not None:
            all_filters.update(self._dto_class.fixed_filters)
        if partition_fields is not None:
            all_filters.update(partition_fields)

        ## Adicionando os filtros para override de dados
        self._add_overide_data_filters(all_filters)

        entity_filters = self._create_entity_filters(all_filters)

        # Resolve o campo de chave sendo utilizado
        entity_key_field, entity_id_value = self._resolve_field_key(
            id,
            partition_fields,
        )

        # Resolvendo os joins
        joins_aux = self._resolve_sql_join_fields(
            fields["root"], entity_filters, partial_join_fields
        )

        partial_exists_clause = self._build_partial_exists_clause(joins_aux)

        # Recuperando a entity
        override_data = (
            self._dto_class.data_override_group is not None
            and self._dto_class.data_override_fields is not None
        )
        entity = self._dao.get(
            entity_key_field,
            entity_id_value,
            entity_fields,
            entity_filters,
            conjunto_type=self._dto_class.conjunto_type,
            conjunto_field=self._dto_class.conjunto_field,
            joins_aux=joins_aux,
            partial_exists_clause=partial_exists_clause,
            override_data=override_data,
        )

        # NOTE: This has to happens on the entity
        if len(self._dto_class.one_to_one_fields_map) > 0:
            self._retrieve_one_to_one_fields(
                [entity],
                fields,
                expands,
                partition_fields,
            )

        # NOTE: This has to be done first so the DTOAggregator can have
        #           the same name as a field in the entity
        for k, v in self._dto_class.aggregator_fields_map.items():
            if k not in fields["root"]:
                continue
            setattr(entity, k, v.expected_type(entity, escape_validator=True))
            pass

        # Convertendo para DTO
        if not override_data:
            dto = self._dto_class(entity, escape_validator=True)
        else:
            # Convertendo para uma lista de DTOs
            dto_list = [self._dto_class(e, escape_validator=True) for e in entity]

            # Agrupando o resultado, de acordo com o override de dados
            dto_list = self._group_by_override_data(dto_list)

            if len(dto_list) > 1:
                raise ConflictException(
                    f"Encontrado mais de um registro do tipo {self._entity_class.__name__}, para o id {id}."
                )

            dto = dto_list[0]

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

    def _get_by_function(
        self,
        id: str,
        partition_fields: Dict[str, Any],
        fields: FieldsTree,
        expands: FieldsTree,
        function_params: Dict[str, Any],
        function_object=None,
    ) -> DTOBase:
        from nsj_rest_lib.exception import NotFoundException

        all_params = {}
        if partition_fields:
            all_params.update(partition_fields)
        all_params.update(function_params or {})

        rows = []
        dto_class = getattr(self, "_get_function_response_dto_class", self._dto_class)

        if function_object is None and getattr(self, "_get_function_type_class", None) is not None:
            function_object = self._build_function_type_from_params(
                all_params,
                self._get_function_type_class,
                id_value=id,
            )
        if function_object is not None:
            rows = self._dao._call_function_with_type(
                function_object, self._get_function_name
            )
            dtos = self._map_function_rows_to_dtos(
                rows,
                dto_class,
                self._get_function_type_class,
            )
        else:
            positional_values = []
            if id is not None:
                positional_values.append(id)
            rows = self._dao._call_function_raw(
                self._get_function_name,
                positional_values,
                all_params,
            )
            dtos = self._map_function_rows_to_dtos(
                rows,
                dto_class,
                None,
                operation="get",
            )

        if not dtos:
            raise NotFoundException(
                f"{self._entity_class.__name__} com id {id} não encontrado."
            )

        dto = dtos[0]
        return dto
