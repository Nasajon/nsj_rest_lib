from typing import Any

from nsj_rest_lib.descriptor.filter_operator import FilterOperator


class Filter:

    def __init__(
        self,
        operator: FilterOperator,
        value: Any,
        table_alias: str = None,
        relation_mode: str = None,
        relation_table: str = None,
        relation_parent_field: str = None,
        relation_child_field: str = None,
    ):
        self.operator = operator
        self.value = value
        self.table_alias = table_alias
        self.relation_mode = relation_mode
        self.relation_table = relation_table
        self.relation_parent_field = relation_parent_field
        self.relation_child_field = relation_child_field

    def __repr__(self) -> str:
        return f"{self.value}"
