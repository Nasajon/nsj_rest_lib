import re
import uuid
import typing as ty

from typing import Any, Dict, List, Set

from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.util.fields_util import FieldsTree
from nsj_rest_lib.util.log_time import log_time_context
from nsj_rest_lib.util.order_spec import (
    OrderFieldSpec,
    OrderFieldSource,
)

from .service_base_retrieve import ServiceBaseRetrieve


class ServiceBaseList(ServiceBaseRetrieve):

    def filter_list(self, filters: Dict[str, Any]):
        return self.list(
            None,
            None,
            {"root": set()},
            None,
            filters,
        )

    def list(
        self,
        after: uuid.UUID,
        limit: int,
        fields: FieldsTree,
        order_fields: List[str],
        filters: Dict[str, Any],
        search_query: str = None,
        return_hidden_fields: set[str] = None,
        expands: ty.Optional[FieldsTree] = None,
    ) -> List[DTOBase]:
        # Resolving fields
        fields = self._resolving_fields(fields)

        has_partial = self._has_partial_support()
        partial_config = getattr(self._dto_class, "partial_dto_config", None)

        base_root_fields: Set[str] = set(fields["root"])
        partial_root_fields: Set[str] = set()
        partial_join_fields_entity: Set[str] = set()
        extension_entity_fields: Set[str] = set()

        if has_partial and partial_config is not None:
            base_root_fields, partial_root_fields = self._split_partial_fields(
                fields["root"]
            )
            partial_join_fields_entity |= self._convert_partial_fields_to_entity(
                partial_root_fields
            )
            extension_entity_fields = self._convert_partial_fields_to_entity(
                partial_config.extension_fields
            )

        base_hidden_fields = None
        if return_hidden_fields is not None:
            hidden_base_candidates = set(return_hidden_fields)
            if has_partial and extension_entity_fields:
                partial_hidden_fields = {
                    field
                    for field in hidden_base_candidates
                    if field in extension_entity_fields
                }
                if partial_hidden_fields:
                    partial_join_fields_entity |= partial_hidden_fields
                hidden_base_candidates -= partial_hidden_fields

            base_hidden_fields = (
                hidden_base_candidates if len(hidden_base_candidates) > 0 else None
            )

        if expands is None:
            expands = {"root": set()}

        entity_fields = self._convert_to_entity_fields(
            base_root_fields, return_hidden_fields=base_hidden_fields
        )

        # Handling order fields
        order_field_specs: List[OrderFieldSpec] | None = None
        if order_fields is not None:
            order_field_specs = []
            for field in order_fields:
                aux = re.sub(
                    r"\basc\b|\bdesc\b", "", field, flags=re.IGNORECASE
                ).strip()
                is_desc = bool(re.search(r"\bdesc\b", field, flags=re.IGNORECASE))

                entity_field_name = self._convert_to_entity_field(aux)
                source = OrderFieldSource.BASE

                if (
                    has_partial
                    and partial_config is not None
                    and aux in partial_config.extension_fields
                ):
                    source = OrderFieldSource.PARTIAL_EXTENSION
                    partial_join_fields_entity.add(entity_field_name)

                order_field_specs.append(
                    OrderFieldSpec(
                        column=entity_field_name,
                        is_desc=is_desc,
                        source=source,
                        alias=None,
                    )
                )

        # Tratando dos filtros
        all_filters = {}
        if self._dto_class.fixed_filters is not None:
            all_filters.update(self._dto_class.fixed_filters)
        if filters is not None:
            all_filters.update(filters)

        ## Adicionando os filtros para override de dados
        self._add_overide_data_filters(all_filters)

        entity_filters = self._create_entity_filters(all_filters)

        # Tratando dos campos a serem enviados ao DAO para uso do search (se necessário)
        search_fields = None
        if self._dto_class.search_fields is not None:
            base_search_fields, _ = self._split_partial_fields(
                self._dto_class.search_fields
            )
            if base_search_fields:
                search_fields = self._convert_to_entity_fields(base_search_fields)

        # Resolve o campo de chave sendo utilizado
        entity_key_field, entity_id_value = (None, None)
        if after is not None:
            entity_key_field, entity_id_value = self._resolve_field_key(
                after,
                filters,
            )

        # Resolvendo os joins
        joins_aux = self._resolve_sql_join_fields(
            fields["root"], entity_filters, partial_join_fields_entity
        )

        partial_exists_clause = self._build_partial_exists_clause(joins_aux)

        # Retrieving from DAO
        entity_list = self._dao.list(
            after,
            limit,
            entity_fields,
            order_field_specs,
            entity_filters,
            conjunto_type=self._dto_class.conjunto_type,
            conjunto_field=self._dto_class.conjunto_field,
            entity_key_field=entity_key_field,
            entity_id_value=entity_id_value,
            search_query=search_query,
            search_fields=search_fields,
            joins_aux=joins_aux,
            partial_exists_clause=partial_exists_clause,
        )

        agg_field_map: ty.Dict[str, DTOAggregator] = {
            k: v
            for k, v in self._dto_class.aggregator_fields_map.items()
            if k in fields["root"]
        }

        # NOTE: This has to be done before it's converted to DTO, because after
        #           the `setattr` in this function WILL not work.
        if len(self._dto_class.one_to_one_fields_map) > 0:
            self._retrieve_one_to_one_fields(
                entity_list,
                fields,
                expands,
                filters,
            )

        # Convertendo para uma lista de DTOs
        with log_time_context(
            f"Convertendo entities para lista de DTOs {self._dto_class}"
        ):
            dto_list = []
            for entity in entity_list:
                with log_time_context(f"Convertendo um único DTO"):
                    dto = self._dto_class(entity, escape_validator=True)  # type: ignore

                    # FIXME GAMBIARRA! A ideia aqui foi recuperar propriedades diretamente da Entity
                    # para o DTO, pois os PropertiesDescriptors de Relacionamento estavam usando, erradamente,
                    # o nome da Entity, e não do DTO.
                    # A solução retrocompatível foi levar essas informações para o DTO.
                    # Próximo passo é criar novos descritores e depreciar os antigos.
                    result_hf: dict[str, any] = {}
                    if return_hidden_fields:
                        for hf in return_hidden_fields:
                            value = getattr(entity, hf)
                            result_hf[hf] = value
                    setattr(dto, "return_hidden_fields", result_hf)

                for k, v in agg_field_map.items():
                    setattr(dto, k, v.expected_type(entity, escape_validator=True))
                    pass
                dto_list.append(dto)
                pass

        # Agrupando o resultado, de acordo com o override de dados
        dto_list = self._group_by_override_data(dto_list)

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
