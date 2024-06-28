import os

from flask import request
from typing import Callable

from nsj_rest_lib.controller.controller_util import DEFAULT_RESP_HEADERS
from nsj_rest_lib.controller.route_base import RouteBase
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.exception import (
    DTOConfigException,
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
    ):
        """
        Tratando requisições HTTP Get para recuperar uma instância de uma entidade.
        """

        with self._injector_factory() as factory:
            try:
                # Recuperando os parâmetros básicos
                if os.getenv("ENV", "").lower() != "erp_sql":
                    args = request.args
                else:
                    args = query_args

                # Tratando dos fields
                fields = args.get("fields")
                fields = self._parse_fields(fields)

                partition_fields = {}
                # Tratando campos de particionamento
                for field in self._dto_class.partition_fields:
                    value = args.get(field)
                    if value is None:
                        raise MissingParameterException(field)

                    partition_fields[field] = value

                # Tratando do filtro de conjunto
                if self._dto_class.conjunto_field is not None:
                    value = args.get(self._dto_class.conjunto_field)
                    if value is None:
                        raise MissingParameterException(field)
                    elif value is not None:
                        partition_fields[self._dto_class.conjunto_field] = value

                # Construindo os objetos
                service = self._get_service(factory)

                # Chamando o service (método get)
                # TODO Rever parametro order_fields abaixo
                data = service.get(id, partition_fields, fields)

                # Convertendo para o formato de dicionário (permitindo omitir campos do DTO)
                dict_data = data.convert_to_dict(fields)

                # Retornando a resposta da requuisição
                return (json_dumps(dict_data), 200, {**DEFAULT_RESP_HEADERS})
            except MissingParameterException as e:
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
