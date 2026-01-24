import uuid

from flask import Flask, g

from nsj_rest_lib.decorator.dto import DTO
from nsj_rest_lib.decorator.entity import Entity
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.exception import NotFoundException
from nsj_rest_lib.entity.function_type_base import (
    InsertFunctionTypeBase,
    UpdateFunctionTypeBase,
)
from nsj_rest_lib.descriptor.function_field import FunctionField
from nsj_rest_lib.service.service_base import ServiceBase
from nsj_rest_lib.service import service_base_audit


@DTO()
class DummyDTO(DTOBase):
    id: uuid.UUID = DTOField(pk=True)
    nome: str = DTOField()


@Entity(table_name="dummy", pk_field="id", default_order_fields=["id"])
class DummyEntity(EntityBase):
    id: uuid.UUID = None
    nome: str = None


class FakeDBAdapter:
    def in_transaction(self):
        return True


class FakeDAO:
    def __init__(self):
        self._db = FakeDBAdapter()

    def begin(self):
        return None

    def commit(self):
        return None

    def rollback(self):
        return None

    def get(self, *args, **kwargs):
        raise NotFoundException("not found")

    def insert(self, entity, sql_read_only_fields=None):
        return entity

    def update(self, *args, **kwargs):
        return args[2]

    def delete(self, *args, **kwargs):
        return None


class FakeDAOUpdate(FakeDAO):
    def __init__(self, old_nome: str = "Antigo"):
        super().__init__()
        self.old_nome = old_nome

    def get(self, *args, **kwargs):
        entity_id = args[1] if len(args) > 1 else None
        entity = DummyEntity()
        entity.id = entity_id
        entity.nome = self.old_nome
        return entity


class DummyUpdateFunction(UpdateFunctionTypeBase):
    fields_map = {
        "id": FunctionField(pk=True),
        "nome": FunctionField(),
    }
    type_name = "dummy_update_type"
    function_name = "dummy_update"


class DummyInsertFunction(InsertFunctionTypeBase):
    fields_map = {
        "id": FunctionField(pk=True),
        "nome": FunctionField(),
    }
    type_name = "dummy_insert_type"
    function_name = "dummy_insert"


class FakeInjector:
    def db_adapter(self):
        return FakeDBAdapter()


def test_outbox_insert_called_on_insert(monkeypatch):
    app = Flask(__name__)
    captured = {}

    class FakeAuditDAO:
        def __init__(self, *args, **kwargs):
            return None

        def insert_outbox(self, payload):
            captured["payload"] = payload

    monkeypatch.setattr(service_base_audit, "DAOBaseAudit", FakeAuditDAO)
    monkeypatch.setattr(service_base_audit, "AUDIT_OUTBOX_TRANSACTION", True)

    service = ServiceBase(FakeInjector(), FakeDAO(), DummyDTO, DummyEntity)

    tenant_id = 7
    grupo_empresarial_id = uuid.uuid4()
    area_atendimento_id = uuid.uuid4()
    request_id = uuid.uuid4()

    dto = DummyDTO(id=uuid.uuid4(), nome="Ana")
    with app.test_request_context("/dummy", method="POST", json={"nome": "Ana"}):
        g.request_id = request_id
        g.audit_tenant_id = tenant_id
        g.audit_grupo_empresarial_id = grupo_empresarial_id
        g.audit_area_atendimento_id = area_atendimento_id
        g.audit_params_normalizados = {"body": {"nome": "Ana"}}
        g.profile = {"email": "user@example.com"}

        service.insert(dto)

    payload = captured["payload"]
    assert payload["action"] == "insert"
    assert payload["tenant_id"] == tenant_id
    assert payload["grupo_empresarial_id"] == str(grupo_empresarial_id)
    assert payload["area_atendimento_id"] == str(area_atendimento_id)
    assert payload["request_id"] == request_id
    assert payload["user_id"] == "user@example.com"
    assert payload["resource_type"] == "dummy"
    assert payload["resource_id"] == dto.id
    assert payload["commit_json"]["nome"] == "Ana"


def test_outbox_insert_called_on_delete(monkeypatch):
    app = Flask(__name__)
    captured = {}

    class FakeAuditDAO:
        def __init__(self, *args, **kwargs):
            return None

        def insert_outbox(self, payload):
            captured["payload"] = payload

    monkeypatch.setattr(service_base_audit, "DAOBaseAudit", FakeAuditDAO)
    monkeypatch.setattr(service_base_audit, "AUDIT_OUTBOX_TRANSACTION", True)

    service = ServiceBase(FakeInjector(), FakeDAO(), DummyDTO, DummyEntity)

    request_id = uuid.uuid4()
    with app.test_request_context("/dummy", method="DELETE"):
        g.request_id = request_id
        g.audit_tenant_id = 7
        g.audit_grupo_empresarial_id = uuid.uuid4()
        g.profile = {"email": "user@example.com"}

        service.delete(uuid.uuid4())

    payload = captured["payload"]
    assert payload["action"] == "delete"
    assert payload["request_id"] == request_id


def test_outbox_insert_called_on_update(monkeypatch):
    app = Flask(__name__)
    captured = {}

    class FakeAuditDAO:
        def __init__(self, *args, **kwargs):
            return None

        def insert_outbox(self, payload):
            captured["payload"] = payload

    monkeypatch.setattr(service_base_audit, "DAOBaseAudit", FakeAuditDAO)
    monkeypatch.setattr(service_base_audit, "AUDIT_OUTBOX_TRANSACTION", True)

    service = ServiceBase(FakeInjector(), FakeDAOUpdate(), DummyDTO, DummyEntity)

    request_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    dto = DummyDTO(id=entity_id, nome="Novo")
    with app.test_request_context(f"/dummy/{entity_id}", method="PUT"):
        g.request_id = request_id
        g.audit_tenant_id = 7
        g.audit_grupo_empresarial_id = uuid.uuid4()
        g.profile = {"email": "user@example.com"}

        service.update(dto, id=entity_id)

    payload = captured["payload"]
    assert payload["action"] == "update"
    assert payload["resource_type"] == "dummy"
    assert payload["resource_id"] == entity_id
    assert payload["commit_json"]["nome"]["old"] == "Antigo"
    assert payload["commit_json"]["nome"]["new"] == "Novo"


def test_outbox_insert_called_on_partial_update(monkeypatch):
    app = Flask(__name__)
    captured = {}

    class FakeAuditDAO:
        def __init__(self, *args, **kwargs):
            return None

        def insert_outbox(self, payload):
            captured["payload"] = payload

    monkeypatch.setattr(service_base_audit, "DAOBaseAudit", FakeAuditDAO)
    monkeypatch.setattr(service_base_audit, "AUDIT_OUTBOX_TRANSACTION", True)

    service = ServiceBase(FakeInjector(), FakeDAOUpdate(), DummyDTO, DummyEntity)

    request_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    dto = DummyDTO(id=entity_id, nome="Parcial")
    with app.test_request_context(f"/dummy/{entity_id}", method="PATCH"):
        g.request_id = request_id
        g.audit_tenant_id = 7
        g.audit_grupo_empresarial_id = uuid.uuid4()
        g.profile = {"email": "user@example.com"}

        service.partial_update(dto, id=entity_id)

    payload = captured["payload"]
    assert payload["action"] == "update"
    assert payload["resource_type"] == "dummy"
    assert payload["resource_id"] == entity_id
    assert payload["commit_json"]["nome"]["old"] == "Antigo"
    assert payload["commit_json"]["nome"]["new"] == "Parcial"


def test_outbox_insert_called_on_update_by_function(monkeypatch):
    app = Flask(__name__)
    captured = {}

    class FakeAuditDAO:
        def __init__(self, *args, **kwargs):
            return None

        def insert_outbox(self, payload):
            captured["payload"] = payload

    class FakeDAOFunction(FakeDAOUpdate):
        def update_by_function(self, *args, **kwargs):
            return {"status": "ok"}

    monkeypatch.setattr(service_base_audit, "DAOBaseAudit", FakeAuditDAO)
    monkeypatch.setattr(service_base_audit, "AUDIT_OUTBOX_TRANSACTION", True)

    service = ServiceBase(
        FakeInjector(),
        FakeDAOFunction(),
        DummyDTO,
        DummyEntity,
        update_function_type_class=DummyUpdateFunction,
    )

    request_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    dto = DummyDTO(id=entity_id, nome="Func")
    with app.test_request_context(f"/dummy/{entity_id}", method="PUT"):
        g.request_id = request_id
        g.audit_tenant_id = 7
        g.audit_grupo_empresarial_id = uuid.uuid4()
        g.profile = {"email": "user@example.com"}

        service.update(dto, id=entity_id, function_name="dummy_update")

    payload = captured["payload"]
    assert payload["action"] == "update"
    assert payload["resource_type"] == "dummy"
    assert payload["resource_id"] == entity_id


def test_outbox_insert_called_on_insert_by_function(monkeypatch):
    app = Flask(__name__)
    captured = {}

    class FakeAuditDAO:
        def __init__(self, *args, **kwargs):
            return None

        def insert_outbox(self, payload):
            captured["payload"] = payload

    class FakeDAOFunction(FakeDAO):
        def insert_by_function(self, *args, **kwargs):
            return {"status": "ok"}

    monkeypatch.setattr(service_base_audit, "DAOBaseAudit", FakeAuditDAO)
    monkeypatch.setattr(service_base_audit, "AUDIT_OUTBOX_TRANSACTION", True)

    service = ServiceBase(
        FakeInjector(),
        FakeDAOFunction(),
        DummyDTO,
        DummyEntity,
        insert_function_type_class=DummyInsertFunction,
    )

    request_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    dto = DummyDTO(id=entity_id, nome="FuncInsert")
    with app.test_request_context("/dummy", method="POST"):
        g.request_id = request_id
        g.audit_tenant_id = 7
        g.audit_grupo_empresarial_id = uuid.uuid4()
        g.profile = {"email": "user@example.com"}

        service.insert(dto, function_name="dummy_insert")

    payload = captured["payload"]
    assert payload["action"] == "insert"
    assert payload["resource_type"] == "dummy"
    assert payload["resource_id"] == entity_id


def test_outbox_insert_called_on_delete_by_function(monkeypatch):
    app = Flask(__name__)
    captured = {}

    class FakeAuditDAO:
        def __init__(self, *args, **kwargs):
            return None

        def insert_outbox(self, payload):
            captured["payload"] = payload

    class FakeDAOFunction(FakeDAO):
        def _call_function_raw(self, *args, **kwargs):
            return []

    monkeypatch.setattr(service_base_audit, "DAOBaseAudit", FakeAuditDAO)
    monkeypatch.setattr(service_base_audit, "AUDIT_OUTBOX_TRANSACTION", True)

    service = ServiceBase(FakeInjector(), FakeDAOFunction(), DummyDTO, DummyEntity)

    request_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    with app.test_request_context(f"/dummy/{entity_id}", method="DELETE"):
        g.request_id = request_id
        g.audit_tenant_id = 7
        g.audit_grupo_empresarial_id = uuid.uuid4()
        g.profile = {"email": "user@example.com"}

        service.delete(entity_id, function_name="dummy_delete")

    payload = captured["payload"]
    assert payload["action"] == "delete"
    assert payload["resource_type"] == "dummy"
    assert payload["resource_id"] == entity_id
