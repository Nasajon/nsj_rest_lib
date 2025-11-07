import abc
from typing import Dict

from nsj_rest_lib.descriptor.insert_function_field import InsertFunctionField


class InsertFunctionTypeBase(abc.ABC):
    """
    Classe base para todos os tipos usados em funções de insert via PL/PGSQL.
    Mantém o contrato esperado pelo DAO para identificar campos e nomes do type/
    função.
    """

    fields_map: Dict[str, InsertFunctionField] = {}
    type_name: str = ""
    function_name: str = ""

    def get_fields_map(self) -> Dict[str, InsertFunctionField]:
        if not hasattr(self.__class__, "fields_map"):
            raise NotImplementedError(
                f"fields_map não definido em {self.__class__.__name__}"
            )
        return self.__class__.fields_map

    def get_type_name(self) -> str:
        if not hasattr(self.__class__, "type_name"):
            raise NotImplementedError(
                f"type_name não definido em {self.__class__.__name__}"
            )
        return self.__class__.type_name

    def get_function_name(self) -> str:
        if not hasattr(self.__class__, "function_name"):
            raise NotImplementedError(
                f"function_name não definido em {self.__class__.__name__}"
            )
        return self.__class__.function_name
