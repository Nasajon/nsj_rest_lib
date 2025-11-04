from unittest.mock import Mock

from nsj_rest_lib.decorator.dto import DTO
from nsj_rest_lib.decorator.entity import Entity
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.service.service_base import ServiceBase
from nsj_rest_lib.exception import NotFoundException
from nsj_rest_lib.settings import ENV_MULTIDB


@Entity(
    table_name="produto",
    pk_field="id",
    default_order_fields=["id"],
)
class ProdutoEntity(EntityBase):
    id: int = None
    codigo: str = None
    tenant: int = None


@DTO()
class ProdutoDTO(DTOBase):
    id: int = DTOField(pk=True, resume=True)
    codigo: str = DTOField(resume=True)
    tenant: int = DTOField(partition_data=True)


@Entity(
    partial_of=ProdutoEntity,
    partial_table_name="farmaco",
)
class FarmacoEntity(EntityBase):
    id_produto: int = None
    registro_anvisa: str = None
    tenant: int = None


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
    tenant: int = DTOField(partition_data=True)


def build_service_with_mock():
    dao = Mock()
    dao.list.return_value = []
    dao.get.return_value = FarmacoEntity()
    dao.partial_extension_exists = Mock(return_value=False)
    dao.insert_partial_extension_record = Mock()
    dao.update_partial_extension_record = Mock()
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

    order_specs = args[3]
    assert len(order_specs) == 1
    spec = order_specs[0]
    assert spec.source.name == "PARTIAL_EXTENSION"
    assert spec.column == "registro_anvisa"
    assert spec.is_desc is True


def test_partial_insert_saves_extension_record():
    service, dao = build_service_with_mock()

    dao.get.side_effect = NotFoundException("not found")
    dao.insert.side_effect = lambda entity, *_: entity
    dao.partial_extension_exists.return_value = False

    dto = FarmacoDTO(id=1, codigo="PROD-1", tenant=42, registro_anvisa="ABC123")

    service.insert(dto)

    dao.insert.assert_called_once()
    dao.partial_extension_exists.assert_called_once_with(
        "farmaco", "id_produto", 1
    )
    dao.insert_partial_extension_record.assert_called_once()

    insert_args, _ = dao.insert_partial_extension_record.call_args
    assert insert_args[0] == "farmaco"
    payload = insert_args[1]
    assert payload["id_produto"] == 1
    assert payload["registro_anvisa"] == "ABC123"    
    ## Verifica se o campo tenant é incluído ou não conforme a configuração
    if ENV_MULTIDB == "false":
        assert payload["tenant"] == 42


def test_partial_update_updates_extension_record():
    service, dao = build_service_with_mock()

    service.get = Mock(
        return_value=FarmacoDTO(
            id=1, codigo="PROD-1", tenant=42, registro_anvisa="OLD"
        )
    )
    dao.update.side_effect = lambda *args, **kwargs: args[2]
    dao.partial_extension_exists.return_value = True

    dto = FarmacoDTO(id=1, codigo="PROD-1", tenant=42, registro_anvisa="NEW")

    service.update(dto, id=1)

    dao.update.assert_called_once()
    dao.update_partial_extension_record.assert_called_once()
    args_call, _ = dao.update_partial_extension_record.call_args
    assert args_call[0] == "farmaco"
    assert args_call[1] == "id_produto"
    assert args_call[2] == 1
    ## Verifica se o campo tenant é incluído ou não conforme a configuração
    if ENV_MULTIDB == "false":
        assert args_call[3] == {"registro_anvisa": "NEW", "tenant": 42}


def test_partial_patch_updates_only_provided_extension_fields():
    service, dao = build_service_with_mock()

    service.get = Mock(
        return_value=FarmacoDTO(
            id=1, codigo="PROD-1", tenant=42, registro_anvisa="OLD"
        )
    )
    dao.update.side_effect = lambda *args, **kwargs: args[2]
    dao.partial_extension_exists.return_value = True

    dto = FarmacoDTO(id=1, registro_anvisa="PATCHED")

    service.partial_update(dto, id=1)

    dao.update_partial_extension_record.assert_called_once()
    args_call, _ = dao.update_partial_extension_record.call_args
    assert args_call[3] == {"registro_anvisa": "PATCHED"}
