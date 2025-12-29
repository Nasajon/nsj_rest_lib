"""Regression tests for ServiceBaseUtil entity filters."""

from unittest.mock import Mock

from nsj_rest_lib.decorator.dto import DTO
from nsj_rest_lib.decorator.entity import Entity
from nsj_rest_lib.descriptor.dto_aggregator import DTOAggregator
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.descriptor.filter_operator import FilterOperator
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.service.service_base import ServiceBase


@DTO()
class AddressDTO(DTOBase):
    rua: str = DTOField()
    cidade: str = DTOField()


@DTO()
class ClientDTO(DTOBase):
    id: int = DTOField(pk=True)
    endereco: AddressDTO = DTOAggregator(AddressDTO)


@Entity(table_name="client", pk_field="id", default_order_fields=["id"])
class ClientEntity(EntityBase):
    id: int = None
    rua: str = None
    cidade: str = None


def _build_service():
    dao = Mock()
    return ServiceBase.construtor1(
        db_adapter=None,
        dao=dao,
        dto_class=ClientDTO,
        entity_class=ClientEntity,
    )


def test_entity_filters_accept_dot_notation_for_aggregator_field():
    service = _build_service()
    filters = service._create_entity_filters({"endereco.rua": "Paulista"})

    assert "rua" in filters
    entity_filters = filters["rua"]
    assert len(entity_filters) == 1

    entity_filter = entity_filters[0]
    assert entity_filter.operator == FilterOperator.EQUALS
    assert entity_filter.value == "Paulista"
