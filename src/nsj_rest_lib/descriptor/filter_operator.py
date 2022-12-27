import enum


class FilterOperator(enum.Enum):
    EQUALS = 'equals'
    DIFFERENT = 'diferent'
    GREATER_THAN = 'greater_than'
    LESS_THAN = 'less_than'
    LIKE = "like"
    ILIKE = "ilike"