import abc

from typing import List


class EMPTY:
    pass


class EntityBase(abc.ABC):

    
    def initialize_fields(self):
        for annotation in self.__annotations__:
            self.__setattr__(annotation, None)  

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
    
    def get_const_fields(self) -> List[str]:
        return ['criado_em','criado_por']
