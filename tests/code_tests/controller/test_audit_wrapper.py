import hashlib
import json
import uuid

from flask import Flask, g

from nsj_rest_lib.controller.funtion_route_wrapper import FunctionRouteWrapper
from nsj_rest_lib.controller.route_base import RouteBase
from nsj_rest_lib.decorator.dto import DTO
from nsj_rest_lib.decorator.entity import Entity
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.util.audit_util import AuditUtil


@DTO()
class DummyDTO(DTOBase):
    nome: str = DTOField(resume=True)
    segredo: str = DTOField()


@Entity(table_name="dummy", pk_field="id", default_order_fields=["id"])
class DummyEntity(EntityBase):
    nome: str = None


class DummyFactory:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyRoute(RouteBase):
    def handle_request(self, id: str = None, **kwargs):
        return ("ok", 200, {})


class DummyErrorRoute(RouteBase):
    def handle_request(self, id: str = None, **kwargs):
        return (json.dumps({"code": "E_TEST", "message": "Falha"}), 400, {})


class FakeRedis:
    def __init__(self):
        self.calls = []

    def xadd(self, stream_key, fields, minid=None):
        self.calls.append({"stream_key": stream_key, "fields": fields, "minid": minid})
        return "1-0"


def test_audit_called_with_normalized_params(monkeypatch):
    app = Flask(__name__)
    fake_redis = FakeRedis()

    def fake_init(self, redis_client=None, audit_stream_key="audit-stream"):
        self.redis_client = fake_redis
        self.stream_key = audit_stream_key

    monkeypatch.setattr(AuditUtil, "__init__", fake_init)

    route = DummyRoute(
        url="/items/<id>",
        http_method="POST",
        dto_class=DummyDTO,
        entity_class=DummyEntity,
        injector_factory=DummyFactory,
    )

    wrapper = FunctionRouteWrapper(route, lambda req, resp: resp)

    body = {"nome": "Ana", "segredo": "x", "extra": "y"}
    with app.test_request_context(
        "/items/123?foo=bar",
        method="POST",
        json=body,
    ):
        g.profile = {"email": "user@example.com"}
        g.external_database = {"name": "db1", "user": "db_user"}
        response = wrapper(id="123")

    assert response == ("ok", 200, {})
    assert len(fake_redis.calls) == 2

    started_event = next(
        call["fields"]
        for call in fake_redis.calls
        if call["fields"].get("event_type") == "request_started"
    )
    params_normalizados = json.loads(started_event["params_normalizados"])
    assert params_normalizados["query_args"] == {"foo": "bar"}
    assert params_normalizados["body"] == {"nome": "Ana"}
    assert params_normalizados["path_args"] == {"id": "123"}
    assert started_event["actor_user_id"] == "user@example.com"
    assert started_event["db_user"] == "db_user"


def test_audit_finished_records_error_payload(monkeypatch):
    app = Flask(__name__)
    fake_redis = FakeRedis()

    def fake_init(self, redis_client=None, audit_stream_key="audit-stream"):
        self.redis_client = fake_redis
        self.stream_key = audit_stream_key

    monkeypatch.setattr(AuditUtil, "__init__", fake_init)

    route = DummyErrorRoute(
        url="/items/<id>",
        http_method="POST",
        dto_class=DummyDTO,
        entity_class=DummyEntity,
        injector_factory=DummyFactory,
    )

    wrapper = FunctionRouteWrapper(route, lambda req, resp: resp)

    area_atendimento_id = uuid.uuid4()
    grupo_empresarial_id = uuid.uuid4()
    long_text = "a" * 5000
    body = {
        "aa_password": "123",
        "nome": "Ana",
        "observacao": long_text,
    }

    with app.test_request_context(
        f"/items/123?tenant_id=7&grupo_empresarial_id={grupo_empresarial_id}&area_atendimento_id={area_atendimento_id}",
        method="POST",
        json=body,
    ):
        g.profile = {"email": "user@example.com"}
        g.external_database = {"name": "db1", "user": "db_user"}
        response = wrapper(id="123")

    assert response[1] == 400
    assert len(fake_redis.calls) == 2

    finished_event = next(
        call["fields"]
        for call in fake_redis.calls
        if call["fields"].get("event_type") == "request_finished"
    )
    assert finished_event["http_status"] == "400"
    assert finished_event["tx_attempted"] == "1"
    assert finished_event["db_user"] == "db_user"
    assert finished_event["area_atendimento_id"] == str(area_atendimento_id)
    assert int(finished_event["duration_ms"]) >= 0

    payload_text = json.dumps(
        {"code": "E_TEST", "message": "Falha"},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    expected_fingerprint = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    assert finished_event["error_code"] == "E_TEST"
    assert finished_event["error_message_short"] == "Falha"
    assert finished_event["error_fingerprint"] == expected_fingerprint

    request_json = finished_event.get("request_json")
    assert request_json is not None
    assert "******" in request_json
    assert "123" not in request_json
    assert len(request_json) == 4096
