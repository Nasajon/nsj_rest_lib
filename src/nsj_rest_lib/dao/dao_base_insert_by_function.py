from nsj_gcf_utils.json_util import convert_to_dumps

from nsj_rest_lib.dao.dao_base_util import DAOBaseUtil
from nsj_rest_lib.entity.insert_function_type_base import InsertFunctionTypeBase
from nsj_rest_lib.exception import PostgresFunctionException


class DAOBaseInsertByFunction(DAOBaseUtil):
    def _sql_insert_function_type(
        self,
        insert_function_object: InsertFunctionTypeBase,
    ) -> str:
        """
        Retorna as atribuições necessárias para preencher o type usado na função de insert.
        """
        assignments = []
        fields_map = getattr(insert_function_object.__class__, "fields_map", {})

        for field_name, insert_field in fields_map.items():
            value = getattr(insert_function_object, field_name, None)
            if value is None:
                continue

            type_field_name = insert_field.get_type_field_name()
            assignments.append(f"VAR_TIPO.{type_field_name} = :{field_name};")

        return "\n".join(assignments)

    def insert_by_function(
        self,
        insert_function_object: InsertFunctionTypeBase,
    ):
        """
        Insere a entidade utilizando uma função de banco declarada por meio de um InsertFunctionType.
        """

        if insert_function_object is None:
            raise ValueError(
                "É necessário informar um objeto do tipo InsertFunctionTypeBase para o insert por função."
            )

        insert_function_type_class = insert_function_object.__class__

        sql_insert_function_type = self._sql_insert_function_type(
            insert_function_object
        )

        sql = f"""
        DO $DOINSERT$
            DECLARE VAR_TIPO {insert_function_type_class.type_name};
            DECLARE VAR_RETORNO RECORD;
        BEGIN
            {sql_insert_function_type}

            VAR_RETORNO = {insert_function_type_class.function_name}(VAR_TIPO);
            PERFORM set_config('retorno.bloco', VAR_RETORNO.mensagem::varchar, true);
        END $DOINSERT$;

        SELECT current_setting('retorno.bloco', true)::jsonb as retorno;
        """

        values_map = convert_to_dumps(insert_function_object)

        rowcount, returning = self._db.execute_batch(sql, **values_map)

        if rowcount <= 0 or len(returning) <= 0:
            raise Exception(
                f"Erro inserindo {insert_function_type_class.__name__} no banco de dados"
            )

        returning = returning[0]["retorno"]

        if returning["codigo"].lower().strip() != "ok":
            if returning["tipo"]:
                msg = f"{returning['tipo']}: {returning['mensagem']}"
            else:
                msg = returning["mensagem"]

            raise PostgresFunctionException(msg)

        return insert_function_object
