import os

from flask import request
from typing import Callable

from nsj_rest_lib.controller.controller_util import DEFAULT_RESP_HEADERS
from nsj_rest_lib.controller.route_base import RouteBase
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.exception import (
    DataOverrideParameterException,
    MissingParameterException,
    NotFoundException,
)
from nsj_rest_lib.injector_factory_base import NsjInjectorFactoryBase
from nsj_rest_lib.settings import get_logger

from nsj_gcf_utils.json_util import json_dumps
from nsj_gcf_utils.pagination_util import PaginationException
from nsj_gcf_utils.rest_error_util import format_json_error


class GetRoute(RouteBase):
    def __init__(
        self,
        url: str,
        http_method: str,
        dto_class: DTOBase,
        entity_class: EntityBase,
        injector_factory: NsjInjectorFactoryBase = NsjInjectorFactoryBase,
        service_name: str = None,
        handle_exception: Callable = None,
    ):
        super().__init__(
            url=url,
            http_method=http_method,
            dto_class=dto_class,
            entity_class=entity_class,
            dto_response_class=None,
            injector_factory=injector_factory,
            service_name=service_name,
            handle_exception=handle_exception,
        )

    def handle_request(
        self,
        id: str,
        query_args: dict[str, any] = None,
        body: dict[str, any] = None,
        **kwargs,
    ):
        """
        Tratando requisições HTTP Get para recuperar uma instância de uma entidade.
        """

        with self._injector_factory() as factory:
            try:
                ctx = self._resolve_nested_route_context(id, kwargs)

                dto_class = ctx["dto_class"]
                entity_class = ctx["entity_class"]
                dto_response_class = ctx["dto_response_class"]
                service_name = ctx["service_name"]
                target_id = ctx["target_id"]
                relation_filters = ctx["relation_filters"]

                if ctx["matched"] and target_id is None:
                    raise MissingParameterException(dto_class.pk_field)

                # Recuperando os parâmetros básicos
                if os.getenv("ENV", "").lower() != "erp_sql":
                    args = request.args
                else:
                    args = query_args

                # Tratando dos fields
                fields = args.get("fields")
                fields = RouteBase.parse_fields(dto_class, fields)

                expands = RouteBase.parse_expands(dto_class, args.get('expand'))

                partition_fields = {}
                # Tratando campos de particionamento
                for field in dto_class.partition_fields:
                    value = args.get(field)
                    if value is None:
                        raise MissingParameterException(field)

                    partition_fields[field] = value

                if relation_filters:
                    partition_fields.update(relation_filters)

                # Tratando do filtro de conjunto
                if dto_class.conjunto_field is not None:
                    value = args.get(dto_class.conjunto_field)
                    if value is None:
                        raise MissingParameterException(field)
                    elif value is not None:
                        partition_fields[dto_class.conjunto_field] = value

                # Tratando dos campos de data_override
                self._validade_data_override_parameters(args, dto_class)

                # Construindo os objetos
                service = self._get_service(
                    factory,
                    dto_class=dto_class,
                    entity_class=entity_class,
                    dto_response_class=dto_response_class,
                    service_name=service_name,
                )

                # Chamando o service (método get)
                # TODO Rever parametro order_fields abaixo
                data = service.get(
                    target_id,
                    partition_fields,
                    fields,
                    expands=expands,
                )

                # Convertendo para o formato de dicionário (permitindo omitir campos do DTO)
                dict_data = data.convert_to_dict(fields, expands)

                # Retornando a resposta da requuisição
                return (json_dumps(dict_data), 200, {**DEFAULT_RESP_HEADERS})
            except MissingParameterException as e:
                get_logger().warning(e)
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(e), 400, {**DEFAULT_RESP_HEADERS})
            except DataOverrideParameterException as e:
                get_logger().warning(e)
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(e), 400, {**DEFAULT_RESP_HEADERS})
            except PaginationException as e:
                get_logger().warning(e)
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(e), 400, {**DEFAULT_RESP_HEADERS})
            except NotFoundException as e:
                get_logger().warning(e)
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(e), 404, {**DEFAULT_RESP_HEADERS})
            except Exception as e:
                get_logger().exception(e)
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (
                        format_json_error(f"Erro desconhecido: {e}"),
                        500,
                        {**DEFAULT_RESP_HEADERS},
                    )
