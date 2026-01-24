from typing import Any, Dict, Set


def build_fields_tree(dto: Any) -> Dict[str, Set[str]]:
    root_fields: Set[str] = set()
    for attr in (
        "fields_map",
        "list_fields_map",
        "object_fields_map",
        "one_to_one_fields_map",
        "aggregator_fields_map",
        "sql_join_fields_map",
        "left_join_fields_map",
    ):
        fields_map = getattr(dto, attr, None)
        if isinstance(fields_map, dict):
            root_fields |= set(fields_map.keys())
    return {"root": root_fields}


def build_expands_tree(dto: Any) -> Dict[str, Set[str]]:
    expands_root: Set[str] = set()
    one_to_one_fields = getattr(dto, "one_to_one_fields_map", None)
    if isinstance(one_to_one_fields, dict):
        expands_root |= set(one_to_one_fields.keys())
    return {"root": expands_root}


def convert_dto_full(dto: Any) -> Any:
    if hasattr(dto, "convert_to_dict") and callable(dto.convert_to_dict):
        fields_tree = build_fields_tree(dto)
        expands_tree = build_expands_tree(dto)
        return dto.convert_to_dict(fields_tree, expands_tree)
    return dto
