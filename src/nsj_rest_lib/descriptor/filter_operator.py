import enum


class FilterOperator(enum.Enum):
    EQUALS = "equals"
    DIFFERENT = "diferent"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_OR_EQUAL_THAN = "greater_or_equal_than"
    LESS_OR_EQUAL_THAN = "less_or_equal_than"
    LIKE = "like"
    ILIKE = "ilike"
    NOT_NULL = "not_null"
