import json

from typing import List

from nsj_gcf_utils.json_util import convert_to_dumps
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.exception import PostgresFunctionException
from nsj_rest_lib.settings import USE_SQL_RETURNING_CLAUSE

from .dao_base_util import DAOBaseUtil


class DAOBaseInsert(DAOBaseUtil):

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

    def _sql_insert_function_type(
        self, entity: EntityBase, sql_read_only_fields: List[str] = []
    ) -> str:
        """
        Retorna uma string contendo uma lista de atribuições para os campos do type do banco de dados (a ser usado como entrada da função).
        """
        # Construindo a lista de valores que entrarão na query
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
        fields = []
        for k in sql_fields:
            if k in sql_read_only_fields:
                continue

            if getattr(entity, k, None) is None:
                continue

            if k not in entity.__class__.fields_map:
                continue

            entity_field = entity.__class__.fields_map[k]
            if not getattr(entity_field, "insert_by_function", False):
                continue

            type_field_name = entity_field.get_insert_type_field_name()

            fields.append(f"VAR_TIPO.{type_field_name} = :{k};")

        return "\n".join(fields)

    def insert_by_function(
        self, entity: EntityBase, sql_read_only_fields: List[str] = []
    ):
        """
        Insere o objeto de entidade "entity" no banco de dados, por meio de uma função de banco em PL/PGSQL
        """

        # Montando as cláusulas dos campos
        sql_insert_function_type = self._sql_insert_function_type(
            entity, sql_read_only_fields
        )

        # Montando a query principal
        sql = f"""
        DO $DOINSERT$
            DECLARE VAR_TIPO {entity.insert_type};
            DECLARE VAR_RETORNO RECORD;
        BEGIN
            {sql_insert_function_type}

            VAR_RETORNO = {entity.insert_function}(VAR_TIPO);
            PERFORM set_config('retorno.bloco', VAR_RETORNO.mensagem::varchar, true);
        END $DOINSERT$;

        SELECT current_setting('retorno.bloco', true)::jsonb as retorno;
        """

        # Montando um dicionário com valores das propriedades
        values_map = convert_to_dumps(entity)

        # Realizando o insert no BD e recuperando o retorno em uma única chamada
        rowcount, returning = self._db.execute_batch(sql, **values_map)

        if rowcount <= 0 or len(returning) <= 0:
            raise Exception(
                f"Erro inserindo {entity.__class__.__name__} no banco de dados"
            )

        # Interpretando o retorno da função
        returning = returning[0]["retorno"]

        if returning["codigo"].lower().strip() != "ok":
            if returning["tipo"]:
                msg = f"{returning['tipo']}: {returning['mensagem']}"
            else:
                msg = returning["mensagem"]

            raise PostgresFunctionException(msg)

        return entity
