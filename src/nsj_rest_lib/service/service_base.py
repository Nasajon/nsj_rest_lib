import typing as ty

from nsj_rest_lib.dao.dao_base import DAOBase
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.entity.insert_function_type_base import InsertFunctionTypeBase
from nsj_rest_lib.injector_factory_base import NsjInjectorFactoryBase
from nsj_rest_lib.util.db_adapter2 import DBAdapter2

from .service_base_delete import ServiceBaseDelete
from .service_base_get import ServiceBaseGet
from .service_base_insert import ServiceBaseInsert
from .service_base_list import ServiceBaseList
from .service_base_partial_update import ServiceBasePartialUpdate
from .service_base_update import ServiceBaseUpdate


class ServiceBase(
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
        insert_function_type_class: ty.Optional[
            ty.Type[InsertFunctionTypeBase]
        ] = None,
    ):
        self._injector_factory = injector_factory
        self._dao = dao
        self._dto_class = dto_class
        self._entity_class = entity_class
        self._dto_post_response_class = dto_post_response_class
        self._created_by_property = "criado_por"
        self._updated_by_property = "atualizado_por"
        self._insert_function_type_class: ty.Optional[
            ty.Type[InsertFunctionTypeBase]
        ] = None
        self._insert_function_type_fields_map: ty.Optional[dict[str, any]] = None
        self.set_insert_function_type_class(insert_function_type_class)

    @staticmethod
    def construtor1(
        db_adapter: DBAdapter2,
        dao: DAOBase,
        dto_class: ty.Type[DTOBase],
        entity_class: ty.Type[EntityBase],
        dto_post_response_class: DTOBase = None,
        insert_function_type_class: ty.Optional[
            ty.Type[InsertFunctionTypeBase]
        ] = None,
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
        )

    def set_insert_function_type_class(
        self,
        insert_function_type_class: ty.Optional[
            ty.Type[InsertFunctionTypeBase]
        ],
    ):
        if insert_function_type_class is not None and not issubclass(
            insert_function_type_class, InsertFunctionTypeBase
        ):
            raise ValueError(
                "A classe informada em insert_function_type_class deve herdar de InsertFunctionTypeBase."
            )

        self._insert_function_type_class = insert_function_type_class
        self._insert_function_type_fields_map = (
            self._validate_insert_function_type_fields()
        )

    def _validate_insert_function_type_fields(self):
        if self._insert_function_type_class is None:
            return None

        if not hasattr(self._insert_function_type_class, "fields_map"):
            raise ValueError(
                f"A classe {self._insert_function_type_class.__name__} não possui fields_map configurado."
            )

        dto_fields_map = getattr(self._dto_class, "fields_map", {})
        insert_fields_map = getattr(self._insert_function_type_class, "fields_map", {})

        for field_name in insert_fields_map.keys():
            if field_name not in dto_fields_map:
                raise ValueError(
                    f"O campo '{field_name}' do InsertFunctionType '{self._insert_function_type_class.__name__}' não existe no DTO '{self._dto_class.__name__}'."
                )

        return insert_fields_map

    def _build_insert_function_type_object(self, dto: DTOBase):
        if self._insert_function_type_class is None:
            return None

        if self._insert_function_type_fields_map is None:
            raise ValueError(
                "InsertFunctionType configurado sem campos mapeados para o DTO."
            )

        insert_object = self._insert_function_type_class()

        for field_name in self._insert_function_type_fields_map.keys():
            if not hasattr(dto, field_name):
                raise ValueError(
                    f"DTO '{self._dto_class.__name__}' não possui o campo '{field_name}' utilizado no InsertFunctionType '{self._insert_function_type_class.__name__}'."
                )

            value = getattr(dto, field_name, None)
            setattr(insert_object, field_name, value)

        return insert_object
