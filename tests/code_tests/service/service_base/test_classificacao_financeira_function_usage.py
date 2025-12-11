import uuid

from nsj_rest_lib.decorator.dto import DTO
from nsj_rest_lib.decorator.entity import Entity
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.descriptor.entity_field import EntityField
from nsj_rest_lib.service.service_base import ServiceBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.entity.function_type_base import (
    GetFunctionTypeBase,
    ListFunctionTypeBase,
    DeleteFunctionTypeBase,
)
from nsj_rest_lib.decorator.get_function_type import GetFunctionType
from nsj_rest_lib.decorator.list_function_type import ListFunctionType
from nsj_rest_lib.decorator.delete_function_type import DeleteFunctionType
from nsj_rest_lib.descriptor.function_field import FunctionField


class FakeDAO:
    def __init__(self):
        self.called_with_type = None
        self.called_function_name = None
        self.called_raw = None

    def begin(self): ...
    def commit(self): ...
    def rollback(self): ...

    def _call_function_with_type(self, obj, function_name):
        self.called_with_type = obj
        self.called_function_name = function_name
        # retorna objeto compatível com DTO
        return [
            {
                "classificacao": getattr(obj, "id", None),
                "codigo": getattr(obj, "codigo", None) or "COD",
                "descricao_func": getattr(obj, "descricao_func", None) or "DESC",
            }
        ]

    def _call_function_raw(self, name, positional, named):
        self.called_raw = (name, positional, named)
        return []

    def delete(self, *_args, **_kwargs): ...
    def _delete_related_lists(self, *_args, **_kwargs): ...


class FakeInjector:
    def db_adapter(self):
        return None


from nsj_rest_lib.dto.dto_base import DTOBase


@DTO()
class CFDTO(DTOBase):
    id: uuid.UUID = DTOField(pk=True, entity_field="classificacao")
    codigo: str = DTOField()
    descricao: str = DTOField(insert_function_field="descricao_func")
    grupoempresarial: uuid.UUID = DTOField()


@Entity(
    table_name="teste.classificacoesfinanceiras",
    pk_field="classificacao",
    default_order_fields=["classificacao"],
)
class CFEntity(EntityBase):
    classificacao: uuid.UUID = EntityField()
    codigo: str = EntityField()


@GetFunctionType(type_name="teste.tcf_get")
class CFGetType(GetFunctionTypeBase):
    id: uuid.UUID = FunctionField(pk=True, type_field_name="classificacao")
    codigo: str = FunctionField()
    descricao_func: str = FunctionField()


@ListFunctionType(type_name="teste.tcf_list")
class CFListType(ListFunctionTypeBase):
    grupoempresarial: uuid.UUID = FunctionField(pk=True)
    codigo: str = FunctionField()


@DeleteFunctionType(type_name="teste.tcf_delete")
class CFDeleteType(DeleteFunctionTypeBase):
    id: uuid.UUID = FunctionField(pk=True, type_field_name="classificacao")
    grupoempresarial: uuid.UUID = FunctionField()


def _build_service(dao: FakeDAO):
    return ServiceBase(
        FakeInjector(),
        dao,
        CFDTO,
        CFEntity,
        get_function_type_class=CFGetType,
        list_function_type_class=CFListType,
        delete_function_type_class=CFDeleteType,
        get_function_name="teste.fn_cf_get",
        list_function_name="teste.fn_cf_list",
        delete_function_name="teste.fn_cf_delete",
    )


def test_get_by_function_sets_pk_and_calls_with_name():
    dao = FakeDAO()
    service = _build_service(dao)

    dto = service.get(
        "abc",
        partition_fields={},
        fields={"root": set()},
        function_object=CFGetType.build_from_params({}, id_value="abc"),
    )

    assert isinstance(dao.called_with_type, CFGetType)
    assert dao.called_with_type.id == "abc"
    assert dao.called_function_name == "teste.fn_cf_get"
    assert dto.codigo == "COD"
    assert dto.descricao == "DESC"


def test_list_by_function_builds_from_params():
    dao = FakeDAO()
    service = _build_service(dao)

    dto_list = service.list(
        after=None,
        limit=None,
        fields={"root": set()},
        order_fields=None,
        filters={},
        function_object=CFListType.build_from_params({"grupoempresarial": "grp"}),
    )

    assert isinstance(dao.called_with_type, CFListType)
    assert dao.called_function_name == "teste.fn_cf_list"
    assert dao.called_with_type.grupoempresarial == "grp"
    assert len(dto_list) == 1
    assert dto_list[0].codigo == "COD"


def test_delete_by_function_requires_pk_and_calls_name():
    dao = FakeDAO()
    service = _build_service(dao)

    fo = CFDeleteType.build_from_params({"grupoempresarial": "grp"}, id_value="delid")
    service.delete(
        id="delid",
        additional_filters=None,
        function_object=fo,
    )

    assert isinstance(dao.called_with_type, CFDeleteType)
    assert dao.called_function_name == "teste.fn_cf_delete"
    assert dao.called_with_type.id == "delid"
    assert dao.called_with_type.grupoempresarial == "grp"
