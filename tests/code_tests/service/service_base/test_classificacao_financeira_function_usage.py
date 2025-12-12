import uuid

from nsj_rest_lib.decorator.dto import DTO
from nsj_rest_lib.decorator.entity import Entity
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.descriptor.entity_field import EntityField
from nsj_rest_lib.service.service_base import ServiceBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.entity.function_type_base import ListFunctionTypeBase
from nsj_rest_lib.decorator.list_function_type import ListFunctionType
from nsj_rest_lib.descriptor.function_field import FunctionField


class FakeDAO:
    def __init__(self):
        self.called_with_type = None
        self.called_function_name = None
        self.called_raw = None

    def begin(self): ...
    def commit(self): ...
    def rollback(self): ...

    def _call_function_raw(self, name, positional, named):
        self.called_raw = (name, positional, named)
        # retorna objeto compatível com CFDTO via GET/LIST (campos com nomes de DTO)
        return [
            {
                "id": None,
                "codigo": "COD",
                "descricao": "DESC",
            }
        ]

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


@ListFunctionType(type_name="teste.tcf_list")
class CFListType(ListFunctionTypeBase):
    grupoempresarial: uuid.UUID = FunctionField(pk=True)
    codigo: str = FunctionField()
    descricao: str = FunctionField(type_field_name="descricao_func")


@DTO()
class CFListParams(DTOBase):
    grupoempresarial: uuid.UUID = DTOField()


def _build_service(dao: FakeDAO):
    return ServiceBase(
        FakeInjector(),
        dao,
        CFDTO,
        CFEntity,
        get_function_name="teste.fn_cf_get",
        list_function_name="teste.fn_cf_list",
        delete_function_name="teste.fn_cf_delete",
    )


def test_list_by_function_builds_from_params():
    dao = FakeDAO()
    service = _build_service(dao)

    import uuid as _uuid
    grupo = _uuid.uuid4()
    params_dto = CFListParams(grupoempresarial=grupo)

    dto_list = service.list(
        after=None,
        limit=None,
        fields={"root": set()},
        order_fields=None,
        filters={},
        function_object=params_dto,
        function_name="teste.fn_cf_list",
    )

    assert dao.called_raw[0] == "teste.fn_cf_list"
    assert dao.called_raw[2]["grupoempresarial"] == grupo
    assert len(dto_list) == 1
    assert dto_list[0].codigo == "COD"
