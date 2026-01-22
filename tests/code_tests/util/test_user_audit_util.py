import base64
import json

from flask import Flask, g

from nsj_rest_lib.util.user_audit_util import get_actor_user_id, get_db_user


def _make_jwt(payload):
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
    return f"hdr.{payload_b64}.sig"


def test_get_db_user_prefers_external_database(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(
        "nsj_rest_lib.util.user_audit_util.DATABASE_USER",
        "db_default",
    )
    with app.test_request_context("/"):
        g.external_database = {"user": "external_user"}
        assert get_db_user() == "external_user"


def test_get_db_user_fallbacks_to_settings(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(
        "nsj_rest_lib.util.user_audit_util.DATABASE_USER",
        "db_default",
    )
    with app.test_request_context("/"):
        g.external_database = None
        assert get_db_user() == "db_default"


def test_get_actor_user_id_from_profile():
    app = Flask(__name__)
    with app.test_request_context("/", headers={"Authorization": "Bearer x"}):
        g.profile = {"email": "profile@example.com"}
        assert get_actor_user_id() == "profile@example.com"


def test_get_actor_user_id_from_bearer():
    app = Flask(__name__)
    token = _make_jwt({"email": "jwt@example.com"})
    with app.test_request_context("/", headers={"Authorization": f"Bearer {token}"}):
        g.profile = None
        assert get_actor_user_id() == "jwt@example.com"


def test_get_actor_user_id_from_basic():
    app = Flask(__name__)
    basic = base64.b64encode(b"user:pass").decode("utf-8")
    with app.test_request_context("/", headers={"Authorization": f"Basic {basic}"}):
        g.profile = None
        assert get_actor_user_id() == "sistema2_user"


def test_get_actor_user_id_from_api_key():
    app = Flask(__name__)
    token = _make_jwt({"sistema": {"id_sistema": 42}})
    with app.test_request_context("/", headers={"X-API-Key": token}):
        g.profile = None
        assert get_actor_user_id() == "sistema_42"


def test_get_actor_user_id_fallback_db_user(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(
        "nsj_rest_lib.util.user_audit_util.DATABASE_USER",
        "db_default",
    )
    with app.test_request_context("/"):
        g.profile = None
        g.external_database = None
        assert get_actor_user_id() == "db_default"
