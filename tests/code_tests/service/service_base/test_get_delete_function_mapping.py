import pytest

from nsj_rest_lib.decorator.dto import DTO
from nsj_rest_lib.decorator.entity import Entity
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.service.service_base import ServiceBase


class FakeDAO:
    def __init__(self):
        self.called_with_type = None
        self.called_with_type_name = None
        self.called_raw = None

    def begin(self):
        return None

    def commit(self):
        return None

    def rollback(self):
        return None

    def _call_function_with_type(self, obj, function_name=None):
        self.called_with_type = obj
        self.called_with_type_name = function_name
        return [{"id_func": getattr(obj, "id_func", None), "nome_func": "by_type"}]

    def _call_function_raw(self, name, positional, named):
        self.called_raw = (name, positional, named)
        id_value = positional[0] if positional else named.get("id_func")
        return [{"id_func": id_value, "nome_func": "raw"}]

    def delete(self, *_args, **_kwargs):
        return None

    def _delete_related_lists(self, *_args, **_kwargs):
        return None


class FakeInjector:
    def db_adapter(self):
        return None


@DTO()
class DummyDTO(DTOBase):
    id: int = DTOField(
        insert_function_field="id_func",
        get_function_field="id_func",
        delete_function_field="id_func",
    )
    nome: str = DTOField(
        insert_function_field="nome_func",
        get_function_field="nome_func",
        delete_function_field="nome_func",
    )
    motivo: str = DTOField(
        get_function_field="motivo",
        delete_function_field="motivo",
    )

@Entity(table_name="teste.entity", pk_field="id", default_order_fields=["id"])
class DummyEntity(EntityBase):
    id: int
    nome: str


@DTO()
class DummyGetParams(DTOBase):
    pk_field = "id_func"

    id_func: int = DTOField()
    nome_func: str = DTOField()


@DTO()
class DummyListParams(DTOBase):
    id_func: int = DTOField()
    nome_func: str = DTOField()


@DTO()
class DummyDeleteParams(DTOBase):
    pk_field = "id_func"

    id_func: int = DTOField()
    motivo: str = DTOField()


def build_service(dao: FakeDAO):
    return ServiceBase(
        FakeInjector(),
        dao,
        DummyDTO,
        DummyEntity,
        get_function_name="teste.fn_dummy_get",
        list_function_name="teste.fn_dummy_list",
        delete_function_name="teste.fn_dummy_delete",
    )


def test_get_by_function_params_dto_maps_pk_and_result():
    dao = FakeDAO()
    service = build_service(dao)

    params_dto = DummyGetParams(id_func=10)

    dto = service.get(
        10,
        partition_fields={},
        fields={"root": set()},
        function_params=None,
        function_object=params_dto,
        function_name="teste.fn_dummy_get",
    )

    assert dao.called_raw[0] == "teste.fn_dummy_get"
    # sem posicionais quando usamos DTO de parâmetros
    assert dao.called_raw[1] == []
    # pk_field mapeado para id_func nos parâmetros nomeados
    assert dao.called_raw[2]["id_func"] == 10
    assert dto.id == 10
    assert dto.nome == "raw"


def test_get_by_function_raw():
    dao = FakeDAO()
    service = ServiceBase(
        FakeInjector(),
        dao,
        DummyDTO,
        DummyEntity,
        get_function_name="teste.fn_raw",
    )

    dto = service.get(
        7,
        partition_fields={},
        fields={"root": set()},
        function_name="teste.fn_raw",
    )

    assert dao.called_raw[0] == "teste.fn_raw"
    assert dto.id == 7
    assert dto.nome == "raw"


def test_list_by_function_type():
    dao = FakeDAO()
    service = build_service(dao)

    params_dto = DummyListParams(id_func=1, nome_func="x")

    dtos = service.list(
        None,
        None,
        {"root": set()},
        None,
        {},  # filters
        function_object=params_dto,
        function_name="teste.fn_dummy_list",
    )

    assert len(dtos) == 1
    assert dtos[0].nome == "raw"


def test_delete_by_function_type_uses_pk_field():
    dao = FakeDAO()
    service = build_service(dao)

    params_dto = DummyDeleteParams(id_func=99, motivo="x")

    service.delete(
        99,
        additional_filters=None,
        function_object=params_dto,
        function_params=None,
        function_name="teste.fn_dummy_delete",
    )

    assert dao.called_raw[0] == "teste.fn_dummy_delete"
    # positional id
    assert dao.called_raw[1] == [99]
    # pk_field mapeado para id_func nos parâmetros nomeados
    assert dao.called_raw[2]["id_func"] == 99
