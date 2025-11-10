from nsj_rest_lib.dao.dao_base_insert_by_function import DAOBaseInsertByFunction
from nsj_rest_lib.decorator.dto import DTO
from nsj_rest_lib.decorator.entity import Entity
from nsj_rest_lib.decorator.insert_function_type import InsertFunctionType
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.descriptor.dto_list_field import DTOListField
from nsj_rest_lib.descriptor.dto_one_to_one_field import (
    DTOOneToOneField,
    OTORelationType,
)
from nsj_rest_lib.descriptor.insert_function_relation_field import (
    InsertFunctionRelationField,
)
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


@InsertFunctionType(type_name="teste.tendereco", function_name="teste.fn_endereco")
class AddressInsertType(InsertFunctionTypeBase):
    rua: str = InsertFunctionField()
    numero: str = InsertFunctionField()


@InsertFunctionType(type_name="teste.tdocumento", function_name="teste.fn_documento")
class DocumentInsertType(InsertFunctionTypeBase):
    numero: str = InsertFunctionField()
    tipo: str = InsertFunctionField()


@InsertFunctionType(
    type_name="teste.tcliente_relacionado",
    function_name="teste.fn_cliente_relacionado",
)
class CustomerWithRelationsInsertType(InsertFunctionTypeBase):
    nome: str = InsertFunctionField()
    enderecos: list[AddressInsertType] = InsertFunctionRelationField()
    documento: DocumentInsertType = InsertFunctionRelationField()


@DTO()
class AddressDTO(DTOBase):
    rua: str = DTOField()
    numero: str = DTOField()


@DTO()
class DocumentDTO(DTOBase):
    numero: str = DTOField()
    tipo: str = DTOField()


@DTO()
class CustomerWithRelationsDTO(DTOBase):
    nome: str = DTOField()

    enderecos: list[AddressDTO] = DTOListField(
        dto_type=AddressDTO,
        entity_type=DummyEntity,
        related_entity_field="cliente_id",
        insert_function_field="enderecos",
        insert_function_type=AddressInsertType,
    )

    documento: DocumentDTO = DTOOneToOneField(
        entity_type=DummyEntity,
        relation_type=OTORelationType.COMPOSITION,
        insert_function_field="documento",
        insert_function_type=DocumentInsertType,
    )


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


def test_build_insert_function_type_object_with_relations():
    service = ServiceBase(
        FakeInjector(),
        DummyDAO(),
        CustomerWithRelationsDTO,
        DummyEntity,
        insert_function_type_class=CustomerWithRelationsInsertType,
    )

    dto = CustomerWithRelationsDTO()
    dto.nome = "Cliente Teste"

    addr1 = AddressDTO()
    addr1.rua = "Rua A"
    addr1.numero = "10"

    addr2 = AddressDTO()
    addr2.rua = "Rua B"
    addr2.numero = "20"

    dto.enderecos = [addr1, addr2]

    document = DocumentDTO()
    document.numero = "123"
    document.tipo = "CPF"
    dto.documento = document

    insert_object = service._build_insert_function_type_object(dto)

    assert insert_object.nome == "Cliente Teste"
    assert isinstance(insert_object.enderecos, list)
    assert len(insert_object.enderecos) == 2
    assert all(
        isinstance(item, AddressInsertType) for item in insert_object.enderecos
    )
    assert insert_object.enderecos[0].rua == "Rua A"
    assert insert_object.enderecos[1].numero == "20"
    assert isinstance(insert_object.documento, DocumentInsertType)
    assert insert_object.documento.numero == "123"


def test_sql_insert_function_type_with_relations():
    dao = DAOBaseInsertByFunction(None, DummyEntity)

    insert_object = CustomerWithRelationsInsertType()
    insert_object.nome = "Cliente SQL"

    endereco_insert = AddressInsertType()
    endereco_insert.rua = "Rua SQL"
    endereco_insert.numero = "99"
    insert_object.enderecos = [endereco_insert]

    document_insert = DocumentInsertType()
    document_insert.numero = "321"
    document_insert.tipo = "CNPJ"
    insert_object.documento = document_insert

    declarations, assignments, values_map = dao._sql_insert_function_type(
        insert_object
    )

    assert "VAR_ROOT_ENDERECOS_0 teste.tendereco;" in declarations
    assert "VAR_ROOT_DOCUMENTO teste.tdocumento;" in declarations

    assert "VAR_TIPO.nome = :root_nome;" in assignments
    assert "VAR_TIPO.enderecos = ARRAY[]::teste.tendereco[];" in assignments
    assert (
        "VAR_ROOT_ENDERECOS_0.rua = :root_enderecos_0_rua;" in assignments
    )
    assert (
        "VAR_TIPO.enderecos = array_append(VAR_TIPO.enderecos, VAR_ROOT_ENDERECOS_0);"
        in assignments
    )
    assert "VAR_TIPO.documento = VAR_ROOT_DOCUMENTO;" in assignments

    assert values_map["root_nome"] == "Cliente SQL"
    assert values_map["root_enderecos_0_rua"] == "Rua SQL"
    assert values_map["root_documento_numero"] == "321"
