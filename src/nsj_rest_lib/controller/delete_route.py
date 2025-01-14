import os
from flask import request
from typing import Callable

from nsj_rest_lib.controller.controller_util import DEFAULT_RESP_HEADERS
from nsj_rest_lib.controller.route_base import RouteBase
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.exception import DTOConfigException, MissingParameterException, NotFoundException
from nsj_rest_lib.injector_factory_base import NsjInjectorFactoryBase
from nsj_rest_lib.settings import get_logger

from nsj_gcf_utils.json_util import json_dumps
from nsj_gcf_utils.pagination_util import PaginationException
from nsj_gcf_utils.rest_error_util import format_json_error


class DeleteRoute(RouteBase):
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

    def _partition_filters(self, args):
        partition_filters = {}
        # Tratando campos de particionamento
        for field in self._dto_class.partition_fields:
            value = args.get(field)
            if value is None:
                raise MissingParameterException(field)
            partition_filters[field] = value

        return partition_filters

    def handle_request(
        self,
        id: str = None,
        query_args: dict[str, any] = None,
        body: dict[str, any] = None,
    ):
        """
        Tratando requisições HTTP Delete para excluir uma instância de uma entidade.
        """

        with self._injector_factory() as factory:
            try:
                # Recuperando os parâmetros básicos
                if os.getenv("ENV", "").lower() != "erp_sql":
                    args = request.args
                else:
                    args = query_args

                # Recuperando os dados do corpo da requisição
                request_data = request.json

                if request_data is not None:
                    if not isinstance(request_data, list):
                        request_data = [request_data]

                partition_filters = self._partition_filters(args)

                # Construindo os objetos
                service = self._get_service(factory)

                if id is not None:
                    # Chamando o service (método get)
                    # TODO Rever parametro order_fields abaixo
                    service.delete(id, partition_filters)
                else:
                    service.delete_list(
                        request_data,
                        partition_filters
                    )

                # Retornando a resposta da requuisição
                return ("", 204, {**DEFAULT_RESP_HEADERS})
            except MissingParameterException as e:
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
                    return (format_json_error(f'Erro desconhecido: {e}'), 500, {**DEFAULT_RESP_HEADERS})
