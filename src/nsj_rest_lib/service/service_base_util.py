import copy
import uuid
import typing as ty

from typing import Any, Dict, List, Set, Tuple

from nsj_rest_lib.descriptor.dto_field import DTOFieldFilter
from nsj_rest_lib.descriptor.filter_operator import FilterOperator
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.entity.filter import Filter
from nsj_rest_lib.exception import NotFoundException
from nsj_rest_lib.util.fields_util import FieldsTree
from nsj_rest_lib.util.type_validator_util import TypeValidatorUtil
from nsj_rest_lib.validator.validate_data import validate_uuid


class ServiceBaseUtil:

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
            elif candidate_key_field.expected_type in [int] and isinstance(
                id_value, str
            ):
                id_value = candidate_key_field.expected_type(id_value)
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
        return_hidden_fields: set[str] = None,
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

        acceptable_fields: ty.Set[str] = {
            self._convert_to_entity_field(k, dto_class)
            for k, _ in dto_class.fields_map.items()
            if k in fields
        }
        for v in dto_class.aggregator_fields_map.values():
            acceptable_fields.update(
                {
                    self._convert_to_entity_field(k1, v.expected_type)
                    for k1, v1 in v.expected_type.fields_map.items()
                    if k1 in fields
                }
            )
            pass

        # Adding hidden fields
        if return_hidden_fields is not None:
            acceptable_fields |= return_hidden_fields

        # Removing all the fields not in the entity
        acceptable_fields &= set(entity.__dict__)

        return list(acceptable_fields)

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
        partial_config = getattr(self._dto_class, "partial_dto_config", None)
        partial_join_alias = (
            self._get_partial_join_alias() if partial_config is not None else None
        )

        # Iterando enquanto houver filtros recebidos, ou derivalos a partir dos filter_aliases
        while len(aux_filters) > 0:
            new_filters = {}

            for filter in aux_filters:
                is_entity_filter = False
                is_conjunto_filter = False
                is_sql_join_filter = False
                is_length_filter = False
                dto_field = None
                dto_sql_join_field = None
                table_alias = None
                is_partial_extension_field = False

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
                    if (
                        partial_config is not None
                        and getattr(dto_field, "name", aux)
                        in partial_config.extension_fields
                    ):
                        is_partial_extension_field = True
                    is_length_filter = field_filter.operator in [
                        FilterOperator.LENGTH_GREATER_OR_EQUAL_THAN,
                        FilterOperator.LENGTH_LESS_OR_EQUAL_THAN,
                    ]

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
                    if (
                        partial_config is not None
                        and getattr(dto_field, "name", filter)
                        in partial_config.extension_fields
                    ):
                        is_partial_extension_field = True

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
                    if (
                        not is_entity_filter
                        and not is_sql_join_filter
                        and not is_length_filter
                    ):
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
                            alias = None
                            if is_partial_extension_field:
                                alias = partial_join_alias
                                if entity_field != entity_field_name:
                                    alias = None
                            entity_filter = Filter(
                                field_filter.operator, converted_value, alias
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










    def _make_fields_from_dto(self, dto: DTOBase) -> FieldsTree:
        fields_tree: FieldsTree = {"root": set()}

        for field in dto.fields_map:
            if field in dto.__dict__:
                fields_tree["root"].add(field)

        for list_field in dto.list_fields_map:
            if list_field not in dto.__dict__:
                continue

            list_dto = getattr(dto, list_field)
            if not list_dto:
                continue

            fields_tree["root"].add(list_field)
            fields_tree[list_field] = self._make_fields_from_dto(list_dto[0])

        return fields_tree

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
