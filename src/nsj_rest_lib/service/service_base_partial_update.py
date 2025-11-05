from typing import Any, Callable, Dict, List

from nsj_rest_lib.dto.dto_base import DTOBase

from .service_base_update import ServiceBaseUpdate


class ServiceBasePartialUpdate(ServiceBaseUpdate):

    def partial_update(
        self,
        dto: DTOBase,
        id: Any,
        aditional_filters: Dict[str, Any] = None,
        custom_before_update: Callable = None,
        custom_after_update: Callable = None,
        manage_transaction: bool = True,
    ) -> DTOBase:
        return self._save(
            insert=False,
            dto=dto,
            manage_transaction=manage_transaction,
            partial_update=True,
            id=id,
            aditional_filters=aditional_filters,
            custom_before_update=custom_before_update,
            custom_after_update=custom_after_update,
        )

    def partial_update_list(
        self,
        dtos: List[DTOBase],
        aditional_filters: Dict[str, Any] = None,
        custom_before_update: Callable = None,
        custom_after_update: Callable = None,
        upsert: bool = False,
    ) -> List[DTOBase]:

        _lst_return = []
        try:
            self._dao.begin()

            for dto in dtos:
                _return_object = self._save(
                    insert=False,
                    dto=dto,
                    manage_transaction=False,
                    partial_update=True,
                    id=getattr(dto, dto.pk_field),
                    aditional_filters=aditional_filters,
                    custom_before_update=custom_before_update,
                    custom_after_update=custom_after_update,
                )

                if _return_object is not None:
                    _lst_return.append(_return_object)

        except:
            self._dao.rollback()
            raise
        finally:
            self._dao.commit()

        return _lst_return
