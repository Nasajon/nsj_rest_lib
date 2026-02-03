import pytest

from nsj_rest_lib.decorator.dto import DTO
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.dto.dto_base import DTOBase


@DTO()
class EtagDTO(DTOBase):
    id: int = DTOField(pk=True)
    version: str = DTOField(etag_field=True)


def test_etag_field_sets_class_attribute():
    assert EtagDTO.etag_field_name == "version"


def test_multiple_etag_fields_raise():
    with pytest.raises(ValueError, match="etag_field"):

        @DTO()
        class InvalidEtagDTO(DTOBase):
            id: int = DTOField(pk=True)
            version: str = DTOField(etag_field=True)
            updated_at: str = DTOField(etag_field=True)
