import json

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
    assert len(fake_redis.calls) == 1

    event = fake_redis.calls[0]["fields"]
    params_normalizados = json.loads(event["params_normalizados"])
    assert params_normalizados["query_args"] == {"foo": "bar"}
    assert params_normalizados["body"] == {"nome": "Ana"}
    assert params_normalizados["path_args"] == {"id": "123"}
    assert event["actor_user_id"] == "user@example.com"
    assert event["db_user"] == "db_user"
