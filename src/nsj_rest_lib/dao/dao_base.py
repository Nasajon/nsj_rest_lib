import decimal
import datetime
import enum
import uuid
import re
import unidecode

from typing import Any, Dict, List, Tuple, Set, Type

from nsj_rest_lib.descriptor.conjunto_type import ConjuntoType
from nsj_rest_lib.descriptor.filter_operator import FilterOperator
from nsj_rest_lib.entity.entity_base import EntityBase, EMPTY
from nsj_rest_lib.entity.filter import Filter
from nsj_rest_lib.exception import (
    ConflictException,
    NotFoundException,
    AfterRecordNotFoundException,
)
from nsj_rest_lib.util.db_adapter2 import DBAdapter2
from nsj_rest_lib.util.join_aux import JoinAux
from nsj_rest_lib.util.log_time import log_time
from nsj_rest_lib.util.order_spec import (
    OrderFieldSource,
    OrderFieldSpec,
    PARTIAL_JOIN_ALIAS,
)

from nsj_gcf_utils.json_util import convert_to_dumps

from nsj_rest_lib.settings import (
    USE_SQL_RETURNING_CLAUSE,
    REST_LIB_AUTO_INCREMENT_TABLE,
    get_logger,
)


class DAOBase:
    _db: DBAdapter2
    _entity_class: Type[EntityBase]

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

    def get(
        self,
        key_field: str,
        id: uuid.UUID,
        fields: List[str] = None,
        filters=None,
        conjunto_type: ConjuntoType = None,
        conjunto_field: str = None,
        joins_aux: List[JoinAux] = None,
        override_data: bool = False,
        partial_exists_clause: Tuple[str, str, str] = None,
    ) -> EntityBase:
        """
        Returns an entity instance by its ID.
        """

        # Creating a entity instance
        entity = self._entity_class()

        # Resolvendo o join de conjuntos (se houver)
        with_conjunto = ""
        fields_conjunto = ""
        join_conjuntos = ""
        conjunto_map = {}
        if conjunto_type is not None:
            (
                join_conjuntos,
                with_conjunto,
                fields_conjunto,
                conjunto_map,
            ) = self._make_conjunto_sql(conjunto_type, entity, filters, conjunto_field)

        # Organizando o where dos filtros
        filters_where, filter_values_map = self._make_filters_sql(filters)

        # Montando a clausula dos fields vindos dos joins
        sql_join_fields, sql_join = self._make_joins_sql(joins_aux)

        partial_exists_sql = ""
        if partial_exists_clause is not None:
            (
                partial_table_name,
                partial_base_field,
                partial_relation_field,
            ) = partial_exists_clause
            partial_exists_sql = f"""
            and exists (
                select 1
                from {partial_table_name} as partial_exists
                where partial_exists.{partial_relation_field} = t0.{partial_base_field}
            )
            """

        # Building query
        sql = f"""
        {with_conjunto}
        select
            {fields_conjunto}
            {self._sql_fields(fields)}
            {sql_join_fields}
        from
            {entity.get_table_name()} as t0
            {join_conjuntos}
            {sql_join}
        where
            t0.{key_field} = :id
            {filters_where}
            {partial_exists_sql}
        limit 10
        """
        values = {"id": id}
        values.update(filter_values_map)
        values.update(conjunto_map)

        # Running query
        resp = self._db.execute_query_to_model(sql, self._entity_class, **values)

        # Checking if ID was found
        if len(resp) <= 0:
            raise NotFoundException(
                f"{self._entity_class.__name__} com id {id} não encontrado."
            )

        # Verificando se foi encontrado mais de um registro para o ID passado
        if not override_data and len(resp) > 1:
            raise ConflictException(
                f"Encontrado mais de um registro do tipo {self._entity_class.__name__}, para o id {id}."
            )

        if not override_data:
            return resp[0]
        else:
            return resp

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
                    filters_where.append(f"({field_filter_where} or {field_filter_where_null})")
                else:
                    filters_where.append(field_filter_where_null)
            else:
                filters_where.extend(field_filter_where)

        # Formating all filters (with AND)
        filters_where = "\n and ".join(filters_where)

        if filters_where.strip() != "" and with_and:
            filters_where = f"and {filters_where}"

        return (filters_where, filter_values_map)

    @log_time
    def list(
        self,
        after: uuid.UUID,
        limit: int,
        fields: List[str],
        order_fields: List[OrderFieldSpec] | List[str] | None,
        filters: Dict[str, List[Filter]],
        conjunto_type: ConjuntoType = None,
        conjunto_field: str = None,
        entity_key_field: str = None,
        entity_id_value: any = None,
        search_query: str = None,
        search_fields: List[str] = None,
        joins_aux: List[JoinAux] = None,
        partial_exists_clause: Tuple[str, str, str] = None,
    ) -> List[EntityBase]:
        """
        Returns a paginated entity list.
        """

        # Creating a entity instance
        entity = self._entity_class()

        raw_order_fields = order_fields
        if raw_order_fields is None:
            raw_order_fields = entity.get_default_order_fields()

        order_specs: List[OrderFieldSpec] = []
        for field in raw_order_fields:
            if isinstance(field, OrderFieldSpec):
                order_specs.append(field)
                continue

            if not isinstance(field, str):
                raise ValueError(
                    "order_fields deve ser uma lista de strings ou OrderFieldSpec."
                )

            field_clean = re.sub(r"\basc\b|\bdesc\b", "", field, flags=re.IGNORECASE).strip()
            is_desc = bool(re.search(r"\bdesc\b", field, flags=re.IGNORECASE))
            order_specs.append(
                OrderFieldSpec(
                    column=field_clean,
                    is_desc=is_desc,
                    source=OrderFieldSource.BASE,
                    alias=None,
                )
            )

        sql_order_items: List[Tuple[str, str, bool, str]] = []
        order_fields_alias: List[str] = []
        for spec in order_specs:
            alias_resolved = self._resolve_order_alias(spec)
            param_name = self._build_order_param(alias_resolved, spec.column)
            sql_order_items.append((alias_resolved, spec.column, spec.is_desc, param_name))

            clause = f"{alias_resolved}.{spec.column}"
            if spec.is_desc:
                clause = f"{clause} desc"
            order_fields_alias.append(clause)

        # Resolving data to pagination
        order_map = {param: None for _, _, _, param in sql_order_items}

        if after is not None:
            try:
                if entity_key_field is None:
                    after_obj = self.get(
                        entity.get_pk_field(),
                        after,
                        fields,
                        filters,
                        conjunto_type=conjunto_type,
                        conjunto_field=conjunto_field,
                        joins_aux=joins_aux,
                        partial_exists_clause=partial_exists_clause,
                    )
                else:
                    after_obj = self.get(
                        entity_key_field,
                        entity_id_value,
                        fields,
                        filters,
                        conjunto_type=conjunto_type,
                        conjunto_field=conjunto_field,
                        joins_aux=joins_aux,
                        partial_exists_clause=partial_exists_clause,
                    )
            except NotFoundException as e:
                raise AfterRecordNotFoundException(
                    f"Identificador recebido no parâmetro after {id}, não encontrado para a entidade {self._entity_class.__name__}."
                )

            if after_obj is not None:
                for _, column, _, param_name in sql_order_items:
                    order_map[param_name] = getattr(after_obj, column, None)

        # Making default order by clause
        order_by = f"""
            {', '.join(order_fields_alias)}
        """

        # Organizando o where da paginação
        pagination_where = ""
        if after is not None:
            # Making a list of pagination condictions
            list_page_where = []
            old_specs: List[Tuple[str, str, bool, str]] = []
            for alias, column, is_desc, param_name in sql_order_items:
                # Making equals condictions
                buffer_old_fields = "true"
                for old_alias, old_column, _, old_param in old_specs:
                    buffer_old_fields += (
                        f" and {old_alias}.{old_column} = :{old_param}"
                    )

                # Making current more than condiction
                list_page_where.append(
                    f"({buffer_old_fields} and {alias}.{column} {'<' if is_desc else '>'} :{param_name})"
                )

                # Storing current field as old
                old_specs.append((alias, column, is_desc, param_name))

            # Making SQL page condiction
            pagination_where = f"""
                and (
                    false
                    or {' or '.join(list_page_where)}
                )
            """

        # Montando o filtro de search (com ilike)
        search_map, search_where = self._make_search_sql(
            search_query, search_fields, entity
        )

        # Resolvendo o join de conjuntos (se houver)
        with_conjunto = ""
        fields_conjunto = ""
        join_conjuntos = ""
        conjunto_map = {}
        if conjunto_type is not None:
            (
                join_conjuntos,
                with_conjunto,
                fields_conjunto,
                conjunto_map,
            ) = self._make_conjunto_sql(conjunto_type, entity, filters, conjunto_field)

        # Organizando o where dos filtros
        filters_where, filter_values_map = self._make_filters_sql(filters)

        # Montando a clausula dos fields vindos dos joins
        sql_join_fields, sql_join = self._make_joins_sql(joins_aux)

        partial_exists_sql = ""
        if partial_exists_clause is not None:
            (
                partial_table_name,
                partial_base_field,
                partial_relation_field,
            ) = partial_exists_clause
            partial_exists_sql = f"""
            and exists (
                select 1
                from {partial_table_name} as partial_exists
                where partial_exists.{partial_relation_field} = t0.{partial_base_field}
            )
            """

        # Montando a query em si
        sql = f"""
        {with_conjunto}
        select

            {fields_conjunto}
            {self._sql_fields(fields)}
            {sql_join_fields}

        from
            {entity.get_table_name()} as t0
            {join_conjuntos}
            {sql_join}

        where
            true
            {pagination_where}
            {filters_where}
            {search_where}
            {partial_exists_sql}

        order by
            {order_by}
        """

        # Adding limit if received
        if limit is not None:
            sql += f"        limit {limit}"

        # Making the values dict
        kwargs = {**order_map, **filter_values_map, **conjunto_map, **search_map}

        # Running the SQL query
        get_logger().debug(f"[RestLib Debug] List SQL: {sql}")
        get_logger().debug(f"[RestLib Debug] List Parameters: {kwargs}")
        resp = self._db.execute_query_to_model(sql, self._entity_class, **kwargs)

        return resp

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

    def _make_search_sql(
        self, search_query, search_fields, entity
    ) -> Tuple[Dict[str, any], str]:
        """
        Monta a parte da cláusula where referente ao parâmetro search, bem como o mapa de
        valores para realizar a pesquisa (passando para a execução da query).

        Retorna uma tupla, onde a primeira posição é o mapa de valores, e a segunda a cláusula sql.
        """

        search_map = {}
        search_where = ""

        date_pattern = "(\d\d)/(\d\d)/((\d\d\d\d)|(\d\d))"
        int_pattern = "(\d+)"
        float_pattern = "(\d+((,|\.)\d+)?)"

        if search_fields is not None and search_query is not None:
            search_buffer = "false \n"
            for search_field in search_fields:
                search_str = search_query

                entity_field = entity.fields_map.get(search_field)
                if entity_field is None:
                    continue

                if (
                    entity_field.expected_type is datetime.datetime
                    or entity_field.expected_type is datetime.date
                ):
                    # Tratando da busca de datas
                    received_floats = re.findall(date_pattern, search_str)
                    cont = -1
                    for received_float in received_floats:
                        cont += 1

                        dia = int(received_float[0])
                        mes = int(received_float[0])
                        ano = received_float[0]
                        if len(ano) < 4:
                            ano = f"20{ano}"
                        ano = int(ano)

                        data_obj = None
                        try:
                            data_obj = datetime.date(ano, mes, dia)
                        except Exception:
                            continue

                        search_buffer += (
                            f" or t0.{search_field} = :shf_{search_field}_{cont} \n"
                        )
                        search_map[f"shf_{search_field}_{cont}"] = data_obj

                elif entity_field.expected_type is int:
                    # Tratando da busca de inteiros
                    search_str = re.sub(date_pattern, "", search_str)

                    received_floats = re.findall(int_pattern, search_str)
                    cont = -1
                    for received_float in received_floats:
                        cont += 1
                        valor = int(received_float[0])
                        valor_min = int(valor * 0.9)
                        valor_max = int(valor * 1.1)

                        search_buffer += f" or (t0.{search_field} >= :shf_{search_field}_{cont}_min and t0.{search_field} <= :shf_{search_field}_{cont}_max) \n"
                        search_map[f"shf_{search_field}_{cont}_min"] = valor_min
                        search_map[f"shf_{search_field}_{cont}_max"] = valor_max

                elif (
                    entity_field.expected_type is int
                    or entity_field.expected_type is decimal.Decimal
                ):
                    # Tratando da busca de floats e decimais
                    search_str = re.sub(date_pattern, "", search_str)

                    received_floats = re.findall(float_pattern, search_str)
                    cont = -1
                    for received_float in received_floats:
                        cont += 1
                        valor = float(received_float[0])
                        valor_min = valor * 0.9
                        valor_max = valor * 1.1

                        search_buffer += f" or (t0.{search_field} >= :shf_{search_field}_{cont}_min and t0.{search_field} <= :shf_{search_field}_{cont}_max) \n"
                        search_map[f"shf_{search_field}_{cont}_min"] = valor_min
                        search_map[f"shf_{search_field}_{cont}_max"] = valor_max

                elif (
                    entity_field.expected_type is str
                    or entity_field.expected_type is uuid
                ):
                    # Tratando da busca de strings e UUIDs
                    cont = -1
                    for palavra in search_str.split(" "):
                        if palavra == "":
                            continue

                        cont += 1
                        search_buffer += f" or upper(CAST(t0.{search_field} AS varchar)) like upper(unaccent(:shf_{search_field}_{cont})) \n"
                        search_map[f"shf_{search_field}_{cont}"] = (
                            f"%{unidecode.unidecode(palavra)}%"
                        )

            search_where = f"""
            and (
                {search_buffer}
            )
            """

        return search_map, search_where

    def _make_conjunto_sql(
        self,
        conjunto_type: ConjuntoType,
        entity: EntityBase,
        filters: Dict[str, List[Filter]],
        conjunto_field: str = None,
    ):
        tabela_conjunto = f"ns.conjuntos{conjunto_type.name.lower()}"
        cadastro = conjunto_type.value

        # Motando os parâmetros de conjuntos para a query
        valores_filtro_codigo = []
        valores_filtro_id = []
        for filtro in filters[conjunto_field]:
            if self.is_valid_uuid(filtro.value):
                valores_filtro_id.append(filtro.value)
            else:
                valores_filtro_codigo.append(filtro.value)

        conjunto_map = {
            "conjunto_cadastro": cadastro,
            "grupo_empresarial_conjunto_codigo": tuple(valores_filtro_codigo),
            "grupo_empresarial_conjunto_id": tuple(valores_filtro_id),
        }

        query_grupo = ""
        if valores_filtro_codigo and valores_filtro_id:
            query_grupo = "and (gemp0.codigo in :grupo_empresarial_conjunto_codigo or gemp0.grupoempresarial in :grupo_empresarial_conjunto_id)"
        elif valores_filtro_codigo:
            query_grupo = "and gemp0.codigo in :grupo_empresarial_conjunto_codigo"
        elif valores_filtro_id:
            query_grupo = "and gemp0.grupoempresarial in :grupo_empresarial_conjunto_id"

        with_conjunto = f"""
            with grupos_conjuntos as (
                select
                    gemp0.grupoempresarial as grupo_empresarial_pk,
                    gemp0.codigo as grupo_empresarial_codigo,
                    est_c0.conjunto
                from ns.gruposempresariais gemp0
                join ns.empresas emp0 on (emp0.grupoempresarial = gemp0.grupoempresarial {query_grupo})
                join ns.estabelecimentos est0 on (est0.empresa = emp0.empresa)
                join ns.estabelecimentosconjuntos est_c0 on (
                    est_c0.estabelecimento = est0.estabelecimento
                    and est_c0.cadastro = :conjunto_cadastro
                )
                group by gemp0.grupoempresarial, gemp0.codigo, est_c0.conjunto
            )
            """

        join_conjuntos = f"""
            join {tabela_conjunto} as cr0 on (t0.{entity.get_pk_field()} = cr0.registro)
            join grupos_conjuntos as gc0 on (gc0.conjunto = cr0.conjunto)
            """

        fields_conjunto = """
            gc0.grupo_empresarial_pk,
            gc0.grupo_empresarial_codigo,
            gc0.conjunto as conjunto,
            """

        del filters[conjunto_field]

        return join_conjuntos, with_conjunto, fields_conjunto, conjunto_map

    def insert_relacionamento_conjunto(
        self,
        id: str,
        conjunto_field_value: str,
        conjunto_type: ConjuntoType = None,
    ):
        # Recuperando o conjunto correspondente ao grupo_empresarial
        tabela_conjunto = f"ns.conjuntos{conjunto_type.name.lower()}"
        cadastro = conjunto_type.value
        query_grupo = ""

        if self.is_valid_uuid(conjunto_field_value):
            data = {
                "conjunto_cadastro": cadastro,
                "grupo_empresarial_conjunto_id": conjunto_field_value,
            }
            query_grupo = "and gemp0.grupoempresarial = :grupo_empresarial_conjunto_id"
        else:
            data = {
                "conjunto_cadastro": cadastro,
                "grupo_empresarial_conjunto_codigo": conjunto_field_value,
            }
            query_grupo = "and gemp0.codigo = :grupo_empresarial_conjunto_codigo"

        sql = f"""
        select
            gemp0.grupoempresarial as grupo_empresarial_pk,
            est_c0.conjunto
        from ns.gruposempresariais gemp0
        join ns.empresas emp0 on (emp0.grupoempresarial = gemp0.grupoempresarial {query_grupo})
        join ns.estabelecimentos est0 on (est0.empresa = emp0.empresa)
        join ns.estabelecimentosconjuntos est_c0 on (
            est_c0.estabelecimento = est0.estabelecimento
            and est_c0.cadastro = :conjunto_cadastro
        )
        group by gemp0.grupoempresarial, est_c0.conjunto
        """
        resp = self._db.execute_query(sql, **data)

        if len(resp) > 1:
            raise Exception(
                f"A biblioteca nsj_rest_lib ainda não suporta inserção de registros onde há mais de um conjunto, de um mesmo tipo ({cadastro}), num mesmo grupo_empresarial ({conjunto_field_value})."
            )

        if len(resp) < 1:
            raise Exception(
                f"Não foi encontrado um conjunto correspondente ao grupo empresarial {conjunto_field_value}, para o tipo de cadastro {cadastro}."
            )

        # Inserindo o relacionamento com o conjunto
        sql = f"""
        insert into {tabela_conjunto} (conjunto, registro) values (:conjunto, :registro)
        """

        data = {"conjunto": resp[0]["conjunto"], "registro": id}
        self._db.execute(sql, **data)

    def delete_relacionamento_conjunto(
        self,
        id: str,
        conjunto_type: ConjuntoType = None,
    ):
        # Resolvendo a tabela de conjunto
        tabela_conjunto = f"ns.conjuntos{conjunto_type.name.lower()}"

        # Removendo o relacionamento com o conjunto
        sql = f"""
        delete from {tabela_conjunto} where registro = :registro
        """

        self._db.execute(sql, registro=id)

    def delete_relacionamentos_conjunto(
        self,
        ids: List[str],
        conjunto_type: ConjuntoType = None,
    ):
        # Resolvendo a tabela de conjunto
        tabela_conjunto = f"ns.conjuntos{conjunto_type.name.lower()}"

        # Removendo o relacionamento com o conjunto
        sql = f"""
        delete from {tabela_conjunto} where registro in :registro
        """

        self._db.execute(sql, registro=tuple(ids))

    def _sql_insert_fields(
        self, entity: EntityBase, sql_read_only_fields: List[str] = []
    ) -> str:
        """
        Retorna uma tupla com duas partes: (sql_fields, sql_ref_values), onde:
        - sql_fields: Lista de campos a inserir no insert
        - sql_ref_values: Lista das referências aos campos, a inserir no insert (parte values)
        """

        sql_fields = (
            entity._sql_fields
            if entity._sql_fields
            else [
                f"{k}"
                for k in entity.__dict__
                if not callable(getattr(entity, k, None)) and not k.startswith("_")
            ]
        )

        # Building SQL fields
        fields = [
            f"{k}"
            for k in sql_fields
            if k not in sql_read_only_fields or getattr(entity, k, None) is not None
        ]
        ref_values = [
            f":{k}"
            for k in sql_fields
            if k not in sql_read_only_fields or getattr(entity, k, None) is not None
        ]

        return (", ".join(fields), ", ".join(ref_values))

    def insert(self, entity: EntityBase, sql_read_only_fields: List[str] = []):
        """
        Insere o objeto de entidade "entity" no banco de dados
        """

        # Montando as cláusulas dos campos
        sql_fields, sql_ref_values = self._sql_insert_fields(
            entity, sql_read_only_fields
        )

        # Montando a query principal
        sql = f"""
        insert into {entity.get_table_name()} (

            {sql_fields}

        ) values (

            {sql_ref_values}

        )
        """

        # Montando as cláusulas returning
        returning_fields = entity.get_insert_returning_fields()
        if (
            getattr(entity, entity.get_pk_field()) is None
            and entity.get_pk_field() not in returning_fields
        ):
            returning_fields.append(entity.get_pk_field())

        if len(returning_fields) > 0 and USE_SQL_RETURNING_CLAUSE:
            sql_returning = ", ".join(returning_fields)

            sql += "\n"
            sql += f"returning {sql_returning}"

        # Montando um dicionário com valores das propriedades
        values_map = convert_to_dumps(entity)

        # Realizando o insert no BD
        rowcount, returning = self._db.execute(sql, **values_map)

        if rowcount <= 0:
            raise Exception(
                f"Erro inserindo {entity.__class__.__name__} no banco de dados"
            )

        # Complementando o objeto com os dados de retorno
        if len(returning_fields) > 0 and USE_SQL_RETURNING_CLAUSE:
            for field in returning_fields:
                setattr(entity, field, returning[0][field])

        return entity

    def partial_extension_exists(
        self,
        table_name: str,
        relation_field: str,
        relation_value: Any,
    ) -> bool:
        sql = f"select 1 from {table_name} where {relation_field} = :relation_value limit 1"
        resp = self._db.execute_query(sql, relation_value=relation_value)
        return resp is not None and len(resp) > 0

    def insert_partial_extension_record(
        self,
        table_name: str,
        data: Dict[str, Any],
    ) -> None:
        if data is None or len(data) == 0:
            raise ValueError("Não há dados para inserir na extensão parcial.")

        columns = list(data.keys())
        params = {f"pe_{idx}": data[col] for idx, col in enumerate(columns)}
        placeholders = [f":{key}" for key in params]

        sql = (
            f"insert into {table_name} ({', '.join(columns)}) "
            f"values ({', '.join(placeholders)})"
        )

        rowcount, _ = self._db.execute(sql, **params)

        if rowcount <= 0:
            raise Exception(
                f"Erro inserindo registro na extensão parcial '{table_name}'."
            )

    def update_partial_extension_record(
        self,
        table_name: str,
        relation_field: str,
        relation_value: Any,
        data: Dict[str, Any],
    ) -> int:
        if not data:
            return 0

        set_params = {}
        set_clauses = []
        for idx, (column, value) in enumerate(data.items()):
            param_name = f"pe_set_{idx}"
            set_params[param_name] = value
            set_clauses.append(f"{column} = :{param_name}")

        sql = (
            f"update {table_name} set {', '.join(set_clauses)} "
            f"where {relation_field} = :relation_value"
        )

        params = {**set_params, "relation_value": relation_value}
        rowcount, _ = self._db.execute(sql, **params)

        return rowcount

    def _sql_upsert_fields(
        self,
        entity: EntityBase,
        ignore_nones: bool = False,
        sql_read_only_fields: List[str] = [],
    ) -> str:
        """
        Retorna lista com os campos para upsert, no padrão "field = excluded.field"
        """

        sql_fields = (
            entity._sql_fields
            if entity._sql_fields
            else [
                f"{k}"
                for k in entity.__dict__
                if not callable(getattr(entity, k, None)) and not k.startswith("_")
            ]
        )

        # Building SQL fields
        fields = [
            f"{k} = excluded.{k}"
            for k in entity.__dict__
            if not callable(getattr(entity, k, None))
            and not k.startswith("_")
            and (ignore_nones and getattr(entity, k) is not None or not ignore_nones)
            and k not in entity.get_const_fields()
            and k != entity.get_pk_field()
            and k not in sql_read_only_fields
        ]

        return ", ".join(fields)

    def _sql_update_fields(
        self,
        entity: EntityBase,
        ignore_nones: bool = False,
        sql_read_only_fields: List[str] = [],
        sql_no_update_fields: Set[str] = [],
    ) -> str:
        """
        Retorna lista com os campos para update, no padrão "field = :field"
        """

        sql_fields = (
            entity._sql_fields
            if entity._sql_fields
            else [
                f"{k}"
                for k in entity.__dict__
                if not callable(getattr(entity, k, None)) and not k.startswith("_")
            ]
        )

        # Building SQL fields
        if ignore_nones:
            fields = [
                f"{k} = :{k}"
                for k in sql_fields
                if k not in entity.get_const_fields()
                and k != entity.get_pk_field()
                and k not in sql_read_only_fields
                and k not in sql_no_update_fields
                and getattr(entity, k) is not EMPTY
            ]
        else:
            fields = [
                f"{k} = :{k}"
                for k in sql_fields
                if k not in entity.get_const_fields()
                and k != entity.get_pk_field()
                and k not in sql_read_only_fields
                and k not in sql_no_update_fields
            ]

        return ", ".join(fields)

    def update(
        self,
        key_field: str,
        key_value: Any,
        entity: EntityBase,
        filters: Dict[str, List[Filter]],
        partial_update: bool = False,
        sql_read_only_fields: List[str] = [],
        sql_no_update_fields: Set[str] = [],
        upsert: bool = False,
    ):
        """
        Atualiza o objeto de entidade "entity" no banco de dados
        """

        # Organizando o where dos filtros
        filters_where, filter_values_map = self._make_filters_sql(filters, True)

        # # CUIDADO PARA NÂO ATUALIZAR O QUE NÃO DEVE
        # if filters_where is None or filters_where.strip() == "":
        #     raise NotFoundException(
        #         f"{self._entity_class.__name__} não encontrado. Filtros: {filters}"
        #     )

        # Montando cláusula upsert
        if upsert:
            # NOTE: Does not support sql_no_update_fields.

            # Montando as cláusulas dos campos
            sql_fields, sql_ref_values = self._sql_insert_fields(
                entity, sql_read_only_fields
            )

            sql_upsert_fields = self._sql_upsert_fields(
                entity, partial_update, sql_read_only_fields
            )

            conflict_fields = f"{entity.get_pk_field()}{',' + ','.join(filters.keys()) if filters else ''}"

            conflict_rules = f"""
            ON CONFLICT ({conflict_fields}) DO
            UPDATE
            SET
                {sql_upsert_fields}

                """

            # Montando a query principal
            sql = f"""
            insert into {entity.get_table_name()} as t0 (

                {sql_fields}

            ) values (

                {sql_ref_values}

            )
            {conflict_rules}
            where
                true
                and t0.{key_field} = :candidate_key_value
                {filters_where}
            """
        else:

            # Montando a cláusula dos campos
            sql_fields = self._sql_update_fields(
                entity, partial_update, sql_read_only_fields,
                sql_no_update_fields
            )

            # Montando a query principal
            sql = f"""
            update {entity.get_table_name()} as t0 set

                {sql_fields}

            where
                true
                and t0.{key_field} = :candidate_key_value
                {filters_where}
            """

        # Montando as cláusulas returning
        returning_fields = entity.get_update_returning_fields()
        if (
            getattr(entity, entity.get_pk_field()) is None
            and entity.get_pk_field() not in returning_fields
        ):
            returning_fields.append(entity.get_pk_field())

        if len(returning_fields) > 0 and USE_SQL_RETURNING_CLAUSE:
            sql_returning = ", ".join(returning_fields)

            sql += "\n"
            sql += f"returning {sql_returning}"

        # Montando um dicionário com valores das propriedades
        values_map = convert_to_dumps(entity)

        # Montado o map de valores a passar no update
        kwargs = {"candidate_key_value": key_value, **values_map, **filter_values_map}

        # Realizando o update no BD
        rowcount, returning = self._db.execute(sql, **kwargs)

        if rowcount <= 0:
            raise NotFoundException(
                f"{self._entity_class.__name__} com id {values_map[self._entity_class().get_pk_field()]} não encontrado."
            )

        # Complementando o objeto com os dados de retorno
        if len(returning_fields) > 0 and USE_SQL_RETURNING_CLAUSE:
            for field in returning_fields:
                setattr(entity, field, returning[0][field])

        return entity

    def list_ids(self, filters: Dict[str, List[Filter]]):
        """
        Lista os IDs encontrados, de acordo com os filtros recebidos.
        """

        # Retorna None, se não receber filtros
        if filters is None or len(filters) <= 0:
            return None

        # Montando uma entity fake
        entity = self._entity_class()

        # Recuperando o campo de chave primária
        pk_field = entity.get_pk_field()

        # Organizando o where dos filtros
        filters_where, filter_values_map = self._make_filters_sql(filters)

        # Montando a query
        sql = f"""
        select {pk_field} from {entity.get_table_name()} as t0 where true {filters_where}
        """

        # Executando a query
        resp = self._db.execute_query(sql, **filter_values_map)

        # Retornando em formato de lista de IDs
        if resp is None:
            return None
        else:
            return [item[pk_field] for item in resp]

    def delete(self, filters: Dict[str, List[Filter]]):
        """
        Exclui registros de acordo com os filtros recebidos.
        """

        # Retorna None, se não receber filtros
        if filters is None or len(filters) <= 0:
            raise NotFoundException(
                f"{self._entity_class.__name__} não encontrado. Filtros: {filters}"
            )

        # Montando uma entity fake
        entity = self._entity_class()

        # Organizando o where dos filtros
        filters_where, filter_values_map = self._make_filters_sql(filters, False)

        # CUIDADO PARA NÂO EXCLUIR O QUE NÃO DEVE
        if filters_where is None or filters_where.strip() == "":
            raise NotFoundException(
                f"{self._entity_class.__name__} não encontrado. Filtros: {filters}"
            )

        # Montando a query
        sql = f"""
        delete from {entity.get_table_name()} as t0 where {filters_where}
        """

        # Executando a query
        rowcount, _ = self._db.execute(sql, **filter_values_map)

        # Verificando se houve alguma deleção
        if rowcount <= 0:
            raise NotFoundException(
                f"{self._entity_class.__name__} não encontrado. Filtros: {filters}"
            )

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
