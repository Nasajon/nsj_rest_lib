from .dao_base_delete import DAOBaseDelete
from .dao_base_get import DAOBaseGet
from .dao_base_list import DAOBaseList
from .dao_base_partial_of import DAOBasePartialOf
from .dao_base_partial_update import DAOBasePartialUpdate


class DAOBase(
    DAOBasePartialUpdate,
    DAOBasePartialOf,
    DAOBaseList,
    DAOBaseGet,
    DAOBaseDelete,
):
    """
    DAOBase principal composto pelos mixins especializados.
    """

    pass
