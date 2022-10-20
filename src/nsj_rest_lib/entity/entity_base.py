import abc

from typing import List


class EMPTY:
    pass


class EntityBase(abc.ABC):

    def get_pk_column_name(self) -> str:
        return 'id'

    @abc.abstractmethod
    def get_table_name(self) -> str:
        pass

    @abc.abstractmethod
    def get_default_order_fields(self) -> List[str]:
        pass

    @abc.abstractmethod
    def get_pk_field(self) -> str:
        pass

    def get_insert_returning_fields(self) -> List[str]:
        return None

    def get_update_returning_fields(self) -> List[str]:
        return None
