import copy
import uuid
import typing as ty
import warnings

from typing import Any, Dict, List, Set, Tuple

from nsj_rest_lib.dao.dao_base import DAOBase
from nsj_rest_lib.descriptor import DTOOneToOneField
from nsj_rest_lib.descriptor.dto_field import DTOFieldFilter
from nsj_rest_lib.descriptor.dto_left_join_field import (
    DTOLeftJoinField,
    EntityRelationOwner,
    LeftJoinQuery,
)
from nsj_rest_lib.descriptor.dto_object_field import DTOObjectField
from nsj_rest_lib.descriptor.filter_operator import FilterOperator
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase, EMPTY
from nsj_rest_lib.entity.filter import Filter
from nsj_rest_lib.exception import (
    DTOListFieldConfigException,
    NotFoundException,
)
from nsj_rest_lib.settings import get_logger
from nsj_rest_lib.util.fields_util import (
    FieldsTree,
    clone_fields_tree,
    extract_child_tree,
    merge_fields_tree,
    normalize_fields_tree,
)
from nsj_rest_lib.util.join_aux import JoinAux
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

    def _resolving_fields(self, fields: FieldsTree) -> FieldsTree:
        """
        Verifica os fields recebidos, garantindo que os campos de resumo (incluindo os
        configurados nos relacionamentos) sejam considerados.
        """

        result = normalize_fields_tree(fields)
        merge_fields_tree(result, self._dto_class._build_default_fields_tree())

        # Tratamento especial para campos agregadores
        for field_name, descriptor in self._dto_class.aggregator_fields_map.items():
            if field_name not in result["root"]:
                continue

            result["root"] |= descriptor.expected_type.resume_fields

            if field_name not in result:
                continue

            child_tree = result.pop(field_name)
            if isinstance(child_tree, dict):
                result["root"] |= child_tree.get("root", set())

                for nested_field, nested_tree in child_tree.items():
                    if nested_field == "root":
                        continue

                    existing = result.get(nested_field)
                    if not isinstance(existing, dict):
                        result[nested_field] = clone_fields_tree(nested_tree)
                    else:
                        merge_fields_tree(existing, nested_tree)

        return result

    def _add_overide_data_filters(self, all_filters):
        if (
            self._dto_class.data_override_group is not None
            and self._dto_class.data_override_fields is not None
        ):
            for field in self._dto_class.data_override_fields:
                if field in self._dto_class.fields_map:
                    null_value = self._dto_class.fields_map[field].get_null_value()
                    if field in all_filters:
                        all_filters[field] = f"{all_filters[field]},{null_value}"
                    else:
                        all_filters[field] = f"{null_value}"

    def _group_by_override_data(self, dto_list):

        if (
            self._dto_class.data_override_group is not None
            and self._dto_class.data_override_fields is not None
        ):
            grouped_dto_list = {}
            reversed_data_override_fields = reversed(
                self._dto_class.data_override_fields
            )
            for dto in dto_list:
                ## Resolvendo o ID do grupo
                group_id = ""
                for field in self._dto_class.data_override_group:
                    if field in self._dto_class.fields_map:
                        group_id += f"{getattr(dto, field)}_"

                ## Guardando o DTO mais completo do grupo
                if group_id not in grouped_dto_list:
                    grouped_dto_list[group_id] = dto
                else:
                    ### Testa se o novo DTO é mais específico do que o já guardado, e o troca, caso positivo
                    last_dto_group = grouped_dto_list[group_id]
                    for field in reversed_data_override_fields:
                        if field in self._dto_class.fields_map:
                            dto_value = getattr(dto, field)
                            last_dto_value = getattr(last_dto_group, field)
                            null_value = self._dto_class.fields_map[
                                field
                            ].get_null_value()

                            if (
                                dto_value is not None
                                and null_value is not None
                                and dto_value != null_value
                                and (
                                    last_dto_value is None
                                    or last_dto_value == null_value
                                )
                            ):
                                grouped_dto_list[group_id] = dto

            ## Atualizando a lista de DTOs
            dto_list = list(grouped_dto_list.values())

        return dto_list

    def _retrieve_related_lists(self, dto_list: List[DTOBase], fields: FieldsTree):

        # TODO Controlar profundidade?!
        if not dto_list:
            return

        from .service_base import ServiceBase

        for master_dto_attr, list_field in self._dto_class.list_fields_map.items():
            if master_dto_attr not in fields["root"]:
                continue

            # Coletar todos os valores de chave relacionados dos DTOs
            relation_key_field = self._dto_class.pk_field
            if list_field.relation_key_field is not None:
                relation_key_field = list_field.relation_key_field

            # Mapeia valor da chave -> lista de DTOs que possuem esse valor
            key_to_dtos = {}
            for dto in dto_list:
                relation_filter_value = getattr(dto, relation_key_field, None)
                if relation_filter_value is not None:
                    key_to_dtos.setdefault(relation_filter_value, []).append(dto)
                else:
                    setattr(dto, master_dto_attr, [])

            if not key_to_dtos:
                continue

            # Instancia o service
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

            # Monta o filtro IN para buscar todos os relacionados de uma vez
            filters = {
                list_field.related_entity_field: ",".join(
                    [str(key) for key in key_to_dtos]
                )
            }

            # Campos de particionamento: se existirem, só faz sentido se todos os DTOs tiverem o mesmo valor
            # (caso contrário, teria que quebrar em vários queries)
            # Aqui, só trata se todos tiverem o mesmo valor para cada campo de partição
            for field in self._dto_class.partition_fields:
                if field in list_field.dto_type.partition_fields:
                    partition_values = set(
                        getattr(dto, field, None) for dto in dto_list
                    )
                    partition_values.discard(None)
                    if len(partition_values) == 1:
                        filters[field] = partition_values.pop()
                    # Se houver mais de um valor, teria que quebrar em vários queries (não tratado aqui)

            # Resolvendo os fields da entidade aninhada
            fields_to_list = extract_child_tree(fields, master_dto_attr)

            # Busca todos os relacionados de uma vez
            related_dto_list = service.list(
                None,
                None,
                fields_to_list,
                None,
                filters,
                return_hidden_fields=set([list_field.related_entity_field]),
            )

            # Agrupa os relacionados por chave
            related_map = {}
            for related_dto in related_dto_list:
                relation_key = str(
                    related_dto.return_hidden_fields.get(
                        list_field.related_entity_field, None
                    )
                )
                if relation_key is not None:
                    related_map.setdefault(relation_key, []).append(related_dto)

            # Seta nos DTOs principais
            for key, dtos in key_to_dtos.items():
                related = related_map.get(str(key), [])
                for dto in dtos:
                    setattr(dto, master_dto_attr, related)

    def _resolve_sql_join_fields(
        self,
        fields: Set[str],
        entity_filters: Dict[str, List[Filter]],
        partial_join_fields: Set[str] = None,
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

        partial_config = getattr(self._dto_class, "partial_dto_config", None)
        partial_entity_config = getattr(
            self._entity_class, "partial_entity_config", None
        )
        if partial_config is not None and partial_entity_config is not None:
            alias = self._get_partial_join_alias()
            join_fields_needed: Set[str] = set(partial_join_fields or set())
            join_required = len(join_fields_needed) > 0

            if entity_filters is not None and not join_required:
                for filter_list in entity_filters.values():
                    for condiction in filter_list:
                        if condiction.table_alias == alias:
                            join_required = True
                            break
                    if join_required:
                        break

            if join_required:
                join_aux = JoinAux()
                join_aux.table = partial_entity_config.extension_table_name
                join_aux.type = "inner"
                join_aux.alias = alias
                join_aux.fields = list(join_fields_needed) if join_fields_needed else []

                try:
                    join_aux.self_field = self._convert_to_entity_field(
                        partial_config.related_entity_field,
                        dto_class=partial_config.parent_dto,
                    )
                except KeyError:
                    join_aux.self_field = partial_config.related_entity_field

                join_aux.other_field = partial_config.relation_field

                joins_aux.append(join_aux)

        return joins_aux

    def _retrieve_left_join_fields(
        self,
        dto_list: List[DTOBase],
        fields: FieldsTree,
        partition_fields: Dict[str, Any],
    ):
        warnings.warn(
            "DTOLeftJoinField está depreciado e será removido em breve.",
            DeprecationWarning,
        )

        from .service_base import ServiceBase

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

    def _retrieve_object_fields_old(
        self,
        dto_list: List[DTOBase],
        fields: FieldsTree,
        partition_fields: Dict[str, Any],
    ):
        from .service_base import ServiceBase

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
                        extract_child_tree(fields, key),
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
                                extract_child_tree(fields, key),
                            )
                        except NotFoundException:
                            field = None

                        setattr(dto, key, field)

    def _retrieve_object_fields(
        self,
        dto_list: List[DTOBase],
        fields: FieldsTree,
        partition_fields: Dict[str, Any],
    ):
        """
        Versão otimizada do _retrieve_object_fields_keyson que faz buscas em lote
        ao invés de consultas individuais para cada DTO.
        """
        if not dto_list:
            return

        from .service_base import ServiceBase

        # Processando cada tipo de campo de objeto
        for key in self._dto_class.object_fields_map:
            # Verificando se o campo está no retorno
            if key not in fields["root"]:
                continue

            object_field: DTOObjectField = self._dto_class.object_fields_map[key]

            if object_field.entity_type is None:
                continue

            # Instanciando o service uma vez só para este tipo de campo
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

                # Coletando todas as chaves primárias dos DTOs para buscar de uma vez
                keys_to_fetch = set()
                for dto in dto_list:
                    pk_value = getattr(dto, self._dto_class.pk_field)
                    if pk_value is not None:
                        keys_to_fetch.add(pk_value)

                if not keys_to_fetch:
                    continue

                # Montando filtro para buscar todos os objetos relacionados de uma vez
                related_filters = {
                    object_field.relation_field: ",".join(str(k) for k in keys_to_fetch)
                }

                # Recuperando todos os DTOs relacionados de uma vez
                related_dto_list = service.list(
                    None,
                    None,
                    extract_child_tree(fields, key),
                    None,
                    related_filters,
                    return_hidden_fields=set([object_field.relation_field]),
                )

                # Criando mapa de chave -> DTO relacionado
                related_map = {}
                for related_dto in related_dto_list:
                    relation_key = str(
                        related_dto.return_hidden_fields.get(
                            object_field.relation_field, None
                        )
                    )
                    if relation_key is not None:
                        related_map[relation_key] = related_dto

                # Atribuindo os objetos relacionados nos DTOs originais
                for dto in dto_list:
                    pk_value = str(getattr(dto, self._dto_class.pk_field))
                    related_dto = related_map.get(pk_value)
                    setattr(dto, key, related_dto)

            elif object_field.entity_relation_owner == EntityRelationOwner.SELF:
                # FIXME A recuperação do nome do field do DTO só é necessária,
                # porque o relcionamento aponta para o nome da entity (isso deve ser mudado no futuro)
                dto_field_name = None
                for field, dto_field in self._dto_class.fields_map.items():
                    dto_entity_field_name = field
                    if dto_field.entity_field:
                        dto_entity_field_name = dto_field.entity_field

                    if object_field.relation_field == dto_entity_field_name:
                        dto_field_name = field
                        break

                if not dto_field_name:
                    get_logger().warning(
                        f"Campo de relacionamento do tipo DTOObjectField.SELF ({object_field.relation_field}) não encontrado do DTO: {self._dto_class}"
                    )
                    continue

                # Coletando todas as chaves de relacionamento para buscar de uma vez
                keys_to_fetch = set()
                for dto in dto_list:
                    relation_value = getattr(dto, dto_field_name)
                    if relation_value is not None:
                        keys_to_fetch.add(relation_value)

                if not keys_to_fetch:
                    continue

                # Montando filtro para buscar todos os objetos relacionados de uma vez
                related_filters = {
                    object_field.expected_type.pk_field: ",".join(
                        str(k) for k in keys_to_fetch
                    )
                }

                # Recuperando todos os DTOs relacionados de uma vez
                related_dto_list = service.list(
                    None,
                    None,
                    extract_child_tree(fields, key),
                    None,
                    related_filters,
                )

                # Criando mapa de chave -> DTO relacionado
                related_map = {}
                for related_dto in related_dto_list:
                    pk_field = getattr(related_dto.__class__, "pk_field")
                    pk_value = str(getattr(related_dto, pk_field))
                    if pk_value is not None:
                        related_map[pk_value] = related_dto

                # Atribuindo os objetos relacionados nos DTOs originais
                for dto in dto_list:
                    relation_value = str(getattr(dto, dto_field_name))
                    related_dto = related_map.get(relation_value)
                    setattr(dto, key, related_dto)

    def _retrieve_one_to_one_fields(
        self,
        dto_list: ty.List[ty.Union[DTOBase, EntityBase]],
        fields: ty.Dict[str, ty.Set[str]],
        expands: FieldsTree,
        partition_fields: ty.Dict[str, ty.Any],
    ) -> None:
        if len(dto_list) == 0:
            return

        from .service_base import ServiceBase

        oto_field: DTOOneToOneField
        for key, oto_field in self._dto_class.one_to_one_fields_map.items():
            if key not in fields["root"] or key not in expands["root"]:
                continue

            if oto_field.entity_relation_owner != EntityRelationOwner.SELF:
                continue

            service = ServiceBase(
                self._injector_factory,
                DAOBase(
                    self._injector_factory.db_adapter(),
                    oto_field.entity_type,
                ),
                oto_field.expected_type,
                oto_field.entity_type,
            )

            field_name: str = oto_field.entity_field

            keys_to_fetch: ty.Set[str] = {
                getattr(dto, field_name)
                for dto in dto_list
                if getattr(dto, field_name) is not None
            }

            if len(keys_to_fetch) == 0:
                continue

            pk_field: str = oto_field.expected_type.pk_field

            related_filters: ty.Dict[str, str] = {
                pk_field: ",".join(str(k) for k in keys_to_fetch)
            }

            local_expands: ty.Optional[FieldsTree] = None
            if key in expands:
                local_expands = extract_child_tree(expands, key)
                pass

            local_fields: ty.Optional[FieldsTree] = None
            if key in fields:
                local_fields = extract_child_tree(fields, key)
                pass

            related_dto_list: ty.List[DTOBase] = service.list(
                after=None,
                limit=None,
                fields=local_fields,
                order_fields=None,
                filters=related_filters,
                search_query=None,
                return_hidden_fields=None,
                expands=local_expands,
            )

            related_map: ty.Dict[str, ty.Dict[str, ty.Any]] = {
                str(getattr(x, pk_field)): x.convert_to_dict(local_fields)
                for x in related_dto_list
            }
            # NOTE: I'm assuming pk_field of x will never be NULL, because
            #           to be NULL would mean to not have a PK.

            for dto in dto_list:
                orig_val: str = str(getattr(dto, field_name))
                if orig_val is None:
                    setattr(dto, field_name, None)
                    continue

                if orig_val not in related_map:
                    # NOTE: Separating from when orig_val is None because it
                    #           probably should be an error when the field has
                    #           a value but said value does not exist on the
                    #           related table.
                    setattr(dto, field_name, None)
                    continue

                setattr(dto, field_name, related_map[orig_val])

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
