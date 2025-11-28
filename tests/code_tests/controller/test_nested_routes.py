from nsj_rest_lib.controller.get_route import GetRoute
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.descriptor.dto_list_field import DTOListField
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase


class ParentEntity(EntityBase):
    pk_field = "id"
    fields_map = {}


class ChildEntity(EntityBase):
    pk_field = "id"
    fields_map = {}


class GrandChildEntity(EntityBase):
    pk_field = "id"
    fields_map = {}


class GrandChildDTO(DTOBase):
    pk_field = "id"
    fields_map = {
        "id": DTOField(pk=True),
        "child_id": DTOField(entity_field="child_id"),
    }
    partition_fields = set()
    resume_fields = set()
    list_fields_map = {}
    object_fields_map = {}
    one_to_one_fields_map = {}
    sql_join_fields_map = {}
    left_join_fields_map = {}
    data_override_fields = []
    data_override_group = None


class ChildDTO(DTOBase):
    pk_field = "id"
    fields_map = {
        "id": DTOField(pk=True),
        "parent_id": DTOField(entity_field="parent_id"),
    }
    partition_fields = set()
    resume_fields = set()
    list_fields_map = {
        "grandchildren": DTOListField(
            dto_type=GrandChildDTO,
            entity_type=GrandChildEntity,
            related_entity_field="child_id",
        )
    }
    object_fields_map = {}
    one_to_one_fields_map = {}
    sql_join_fields_map = {}
    left_join_fields_map = {}
    data_override_fields = []
    data_override_group = None


class ParentDTO(DTOBase):
    pk_field = "id"
    fields_map = {"id": DTOField(pk=True)}
    partition_fields = set()
    resume_fields = set()
    list_fields_map = {
        "children": DTOListField(
            dto_type=ChildDTO,
            entity_type=ChildEntity,
            related_entity_field="parent_id",
        )
    }
    object_fields_map = {}
    one_to_one_fields_map = {}
    sql_join_fields_map = {}
    left_join_fields_map = {}
    data_override_fields = []
    data_override_group = None


def _build_route(url: str):
    return GetRoute(
        url=url,
        http_method="GET",
        dto_class=ParentDTO,
        entity_class=ParentEntity,
    )


def test_nested_route_resolves_parent_and_child_ids():
    route = _build_route("/parent/<id>/children/<child_id>")

    result = route._resolve_nested_list_field(
        id_value="fallback",
        kwargs={"id": "10", "child_id": "99"},
    )

    assert result is not None
    list_field, parent_id, child_id = result
    assert list_field is ParentDTO.list_fields_map["children"]
    assert parent_id == "10"
    assert child_id == "99"


def test_no_match_when_parent_placeholder_missing():
    route = _build_route("/children/<child_id>")

    result = route._resolve_nested_list_field(
        id_value="fallback",
        kwargs={"child_id": "99"},
    )

    assert result is None


def test_no_match_when_parent_placeholder_not_provided():
    route = _build_route("/parent/<id>/children/<child_id>")

    result = route._resolve_nested_list_field(
        id_value="fallback",
        kwargs={"child_id": "99"},
    )

    assert result is not None
    _, parent_id, child_id = result
    assert parent_id == "fallback"
    assert child_id == "99"


def test_recursive_nested_route_reaches_last_level():
    route = _build_route("/parent/<id>/children/<child_id>/grandchildren/<grand_id>")

    ctx = route._resolve_nested_route_context(
        id_value="base",
        kwargs={"id": "1", "child_id": "2", "grand_id": "3"},
    )

    assert ctx["matched"] is True
    assert ctx["dto_class"].__name__ == "GrandChildDTO"
    assert ctx["entity_class"] is GrandChildEntity
    assert ctx["target_id"] == "3"
    # Deve carregar filtro de relação do nível imediatamente anterior
    assert ctx["relation_filters"] == {"child_id": "2"}
