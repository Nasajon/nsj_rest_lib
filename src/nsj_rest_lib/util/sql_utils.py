from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nsj_rest_lib.descriptor.dto_sql_join_field import DTOSQLJoinField

from nsj_gcf_utils.sql_utils import SQLUtils

def montar_chave_map_sql_join(field: "DTOSQLJoinField") -> str:
    return f"{field.dto_type}____{field.entity_type}____{field.entity_relation_owner}____{field.join_type}"
