from nsj_rest_lib.decorator.dto import DTO
from nsj_rest_lib.decorator.entity import Entity
from nsj_rest_lib.decorator.insert_function_type import InsertFunctionType
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.descriptor.entity_field import EntityField
from nsj_rest_lib.descriptor.insert_function_field import InsertFunctionField
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.entity.insert_function_type_base import InsertFunctionTypeBase
from nsj_rest_lib.service.service_base import ServiceBase


@DTO()
class DummyDTO(DTOBase):
    valor: int = DTOField(insert_function_field="valor_func")

    descricao: str = DTOField(
        insert_function_field="descricao_func",
        convert_to_function=lambda value, dto_values: {
            "descricao_func": value.upper() if value else value,
            "valor_func": (dto_values.get("valor") or 0) + 10,
        },
    )


@Entity(table_name="teste.dummy", pk_field="id", default_order_fields=["id"])
class DummyEntity(EntityBase):
    id: int = EntityField()
    valor: int = EntityField()


@InsertFunctionType(type_name="teste.tdummy", function_name="teste.fn_dummy")
class DummyInsertType(InsertFunctionTypeBase):
    valor_func: int = InsertFunctionField()
    descricao_func: str = InsertFunctionField()


class DummyDAO:
    pass


class FakeInjector:
    def db_adapter(self):
        return None


def test_build_insert_function_type_object_with_mapped_fields():
    service = ServiceBase(
        FakeInjector(),
        DummyDAO(),
        DummyDTO,
        DummyEntity,
        insert_function_type_class=DummyInsertType,
    )

    dto = DummyDTO()
    dto.valor = 2
    dto.descricao = "nova descricao"

    insert_object = service._build_insert_function_type_object(dto)

    assert insert_object.valor_func == 12
    assert insert_object.descricao_func == "NOVA DESCRICAO"
