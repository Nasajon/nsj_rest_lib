import enum
import re
import uuid

from typing import Any, Dict, List, Tuple, Type


from nsj_rest_lib.descriptor.filter_operator import FilterOperator
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.entity.filter import Filter
from nsj_rest_lib.settings import REST_LIB_AUTO_INCREMENT_TABLE
from nsj_rest_lib.util.db_adapter2 import DBAdapter2
from nsj_rest_lib.util.join_aux import JoinAux
from nsj_rest_lib.util.order_spec import (
    OrderFieldSource,
    OrderFieldSpec,
    PARTIAL_JOIN_ALIAS,
)


class DAOBaseUtil:

    def __init__(self, db: DBAdapter2, entity_class: Type[EntityBase]):
        self._db = db
        self._entity_class = entity_class

    def begin(self):
        """
        Inicia uma transação no banco de dados
        """
        self._db.begin()

    def commit(self):
        """
        Faz commit na transação corrente no banco de dados (se houver uma).

        Não dá erro, se não houver uma transação.
        """
        self._db.commit()

    def rollback(self):
        """
        Faz rollback da transação corrente no banco de dados (se houver uma).

        Não dá erro, se não houver uma transação.
        """
        self._db.rollback()

    def in_transaction(self) -> bool:
        """
        Verifica se há uma transação em aberto no banco de dados
        (na verdade, verifica se há no DBAdapter, e não no BD em si).
        """
        return self._db.in_transaction()

    def _sql_fields(self, fields: List[str] = None, table_alias: str = "t0") -> str:
        """
        Returns a list of fields to build select queries (in string, with comma separator)
        """

        # Creating entity instance
        entity = self._entity_class()

        # Building SQL fields
        if fields is None:
            fields = [
                f"{k}"
                for k in entity.__dict__
                if not callable(getattr(entity, k, None)) and not k.startswith("_")
            ]

        resp = f", {table_alias}.".join(fields)
        return f"{table_alias}.{resp}"

    def _resolve_order_alias(self, spec: OrderFieldSpec) -> str:
        if spec.alias:
            return spec.alias
        if spec.source == OrderFieldSource.PARTIAL_EXTENSION:
            return PARTIAL_JOIN_ALIAS
        return "t0"

    def _build_order_param(self, alias: str, column: str) -> str:
        safe_alias = re.sub(r"[^0-9a-zA-Z_]", "_", alias)
        safe_column = re.sub(r"[^0-9a-zA-Z_]", "_", column)
        if safe_alias and safe_alias != "t0":
            return f"{safe_alias}_{safe_column}"
        return safe_column

    def _make_filters_sql(
        self, filters: Dict[str, List[Filter]], with_and: bool = True
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Interpreta os filtros, retornando uma tupla com formato (filters_where, filter_values_map), onde
        filters_where: Parte do SQL, a ser adicionada na cláusula where, para realização dos filtros
        filter_values_map: Dicionário com os valores dos filtros, a serem enviados na excução da query

        Se receber o parâmetro filters nulo ou vazio, retorna ('', {}).
        """

        filters_where = ""
        filter_values_map = {}

        if filters is None:
            return (filters_where, filter_values_map)

        filters_where = []

        # Iterating fields with filters
        for filter_field in filters:
            field_filter_where_or = []
            field_filter_where_and = []
            field_filter_where_in = []
            field_filter_where_not_in = []
            field_filter_where_native_in: str = None
            field_filter_where = []
            field_filter_where_null = None
            table_alias = "t0"

            # Iterating condictions
            idx = -1
            for condiction in filters[filter_field]:
                idx += 1

                if condiction.table_alias is not None:
                    table_alias = condiction.table_alias

                # Resolving condiction
                operator = "="
                if condiction.operator == FilterOperator.DIFFERENT:
                    operator = "<>"
                elif condiction.operator == FilterOperator.GREATER_THAN:
                    operator = ">"
                elif condiction.operator == FilterOperator.LESS_THAN:
                    operator = "<"
                elif condiction.operator == FilterOperator.GREATER_OR_EQUAL_THAN:
                    operator = ">="
                elif condiction.operator == FilterOperator.LESS_OR_EQUAL_THAN:
                    operator = "<="
                elif condiction.operator == FilterOperator.LIKE:
                    operator = "like"
                elif condiction.operator == FilterOperator.ILIKE:
                    operator = "ilike"
                elif condiction.operator == FilterOperator.NOT_NULL:
                    operator = "is not null"
                elif condiction.operator == FilterOperator.LENGTH_GREATER_OR_EQUAL_THAN:
                    operator = ">="
                elif condiction.operator == FilterOperator.LENGTH_LESS_OR_EQUAL_THAN:
                    operator = "<="
                elif condiction.operator == FilterOperator.IN:
                    operator = "in"
                elif condiction.operator == FilterOperator.NULL:
                    operator = "is null"

                # Making condiction alias
                if not (
                    condiction.operator == FilterOperator.NOT_NULL
                    or condiction.operator == FilterOperator.NULL
                ):
                    condiction_alias = (
                        f"ft_{condiction.operator.value}_{filter_field}_{idx}"
                    )
                    condiction_alias_subtituir = f":{condiction_alias}"
                else:
                    condiction_alias = ""
                    condiction_alias_subtituir = ""

                # Making condiction buffer
                filter_field_str = filter_field
                if condiction.operator in [
                    FilterOperator.LENGTH_GREATER_OR_EQUAL_THAN,
                    FilterOperator.LENGTH_LESS_OR_EQUAL_THAN,
                ]:
                    filter_field_str = f"length({table_alias}.{filter_field})"
                else:
                    filter_field_str = f"{table_alias}.{filter_field}"

                condiction_buffer = (
                    f"{filter_field_str} {operator} {condiction_alias_subtituir}"
                )

                multiple_values = len(filters[filter_field]) > 1 or (
                    isinstance(condiction.value, set) and len(condiction.value) > 1
                )

                # Storing field filter where
                if operator == "=" and multiple_values:
                    field_filter_where_in.append(condiction_alias_subtituir)
                elif operator == "<>" and multiple_values:
                    field_filter_where_not_in.append(condiction_alias_subtituir)
                elif operator == "=" or operator == "like" or operator == "ilike":
                    field_filter_where_or.append(condiction_buffer)
                elif operator == "in":
                    field_filter_where_native_in = condiction_alias_subtituir
                elif operator == "is null":
                    field_filter_where_null = condiction_buffer
                else:
                    field_filter_where_and.append(condiction_buffer)

                # Storing condiction value
                if condiction.value is not None:
                    if isinstance(condiction.value.__class__, enum.EnumMeta):
                        if isinstance(condiction.value.value, tuple):
                            filter_values_map[condiction_alias] = (
                                condiction.value.value[1]
                            )
                        else:
                            filter_values_map[condiction_alias] = condiction.value.value
                    else:
                        if (
                            isinstance(condiction.value, set)
                            and len(condiction.value) > 1
                        ):
                            filter_values_map[condiction_alias] = ", ".join(
                                str(value) for value in condiction.value
                            )
                        elif isinstance(condiction.value, list) >= 1:
                            filter_values_map[condiction_alias] = tuple(
                                condiction.value
                            )
                        else:
                            filter_values_map[condiction_alias] = condiction.value

                if operator == "like" or operator == "ilike":
                    filter_values_map[condiction_alias] = (
                        f"%{filter_values_map[condiction_alias]}%"
                    )

            # Formating condictions (with OR)
            field_filter_where_or = " or ".join(field_filter_where_or)
            field_filter_where_and = " and ".join(field_filter_where_and)

            if field_filter_where_in:
                field_filter_where_in = f"{table_alias}.{filter_field} in ({', '.join(field_filter_where_in)})"
                field_filter_where.append(field_filter_where_in)

            if field_filter_where_native_in:
                field_filter_where_native_in = (
                    f"{table_alias}.{filter_field} in {field_filter_where_native_in}"
                )
                field_filter_where.append(field_filter_where_native_in)

            if field_filter_where_not_in:
                field_filter_where_not_in = f"{table_alias}.{filter_field} not in ({', '.join(field_filter_where_not_in)})"
                field_filter_where.append(field_filter_where_not_in)

            if field_filter_where_or.strip() != "":
                field_filter_where_or = f"({field_filter_where_or})"
                field_filter_where.append(field_filter_where_or)

            if field_filter_where_and.strip() != "":
                field_filter_where_and = f"({field_filter_where_and})"
                field_filter_where.append(field_filter_where_and)

            if field_filter_where_null is not None:
                field_filter_where = "\n and ".join(field_filter_where)
                if field_filter_where.strip() != "":
                    filters_where.append(
                        f"({field_filter_where} or {field_filter_where_null})"
                    )
                else:
                    filters_where.append(field_filter_where_null)
            else:
                filters_where.extend(field_filter_where)

        # Formating all filters (with AND)
        filters_where = "\n and ".join(filters_where)

        if filters_where.strip() != "" and with_and:
            filters_where = f"and {filters_where}"

        return (filters_where, filter_values_map)

    def _make_joins_sql(self, joins_aux: List[JoinAux] = []):
        """
        Método auxiliar, para montar a parte dos campos, e do join propriamente dito,
        para depois compôr a query principal.
        """

        if joins_aux is None:
            return ("", "")

        sql_join_fields = ""
        sql_join = ""
        for join_aux in joins_aux:
            # Ajustando os fields
            if join_aux.fields:
                fields_sql = self._sql_fields(
                    fields=join_aux.fields, table_alias=join_aux.alias
                )

                # Adicionando os fields no SQL geral
                sql_join_fields = f"{sql_join_fields},\n{fields_sql}"

            # Montando a clausula do join em si
            join_operator = f"{join_aux.type} join"

            sql_join = f"{sql_join}\n{join_operator} {join_aux.table} as {join_aux.alias} on (t0.{join_aux.self_field} = {join_aux.alias}.{join_aux.other_field})"

        return (sql_join_fields, sql_join)

    def is_valid_uuid(self, value):
        try:
            uuid.UUID(str(value))

            return True
        except ValueError:
            return False

    def next_val(
        self,
        sequence_base_name: str,
        group_fields: List[str],
        start_value: int = 1,
    ):
        # Resolvendo o nome da sequência
        sequence_name = f"{sequence_base_name}_{'_'.join(group_fields)}"

        # Montando a query
        sql = f"""
        INSERT INTO {REST_LIB_AUTO_INCREMENT_TABLE} (seq_name, current_value)
        VALUES (:sequence_name, :start_value)
        ON CONFLICT (seq_name)
        DO UPDATE SET current_value = {REST_LIB_AUTO_INCREMENT_TABLE}.current_value + 1
        RETURNING {REST_LIB_AUTO_INCREMENT_TABLE}.current_value
        """

        # Executando e retornando
        resp = self._db.execute_query_first_result(
            sql, sequence_name=sequence_name, start_value=start_value
        )
        return resp["current_value"]
