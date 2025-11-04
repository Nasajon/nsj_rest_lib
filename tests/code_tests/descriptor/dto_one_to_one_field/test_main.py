import uuid
import typing as ty

from nsj_rest_lib.decorator.dto import DTO  # type: ignore
from nsj_rest_lib.descriptor import (  # type: ignore
    DTOField,
    DTOOneToOneField,
    OTORelationType,
)
from nsj_rest_lib.descriptor.dto_left_join_field import EntityRelationOwner # type: ignore
from nsj_rest_lib.dto.dto_base import DTOBase  # type: ignore

from nsj_rest_lib.decorator.entity import Entity  # type: ignore
from nsj_rest_lib.entity.entity_base import EntityBase  # type: ignore

from nsj_rest_lib.dao.dao_base import DAOBase  # type: ignore
from nsj_rest_lib.exception import NotFoundException  # type: ignore
from nsj_rest_lib.service.service_base import ServiceBase  # type: ignore

@Entity(table_name="child_entity", pk_field="a", default_order_fields=["a"])
class ChildEntity(EntityBase):
    a: uuid.UUID = uuid.UUID(int=0)
    pass

@DTO()
class ChildDTO(DTOBase):
    a: int = DTOField(pk=True, resume=True)
    pass

@Entity(table_name="parent_entity", pk_field="b", default_order_fields=["b"])
class ParentEntity(EntityBase):
    b: uuid.UUID = uuid.UUID(int=0)
    child: uuid.UUID = uuid.UUID(int=0)
    pass

@DTO()
class ParentDTO(DTOBase):
    b: int = DTOField(pk=True, resume=True)
    child: ChildDTO = DTOOneToOneField(
        not_null=True,
        entity_type=ChildEntity,
        relation_type=OTORelationType.AGGREGATION,
        field=DTOField(),
    )
    pass


class ParentDAO(DAOBase):
    def __init__(self, da, entity_class):
        super().__init__(db=da, entity_class=entity_class)
        self.count = 10
        pass

    # pylint: disable-next=arguments-differ
    def insert(self, entity: EntityBase, *_, **__):
        return entity

    def begin(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass

    # pylint: disable-next=arguments-differ
    def get(self, *_, **__) -> EntityBase:
        raise NotFoundException("")

    # pylint: disable-next=arguments-differ
    def entity_exists(self, *_, **__):
        return False

    pass


def test_configure() -> None:
    oto_field: DTOOneToOneField = ParentDTO.one_to_one_fields_map['child']
    field: DTOField = ParentDTO.fields_map['child']

    assert oto_field.field is field
    assert oto_field.expected_type is ChildDTO
    pass


def test_insert_uuid() -> None:
    vals: ty.Dict[str, ty.Any] = {
        'child': { 'a': uuid.UUID(int=0xDEADBEEF) }
    }
    dto = ParentDTO(**vals)
    service = ServiceBase(
        injector_factory=None,
        dao=ParentDAO(da=None, entity_class=ParentEntity),
        dto_class=ParentDTO,
        entity_class=ParentEntity,
        dto_post_response_class=ParentDTO,
    )
    dto_response: ParentDTO = service.insert(dto)
    assert dto_response.child == vals['child']['a']
    pass

def test_insert_object() -> None:
    vals: ty.Dict[str, ty.Any] = {
        'child': uuid.UUID(int=0xDEADBEEF)
    }
    dto = ParentDTO(**vals)
    service = ServiceBase(
        injector_factory=None,
        dao=ParentDAO(da=None, entity_class=ParentEntity),
        dto_class=ParentDTO,
        entity_class=ParentEntity,
        dto_post_response_class=ParentDTO,
    )
    dto_response: ParentDTO = service.insert(dto)
    assert dto_response.child == vals['child']
    pass

def test_invalid_entity_type() -> None:
    exp_msg: str = 'Argument `entity_type` of `DTOOneToOneField` HAS to be a'\
        ' `EntityBase`. Is <class \'object\'>.'
    try:
        @DTO()
        class _DTO(DTOBase):
            child: ChildDTO = DTOOneToOneField(
                entity_type=object,
                relation_type=OTORelationType.AGGREGATION,
                field=DTOField()
            )
            pass
    except AssertionError as err:
        if err.args[0] != exp_msg:
            raise err
        pass
    pass

def test_no_annotation() -> None:
    exp_msg: str = "`DTOOneToOneField` with name `child` HAS to have an" \
        " annotation."
    try:
        @DTO()
        class _DTO(DTOBase):
            child = DTOOneToOneField(
                entity_type=ChildEntity,
                relation_type=OTORelationType.AGGREGATION,
                field=DTOField()
            )
            pass
    except AssertionError as err:
        if err.args[0] != exp_msg:
            raise err
        pass
    pass

def test_invalid_expected_type() -> None:
    exp_msg: str = "`DTOOneToOneField` with name `child` annotation's MUST" \
        " be a subclass of `DTOBase`. Is `<class 'object'>`."
    try:
        @DTO()
        class _DTO(DTOBase):
            child: object = DTOOneToOneField(
                entity_type=ChildEntity,
                relation_type=OTORelationType.AGGREGATION,
                field=DTOField()
            )
            pass
    except AssertionError as err:
        if err.args[0] != exp_msg:
            raise err
        pass
    pass

def test_entity_relation_owner_other() -> None:
    exp_msg: str = 'At the moment only `EntityRelationOwner.SELF` is supported.'
    try:
        @DTO()
        class _DTO(DTOBase):
            child: ChildDTO = DTOOneToOneField(
                entity_type=ChildEntity,
                relation_type=OTORelationType.AGGREGATION,
                entity_relation_owner=EntityRelationOwner.OTHER,
                field=DTOField()
            )
            pass
    except AssertionError as err:
        if err.args[0] != exp_msg:
            raise err
        pass
    pass
