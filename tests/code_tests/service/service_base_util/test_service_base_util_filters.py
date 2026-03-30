"""Regression tests for ServiceBaseUtil entity filters."""

from unittest.mock import Mock

from nsj_rest_lib.dao.dao_base_util import DAOBaseUtil
from nsj_rest_lib.decorator.dto import DTO
from nsj_rest_lib.decorator.entity import Entity
from nsj_rest_lib.descriptor.dto_aggregator import DTOAggregator
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.descriptor.dto_one_to_one_field import (
    DTOOneToOneField,
    OTORelationType,
)
from nsj_rest_lib.descriptor.filter_operator import FilterOperator
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.entity.filter import Filter
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


@Entity(table_name="job_level", pk_field="id", default_order_fields=["id"])
class JobLevelEntity(EntityBase):
    id: int = None
    codigo: str = None
    descricao: str = None


@DTO()
class JobLevelDTO(DTOBase):
    id: int = DTOField(pk=True)
    codigo: str = DTOField()
    descricao: str = DTOField()


@Entity(table_name="worker", pk_field="id", default_order_fields=["id"])
class WorkerEntity(EntityBase):
    id: int = None
    cargo_id: int = None
    funcao_id: int = None


@DTO()
class WorkerDTO(DTOBase):
    id: int = DTOField(pk=True)
    cargo: JobLevelDTO = DTOOneToOneField(
        entity_type=JobLevelEntity,
        relation_type=OTORelationType.AGGREGATION,
        entity_field="cargo_id",
    )
    funcao: JobLevelDTO = DTOOneToOneField(
        entity_type=JobLevelEntity,
        relation_type=OTORelationType.AGGREGATION,
        entity_field="funcao_id",
    )


def _build_service():
    dao = Mock()
    return ServiceBase.construtor1(
        db_adapter=None,
        dao=dao,
        dto_class=ClientDTO,
        entity_class=ClientEntity,
    )


def _build_worker_service():
    dao = Mock()
    return ServiceBase.construtor1(
        db_adapter=None,
        dao=dao,
        dto_class=WorkerDTO,
        entity_class=WorkerEntity,
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


def test_entity_filters_accept_dot_notation_for_one_to_one_field():
    service = _build_worker_service()
    filters = service._create_entity_filters({"cargo.codigo": "000000"})

    assert "codigo" in filters
    entity_filter = filters["codigo"][0]
    assert entity_filter.operator == FilterOperator.EQUALS
    assert entity_filter.value == "000000"
    assert entity_filter.table_alias == "oto_cargo"


def test_resolve_sql_join_fields_adds_join_for_one_to_one_filter():
    service = _build_worker_service()
    entity_filters = service._create_entity_filters({"cargo.codigo": "000000"})

    joins_aux = service._resolve_sql_join_fields({"id"}, entity_filters)

    assert len(joins_aux) == 1
    join_aux = joins_aux[0]
    assert join_aux.table == "job_level"
    assert join_aux.type == "inner"
    assert join_aux.alias == "oto_cargo"
    assert join_aux.fields == []
    assert join_aux.self_field == "cargo_id"
    assert join_aux.other_field == "id"


def test_make_filters_sql_keeps_alias_groups_separated():
    dao_util = DAOBaseUtil(db=Mock(), entity_class=WorkerEntity)
    filters = {
        "codigo": [
            Filter(FilterOperator.EQUALS, "000000", "oto_cargo"),
            Filter(FilterOperator.EQUALS, "111111", "oto_funcao"),
        ]
    }

    sql, params = dao_util._make_filters_sql(filters)

    assert "oto_cargo.codigo = :ft_equals_oto_cargo_codigo_0" in sql
    assert "oto_funcao.codigo = :ft_equals_oto_funcao_codigo_0" in sql
    assert " in (" not in sql
    assert params["ft_equals_oto_cargo_codigo_0"] == "000000"
    assert params["ft_equals_oto_funcao_codigo_0"] == "111111"
