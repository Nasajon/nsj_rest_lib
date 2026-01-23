import hashlib
import json

from typing import Any


def parse_status_code(status_value: Any) -> int | None:
    if isinstance(status_value, int):
        return status_value
    if isinstance(status_value, str):
        for part in status_value.split():
            if part.isdigit():
                return int(part)
    return None


def parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y"}
    return None


def unpack_response(response: Any) -> tuple[Any, int]:
    if response is None:
        return None, 500

    body = response
    http_status = None

    if isinstance(response, tuple):
        if response:
            body = response[0]
        if len(response) > 1:
            http_status = parse_status_code(response[1])
        if http_status is None and len(response) > 2:
            http_status = parse_status_code(response[2])
    elif hasattr(response, "status_code"):
        http_status = getattr(response, "status_code", None)
        if hasattr(response, "get_data"):
            body = response.get_data(as_text=True)

    if http_status is None:
        http_status = 200

    return body, http_status


def normalize_response_body(body: Any) -> tuple[str, Any | None]:
    body_json = None
    if isinstance(body, (dict, list)):
        body_json = body
        body_text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    elif isinstance(body, bytes):
        body_text = body.decode("utf-8", errors="replace")
    elif isinstance(body, str):
        body_text = body
    elif body is None:
        body_text = ""
    else:
        body_text = str(body)

    if body_json is None and body_text:
        trimmed = body_text.lstrip()
        if trimmed.startswith("{") or trimmed.startswith("["):
            try:
                body_json = json.loads(body_text)
            except json.JSONDecodeError:
                body_json = None

    return body_text, body_json


def mask_sensitive_data(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(token in key_text for token in ("password", "senha", "pass", "secret")):
                sanitized[key] = "******"
            else:
                sanitized[key] = mask_sensitive_data(item)
        return sanitized
    if isinstance(value, list):
        return [mask_sensitive_data(item) for item in value]
    return value


def sanitize_payload(raw_body: str) -> str:
    trimmed = raw_body.lstrip()
    if trimmed.startswith("{") or trimmed.startswith("["):
        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError:
            return raw_body
        sanitized = mask_sensitive_data(parsed)
        return json.dumps(sanitized, ensure_ascii=False, separators=(",", ":"))
    return raw_body


def extract_error_payload(body_json: Any) -> dict | None:
    if isinstance(body_json, list):
        for item in body_json:
            if isinstance(item, dict):
                return item
        return None
    if isinstance(body_json, dict):
        return body_json
    return None


def hash_message(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()


def extract_error_info(
    http_status: int,
    body_json: Any,
    body_text: str,
) -> tuple[str, str, str]:
    if http_status < 400:
        return "", "", ""

    # TODO Refatorar para MULTI STATUS no futuro
    error_payload = extract_error_payload(body_json)
    error_code = ""
    error_message_short = ""
    error_fingerprint = ""

    if isinstance(error_payload, dict):
        error_code = error_payload.get("code") or error_payload.get("error_code") or ""
        message = (
            error_payload.get("message")
            or error_payload.get("error_message_short")
            or error_payload.get("mensagem")
            or error_payload.get("error")
            or ""
        )
        error_message_short = message
        payload_text = json.dumps(
            error_payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        error_fingerprint = hash_message(payload_text)

    if not error_message_short and body_text:
        error_message_short = body_text.strip()

    if error_message_short:
        error_message_short = error_message_short[:255]

    if not error_fingerprint:
        if error_code:
            error_fingerprint = str(error_code)
        elif error_message_short:
            error_fingerprint = hash_message(error_message_short)

    return str(error_code or ""), error_message_short, error_fingerprint
