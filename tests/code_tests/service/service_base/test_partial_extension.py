from unittest.mock import Mock

from nsj_rest_lib.decorator.dto import DTO
from nsj_rest_lib.decorator.entity import Entity
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.service.service_base import ServiceBase


@Entity(
    table_name="produto",
    pk_field="id",
    default_order_fields=["id"],
)
class ProdutoEntity(EntityBase):
    id: int = None
    codigo: str = None


@DTO()
class ProdutoDTO(DTOBase):
    id: int = DTOField(pk=True, resume=True)
    codigo: str = DTOField(resume=True)


@Entity(
    partial_of=ProdutoEntity,
    partial_table_name="farmaco",
)
class FarmacoEntity(EntityBase):
    id_produto: int = None
    registro_anvisa: str = None


@DTO(
    partial_of={
        "dto": ProdutoDTO,
        "relation_field": "id_produto",
        "related_entity_field": "id",
    }
)
class FarmacoDTO(DTOBase):
    id_produto: int = DTOField()
    registro_anvisa: str = DTOField()


def build_service_with_mock():
    dao = Mock()
    dao.list.return_value = []
    dao.get.return_value = FarmacoEntity()
    return ServiceBase(None, dao, FarmacoDTO, FarmacoEntity), dao


def test_partial_list_without_extension_fields_uses_exists_and_no_join():
    service, dao = build_service_with_mock()

    service.list(
        after=None,
        limit=None,
        fields={"root": set()},
        order_fields=None,
        filters={},
    )

    assert dao.list.call_count == 1
    args, kwargs = dao.list.call_args
    joins_aux = kwargs.get("joins_aux")
    assert joins_aux == [] or all(join.alias != "partial_join" for join in joins_aux)
    assert kwargs.get("partial_exists_clause") == ("farmaco", "id", "id_produto")


def test_partial_list_with_extension_field_triggers_join():
    service, dao = build_service_with_mock()

    service.list(
        after=None,
        limit=None,
        fields={"root": {"registro_anvisa"}},
        order_fields=None,
        filters={},
    )

    args, kwargs = dao.list.call_args
    joins_aux = kwargs.get("joins_aux")
    assert joins_aux is not None
    assert any(join.alias == "partial_join" for join in joins_aux)
    assert kwargs.get("partial_exists_clause") is None

    entity_fields = args[2]
    assert "registro_anvisa" not in entity_fields


def test_partial_order_field_triggers_join_and_alias():
    service, dao = build_service_with_mock()

    service.list(
        after=None,
        limit=None,
        fields={"root": set()},
        order_fields=["registro_anvisa desc"],
        filters={},
    )

    args, kwargs = dao.list.call_args
    joins_aux = kwargs.get("joins_aux")
    assert joins_aux is not None
    assert any(join.alias == "partial_join" for join in joins_aux)
    assert kwargs.get("partial_exists_clause") is None

    order_fields = args[3]
    assert "partial_join.registro_anvisa desc" in order_fields
