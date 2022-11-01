from typing import Any

from nsj_rest_lib.descriptor.filter_operator import FilterOperator


class Filter:

    def __init__(
        self,
        operator: FilterOperator,
        value: Any
    ):
        self.operator = operator
        self.value = value

    def __repr__(self) -> str:
        return f'{self.value}'