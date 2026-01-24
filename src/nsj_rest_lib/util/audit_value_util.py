import uuid

from typing import Any


def is_id_segment(segment: str) -> bool:
    if segment.isdigit():
        return True
    try:
        uuid.UUID(segment)
        return True
    except (TypeError, ValueError):
        return False


def coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def coerce_uuid(value: Any, allow_none: bool = False) -> str | None:
    if value is None:
        return None if allow_none else str(uuid.UUID(int=0))
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError):
        return None if allow_none else str(uuid.UUID(int=0))
