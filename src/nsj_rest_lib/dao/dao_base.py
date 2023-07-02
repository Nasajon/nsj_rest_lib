import enum
import uuid

from typing import Any, Dict, List, Tuple

from nsj_rest_lib.descriptor.conjunto_type import ConjuntoType
from nsj_rest_lib.descriptor.filter_operator import FilterOperator
from nsj_rest_lib.entity.entity_base import EntityBase, EMPTY
from nsj_rest_lib.entity.filter import Filter
from nsj_rest_lib.exception import NotFoundException, AfterRecordNotFoundException

from nsj_gcf_utils.db_adapter2 import DBAdapter2
from nsj_gcf_utils.json_util import convert_to_dumps

from nsj_rest_lib.settings import USE_SQL_RETURNING_CLAUSE


class DAOBase:
    _db: DBAdapter2
    _entity_class: EntityBase

    def __init__(self, db: DBAdapter2, entity_class: EntityBase):
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

    def _sql_fields(self, fields: List[str] = None) -> str:
        """
        Returns a list of fields to build select queries (in string, with comma separator)
        """

        # Creating entity instance
        entity = self._entity_class()

        # Building SQL fields
        if fields is None:
            fields = [
                f"t0.{k}"
                for k in entity.__dict__
                if not callable(getattr(entity, k, None)) and not k.startswith("_")
            ]

        return ", ".join(fields)

    def get(self, id: uuid.UUID, fields: List[str] = None, filters=None) -> EntityBase:
        """
        Returns an entity instance by its ID.
        """

        # Creating a entity instance
        entity = self._entity_class()

        # Organizando o where dos filtros
        filters_where, filter_values_map = self._make_filters_sql(filters)

        # Building query
        sql = f"""
        select
            {self._sql_fields(fields)}
        from
            {entity.get_table_name()} as t0
        where
            t0.{entity.get_pk_field()} = :id
            {filters_where}
        """
        values = {"id": id}
        values.update(filter_values_map)

        # Running query
        resp = self._db.execute_query_to_model(sql, self._entity_class, **values)

        # Checking if ID was found
        if len(resp) <= 0:
            raise NotFoundException(
                f"{self._entity_class.__name__} com id {id} não encontrado."
            )

        return resp[0]

    def _make_filters_sql(
        self,
        filters: Dict[str, List[Filter]],
        with_and: bool = True,
        use_table_alias: bool = True,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Interpreta os filtros, retornando uma tupla com formato (filters_where, filter_values_map), onde
        filters_where: Parte do SQL, a ser adicionada na cláusula where, para realização dos filtros
        filter_values_map: Dicionário com os valores dos filtros, a serem enviados na excução da query

        Se receber o parâmetro filters nulo ou vazio, retorna ('', {}).
        """

        filters_where = ""
        filter_values_map = {}
        if filters is not None:
            filters_where = []

            # Iterating fields with filters
            for filter_field in filters:
                field_filter_where_or = []
                field_filter_where_and = []

                # Iterating condictions
                idx = -1
                for condiction in filters[filter_field]:
                    idx += 1

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

                    # Making condiction alias
                    if not (condiction.operator == FilterOperator.NOT_NULL):
                        condiction_alias = (
                            f"ft_{condiction.operator.value}_{filter_field}_{idx}"
                        )
                        condiction_alias_subtituir = f":{condiction_alias}"
                    else:
                        condiction_alias = ""
                        condiction_alias_subtituir = ""

                    # Making condiction buffer
                    if use_table_alias:
                        condiction_buffer = (
                            f"t0.{filter_field} {operator} {condiction_alias_subtituir}"
                        )
                    else:
                        condiction_buffer = (
                            f"{filter_field} {operator} {condiction_alias_subtituir}"
                        )

                    # Storing field filter where
                    if operator == "=" or operator == "like" or operator == "ilike":
                        field_filter_where_or.append(condiction_buffer)
                    else:
                        field_filter_where_and.append(condiction_buffer)

                    # Storing condiction value
                    if condiction.value is not None:
                        if isinstance(condiction.value.__class__, enum.EnumMeta):
                            if isinstance(condiction.value.value, tuple):
                                filter_values_map[
                                    condiction_alias
                                ] = condiction.value.value[1]
                            else:
                                filter_values_map[
                                    condiction_alias
                                ] = condiction.value.value
                        else:
                            filter_values_map[condiction_alias] = condiction.value

                    if operator == "like" or operator == "ilike":
                        filter_values_map[
                            condiction_alias
                        ] = f"%{filter_values_map[condiction_alias]}%"

                # Formating condictions (with OR)
                field_filter_where_or = " or ".join(field_filter_where_or)
                field_filter_where_and = " and ".join(field_filter_where_and)
                if field_filter_where_or.strip() != "":
                    field_filter_where_or = f"({field_filter_where_or})"
                    filters_where.append(field_filter_where_or)

                if field_filter_where_and.strip() != "":
                    field_filter_where_and = f"({field_filter_where_and})"
                    filters_where.append(field_filter_where_and)

            # Formating all filters (with AND)
            filters_where = "\n and ".join(filters_where)
            if filters_where.strip() != "" and with_and:
                filters_where = f"and {filters_where}"

        return (filters_where, filter_values_map)

    def list(
        self,
        after: uuid.UUID,
        limit: int,
        fields: List[str],
        order_fields: List[str],
        filters: Dict[str, List[Filter]],
        conjunto_type: ConjuntoType = None,
        conjunto_field: str = None,
    ) -> List[EntityBase]:
        """
        Returns a paginated entity list.
        """

        # Creating a entity instance
        entity = self._entity_class()

        # Cheking should use default entity order
        if order_fields is None:
            order_fields = entity.get_default_order_fields()

        # Making order fields with alias list
        order_fields_alias = [f"t0.{i}" for i in order_fields]

        # Resolving data to pagination
        order_map = {field: None for field in order_fields}

        if after is not None:
            try:
                after_obj = self.get(after)
            except NotFoundException as e:
                raise AfterRecordNotFoundException(
                    f"Identificador recebido no parâmetro after {id}, não encontrado para a entidade {self._entity_class.__name__}."
                )

            if after_obj is not None:
                for field in order_fields:
                    order_map[field] = getattr(after_obj, field, None)

        # Making default order by clause
        order_by = f"""
            {', '.join(order_fields_alias)}
        """

        # Organizando o where da paginação
        pagination_where = ""
        if after is not None:
            # Making a list of pagination condictions
            list_page_where = []
            old_fields = []
            for field in order_fields:
                # Making equals condictions
                buffer_old_fields = "true"
                for of in old_fields:
                    buffer_old_fields += f" and t0.{of} = :{of}"

                # Making current more than condiction
                list_page_where.append(
                    f"({buffer_old_fields} and t0.{field} > :{field})"
                )

                # Storing current field as old
                old_fields.append(field)

            # Making SQL page condiction
            pagination_where = f"""
                and (
                    false
                    or {' or '.join(list_page_where)}
                )
            """

        # Resulvendo o join de conjuntos (se houver)
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

        # Montando a query em si
        sql = f"""
        {with_conjunto}
        select

            {fields_conjunto}
            {self._sql_fields(fields)}

        from
            {entity.get_table_name()} as t0
            {join_conjuntos}

        where
            true
            {pagination_where}
            {filters_where}

        order by
            {order_by}
        """

        # Adding limit if received
        if limit is not None:
            sql += f"        limit {limit}"

        # Making the values dict
        kwargs = {**order_map, **filter_values_map, **conjunto_map}

        # Running the SQL query
        resp = self._db.execute_query_to_model(sql, self._entity_class, **kwargs)

        return resp

    def _make_conjunto_sql(
        self,
        conjunto_type: ConjuntoType,
        entity: EntityBase,
        filters: Dict[str, List[Filter]],
        conjunto_field: str = None,
    ):
        tabela_conjunto = f"ns.conjuntos{conjunto_type.name.lower()}"
        cadastro = conjunto_type.value

        with_conjunto = f"""
            with grupos_conjuntos as (
                select
                    gemp0.grupoempresarial as grupo_empresarial_pk,
                    gemp0.codigo as grupo_empresarial_codigo,
                    est_c0.conjunto
                from ns.gruposempresariais gemp0
                join ns.empresas emp0 on (emp0.grupoempresarial = gemp0.grupoempresarial and gemp0.codigo in :grupo_empresarial_conjunto_codigo)
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

        fields_conjunto = f"""
            gc0.grupo_empresarial_pk,
            gc0.grupo_empresarial_codigo,
            gc0.conjunto as conjunto,
            """

        # Motando os parâmetros de conjuntos para a query
        valores_filtro = []
        for filtro in filters[conjunto_field]:
            valores_filtro.append(filtro.value)

        conjunto_map = {
            "conjunto_cadastro": cadastro,
            "grupo_empresarial_conjunto_codigo": tuple(valores_filtro),
        }

        del filters[conjunto_field]

        return join_conjuntos, with_conjunto, fields_conjunto, conjunto_map

    def _sql_insert_fields(self) -> str:
        """
        Retorna uma tupla com duas partes: (sql_fields, sql_ref_values), onde:
        - sql_fields: Lista de campos a inserir no insert
        - sql_ref_values: Lista das referências aos campos, a inserir no insert (parte values)
        """

        # Creating entity instance
        entity = self._entity_class()

        # Building SQL fields
        fields = [
            f"{k}"
            for k in entity.__dict__
            if not callable(getattr(entity, k, None)) and not k.startswith("_")
        ]
        ref_values = [
            f":{k}"
            for k in entity.__dict__
            if not callable(getattr(entity, k, None)) and not k.startswith("_")
        ]

        return (", ".join(fields), ", ".join(ref_values))

    def insert(self, entity: EntityBase):
        """
        Insere o objeto de entidade "entity" no banco de dados
        """

        # Montando as cláusulas dos campos
        sql_fields, sql_ref_values = self._sql_insert_fields()

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

        if returning_fields is not None and USE_SQL_RETURNING_CLAUSE:
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
        if returning_fields is not None and USE_SQL_RETURNING_CLAUSE:
            for field in returning_fields:
                setattr(entity, field, returning[0][field])

        return entity

    def _sql_update_fields(self, entity: EntityBase, ignore_nones: bool = False) -> str:
        """
        Retorna lista com os campos para update, no padrão "field = :field"
        """

        # Building SQL fields
        if ignore_nones:
            fields = [
                f"{k} = :{k}"
                for k in entity.__dict__
                if not callable(getattr(entity, k, None))
                and not k.startswith("_")
                and getattr(entity, k) is not None
                and k not in entity.get_const_fields()
            ]
        else:
            fields = [
                f"{k} = :{k}"
                for k in entity.__dict__
                if not callable(getattr(entity, k, None))
                and not k.startswith("_")
                and k not in entity.get_const_fields()
            ]

        return ", ".join(fields)

    def update(
        self,
        entity: EntityBase,
        filters: Dict[str, List[Filter]],
        partial_update: bool = False,
    ):
        """
        Atualiza o objeto de entidade "entity" no banco de dados
        """

        # Montando a cláusula dos campos
        sql_fields = self._sql_update_fields(entity, partial_update)

        # Organizando o where dos filtros
        filters_where, filter_values_map = self._make_filters_sql(filters, False, False)

        # CUIDADO PARA NÂO ATUALIZAR O QUE NÃO DEVE
        if filters_where is None or filters_where.strip() == "":
            raise NotFoundException(
                f"{self._entity_class.__name__} não encontrado. Filtros: {filters}"
            )

        # Montando a query principal
        sql = f"""
        update {entity.get_table_name()} set

            {sql_fields}

        where

            {filters_where}
        """

        # Montando as cláusulas returning
        returning_fields = entity.get_update_returning_fields()

        if returning_fields is not None and USE_SQL_RETURNING_CLAUSE:
            sql_returning = ", ".join(returning_fields)

            sql += "\n"
            sql += f"returning {sql_returning}"

        # Montando um dicionário com valores das propriedades
        values_map = convert_to_dumps(entity)

        # Convertendo EMPTY para None, se necessário
        if partial_update:
            for key in values_map:
                if values_map[key] == EMPTY:
                    values_map[key] = None

        # Montado o map de valores a passar no update
        kwargs = {**values_map, **filter_values_map}

        # Realizando o update no BD
        rowcount, returning = self._db.execute(sql, **kwargs)

        if rowcount <= 0:
            raise NotFoundException(
                f"{self._entity_class.__name__} com id {values_map[self._entity_class().get_pk_field()]} não encontrado."
            )

        # Complementando o objeto com os dados de retorno
        if returning_fields is not None and USE_SQL_RETURNING_CLAUSE:
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
        filters_where, filter_values_map = self._make_filters_sql(filters, False, False)

        # CUIDADO PARA NÂO EXCLUIR O QUE NÃO DEVE
        if filters_where is None or filters_where.strip() == "":
            raise NotFoundException(
                f"{self._entity_class.__name__} não encontrado. Filtros: {filters}"
            )

        # Montando a query
        sql = f"""
        delete from {entity.get_table_name()} where {filters_where}
        """

        # Executando a query
        rowcount, _ = self._db.execute(sql, **filter_values_map)

        # Verificando se houve alguma deleção
        if rowcount <= 0:
            raise NotFoundException(
                f"{self._entity_class.__name__} não encontrado. Filtros: {filters}"
            )
