import base64
import json

from flask import g, request

from nsj_rest_lib.settings import DATABASE_USER


def _decode_jwt_payload(token: str):
    parts = token.split(".")
    if len(parts) < 2:
        return None

    payload_b64 = parts[1]
    padding = "=" * (-len(payload_b64) % 4)
    try:
        payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None

    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return None

    return payload if isinstance(payload, dict) else None


def get_db_user():
    """
    Resolve o usuário do banco para auditoria.

    Ordem de tentativa:
    1) g.external_database["user"] quando definido.
    2) fallback para DATABASE_USER (settings.py).
    """
    external_database = getattr(g, "external_database", None)
    if isinstance(external_database, dict):
        external_user = external_database.get("user")
        if external_user:
            return external_user

    return DATABASE_USER


def get_actor_user_id():
    """
    Resolve o identificador do usuário para auditoria.

    Ordem de tentativa:
    1) g.profile["email"] quando definido.
    2) Authorization Bearer: extrai "email" do payload JWT.
    3) Authorization Basic: usa o usuário antes do ":" após base64.
       Retorna f"sistema2_{id_sistema}".
    4) X-API-Key ou apiKey: trata como JWT e usa "sistema" -> "id_sistema".
       Retorna f"sistema_{id_sistema}".
    5) fallback para o usuário do banco (get_db_user).
    """
    profile = getattr(g, "profile", None)
    if isinstance(profile, dict):
        email = profile.get("email")
        if email:
            return email

    authorization = request.headers.get("Authorization")
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if value:
            scheme_lower = scheme.lower()
            if scheme_lower == "bearer":
                payload = _decode_jwt_payload(value)
                if payload and payload.get("email"):
                    return payload.get("email")
            elif scheme_lower == "basic":
                try:
                    decoded = base64.b64decode(value).decode("utf-8")
                except (ValueError, UnicodeDecodeError):
                    decoded = ""
                if decoded:
                    return f"sistema2_{decoded.split(':', 1)[0]}"

    api_key = request.headers.get("X-API-Key") or request.headers.get("apiKey")
    if api_key:
        payload = _decode_jwt_payload(api_key)
        if payload:
            sistema = payload.get("sistema")
            if isinstance(sistema, dict):
                id_sistema = sistema.get("id_sistema")
            else:
                id_sistema = sistema
            if id_sistema is not None:
                return f"sistema_{id_sistema}"

    return get_db_user()
