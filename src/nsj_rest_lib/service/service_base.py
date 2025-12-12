import typing as ty

from nsj_gcf_utils.db_adapter2 import DBAdapter2

from nsj_rest_lib.dao.dao_base import DAOBase
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.entity.function_type_base import (
    InsertFunctionTypeBase,
    UpdateFunctionTypeBase,
    GetFunctionTypeBase,
    ListFunctionTypeBase,
    DeleteFunctionTypeBase,
)
from nsj_rest_lib.injector_factory_base import NsjInjectorFactoryBase

from .service_base_delete import ServiceBaseDelete
from .service_base_get import ServiceBaseGet
from .service_base_insert import ServiceBaseInsert
from .service_base_save_by_function import ServiceBaseSaveByFunction
from .service_base_list import ServiceBaseList
from .service_base_partial_update import ServiceBasePartialUpdate
from .service_base_update import ServiceBaseUpdate


class ServiceBase(
    ServiceBaseSaveByFunction,
    ServiceBasePartialUpdate,
    ServiceBaseUpdate,
    ServiceBaseInsert,
    ServiceBaseDelete,
    ServiceBaseList,
    ServiceBaseGet,
):
    _dao: DAOBase
    _dto_class: ty.Type[DTOBase]

    def __init__(
        self,
        injector_factory: NsjInjectorFactoryBase,
        dao: DAOBase,
        dto_class: ty.Type[DTOBase],
        entity_class: ty.Type[EntityBase],
        dto_post_response_class: DTOBase = None,
        insert_function_type_class: ty.Optional[ty.Type[InsertFunctionTypeBase]] = None,
        update_function_type_class: ty.Optional[ty.Type[UpdateFunctionTypeBase]] = None,
        get_function_type_class: ty.Optional[ty.Type[GetFunctionTypeBase]] = None,
        list_function_type_class: ty.Optional[ty.Type[ListFunctionTypeBase]] = None,
        delete_function_type_class: ty.Optional[ty.Type[DeleteFunctionTypeBase]] = None,
        get_function_name: str | None = None,
        list_function_name: str | None = None,
        delete_function_name: str | None = None,
        get_function_response_dto_class: ty.Optional[ty.Type[DTOBase]] = None,
        list_function_response_dto_class: ty.Optional[ty.Type[DTOBase]] = None,
        insert_function_name: str | None = None,
        update_function_name: str | None = None,
    ):
        self._injector_factory = injector_factory
        self._dao = dao
        self._dto_class = dto_class
        self._entity_class = entity_class
        self._dto_post_response_class = dto_post_response_class
        self._created_by_property = "criado_por"
        self._updated_by_property = "atualizado_por"
        self._insert_function_type_class = None
        self._update_function_type_class = None
        self._get_function_type_class = None
        self._list_function_type_class = None
        self._delete_function_type_class = None
        self._get_function_name = get_function_name
        self._list_function_name = list_function_name
        self._delete_function_name = delete_function_name
        self._insert_function_name = insert_function_name
        self._update_function_name = update_function_name
        self._get_function_response_dto_class = (
            get_function_response_dto_class or dto_class
        )
        self._list_function_response_dto_class = (
            list_function_response_dto_class or dto_class
        )
        self.set_insert_function_type_class(insert_function_type_class)
        self.set_update_function_type_class(update_function_type_class)
        self.set_get_function_type_class(get_function_type_class)
        self.set_list_function_type_class(list_function_type_class)
        self.set_delete_function_type_class(delete_function_type_class)

    @staticmethod
    def construtor1(
        db_adapter: DBAdapter2,
        dao: DAOBase,
        dto_class: ty.Type[DTOBase],
        entity_class: ty.Type[EntityBase],
        dto_post_response_class: DTOBase = None,
        insert_function_type_class: ty.Optional[ty.Type[InsertFunctionTypeBase]] = None,
        update_function_type_class: ty.Optional[ty.Type[UpdateFunctionTypeBase]] = None,
        get_function_type_class: ty.Optional[ty.Type[GetFunctionTypeBase]] = None,
        list_function_type_class: ty.Optional[ty.Type[ListFunctionTypeBase]] = None,
        delete_function_type_class: ty.Optional[ty.Type[DeleteFunctionTypeBase]] = None,
        get_function_name: str | None = None,
        list_function_name: str | None = None,
        delete_function_name: str | None = None,
        insert_function_name: str | None = None,
        update_function_name: str | None = None,
    ):
        """
        Esse construtor alternativo, evita a necessidade de passar um InjectorFactory,
        pois esse só é usado (internamente) para recuperar um db_adapter.

        Foi feito para não gerar breaking change de imediato (a ideia porém é, no futuro,
        gerar um breaking change).
        """

        class FakeInjectorFactory:
            def db_adapter(self):
                return db_adapter

        return ServiceBase(
            FakeInjectorFactory(),
            dao,
            dto_class,
            entity_class,
            dto_post_response_class,
            insert_function_type_class,
            update_function_type_class,
            get_function_type_class,
            list_function_type_class,
            delete_function_type_class,
            get_function_name,
            list_function_name,
            delete_function_name,
            insert_function_name,
            update_function_name,
        )

    def set_get_function_type_class(
        self, get_function_type_class: ty.Optional[ty.Type[GetFunctionTypeBase]]
    ):
        if get_function_type_class is not None and not issubclass(
            get_function_type_class, GetFunctionTypeBase
        ):
            raise ValueError(
                "A classe informada em get_function_type_class deve herdar de GetFunctionTypeBase."
            )
        self._get_function_type_class = get_function_type_class
        if (
            self._get_function_type_class is not None
            and getattr(self, "_dto_class", None) is not None
        ):
            self._get_function_type_class.get_function_mapping(self._dto_class)

    def set_list_function_type_class(
        self, list_function_type_class: ty.Optional[ty.Type[ListFunctionTypeBase]]
    ):
        if list_function_type_class is not None and not issubclass(
            list_function_type_class, ListFunctionTypeBase
        ):
            raise ValueError(
                "A classe informada em list_function_type_class deve herdar de ListFunctionTypeBase."
            )
        self._list_function_type_class = list_function_type_class
        if (
            self._list_function_type_class is not None
            and getattr(self, "_dto_class", None) is not None
        ):
            self._list_function_type_class.get_function_mapping(self._dto_class)

    def set_delete_function_type_class(
        self, delete_function_type_class: ty.Optional[ty.Type[DeleteFunctionTypeBase]]
    ):
        if delete_function_type_class is not None and not issubclass(
            delete_function_type_class, DeleteFunctionTypeBase
        ):
            raise ValueError(
                "A classe informada em delete_function_type_class deve herdar de DeleteFunctionTypeBase."
            )
        self._delete_function_type_class = delete_function_type_class
        if (
            self._delete_function_type_class is not None
            and getattr(self, "_dto_class", None) is not None
        ):
            self._delete_function_type_class.get_function_mapping(self._dto_class)

    def set_get_function_name(self, function_name: str | None):
        self._get_function_name = function_name

    def set_list_function_name(self, function_name: str | None):
        self._list_function_name = function_name

    def set_delete_function_name(self, function_name: str | None):
        self._delete_function_name = function_name

    def set_insert_function_name(self, function_name: str | None):
        self._insert_function_name = function_name

    def set_update_function_name(self, function_name: str | None):
        self._update_function_name = function_name

    def set_get_function_response_dto_class(self, dto_class: ty.Type[DTOBase]):
        self._get_function_response_dto_class = dto_class

    def set_list_function_response_dto_class(self, dto_class: ty.Type[DTOBase]):
        self._list_function_response_dto_class = dto_class

    def _build_function_type_from_params(
        self,
        params: dict[str, ty.Any],
        function_type_class,
        id_value: ty.Any = None,
    ):
        if function_type_class is None:
            return None
        return function_type_class.build_from_params(params, id_value=id_value)

    def _map_function_rows_to_dtos(
        self,
        rows: list[dict],
        dto_class: ty.Type[DTOBase],
        function_type_class=None,
        operation: str | None = None,
        mapping: ty.Optional[ty.Dict[str, ty.Tuple[str, ty.Any]]] = None,
    ):
        if rows is None:
            return []

        # Determina a operação quando não for informada explicitamente.
        # Para GET/LIST por FunctionType, a operação é derivada da classe.
        if operation is None and function_type_class is not None:
            from nsj_rest_lib.entity.function_type_base import (
                GetFunctionTypeBase,
                ListFunctionTypeBase,
            )

            if isinstance(function_type_class, type):
                if issubclass(function_type_class, GetFunctionTypeBase):
                    operation = "get"
                elif issubclass(function_type_class, ListFunctionTypeBase):
                    operation = "list"

        dto_fields_map = getattr(dto_class, "fields_map", {}) or {}

        dtos: list[DTOBase] = []
        for row in rows:
            dto_kwargs: dict[str, ty.Any] = {}

            # Para GET/LIST, o contrato é:
            # - o nome da coluna no retorno SEMPRE é igual a:
            #   - o valor de get_function_field, se configurado; ou
            #   - o nome do campo no DTO (descriptor.name), quando get_function_field é None.
            if operation in ("get", "list"):
                for dto_field_name, descriptor in dto_fields_map.items():
                    source_field_name = descriptor.get_function_field_name(operation)
                    dto_kwargs[dto_field_name] = row.get(source_field_name)
            else:
                # Mantém um comportamento genérico para outros cenários,
                # caso venham a reutilizar esse helper no futuro.
                dto_kwargs.update(row)

            dto_instance = dto_class(escape_validator=True, **dto_kwargs)
            dtos.append(dto_instance)

        return dtos
