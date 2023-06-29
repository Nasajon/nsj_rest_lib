from flask import request
from typing import Callable

from nsj_rest_lib.controller.controller_util import DEFAULT_RESP_HEADERS
from nsj_rest_lib.controller.route_base import RouteBase
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.exception import DTOConfigException, MissingParameterException, ConflictException
from nsj_rest_lib.injector_factory_base import NsjInjectorFactoryBase
from nsj_rest_lib.settings import get_logger

from nsj_gcf_utils.json_util import json_dumps, json_loads, JsonLoadException
from nsj_gcf_utils.rest_error_util import format_json_error


class PostRoute(RouteBase):
    def __init__(
        self,
        url: str,
        http_method: str,
        dto_class: DTOBase,
        entity_class: EntityBase,
        dto_response_class: DTOBase = None,
        injector_factory: NsjInjectorFactoryBase = NsjInjectorFactoryBase,
        service_name: str = None,
        handle_exception: Callable = None,
    ):
        super().__init__(
            url=url,
            http_method=http_method,
            dto_class=dto_class,
            entity_class=entity_class,
            dto_response_class=dto_response_class,
            injector_factory=injector_factory,
            service_name=service_name,
            handle_exception=handle_exception,
        )

    def handle_request(self):
        """
        Tratando requisições HTTP Post para inserir uma instância de uma entidade.
        """

        with self._injector_factory() as factory:
            try:
                # Recuperando os dados do corpo da rquisição
                data = request.json

                # Convertendo os dados para o DTO
                data = self._dto_class(**data)

                # Construindo os objetos
                service = self._get_service(factory)

                # Chamando o service (método insert)
                data = service.insert(data)

                if data is not None:
                    # Convertendo para o formato de dicionário (permitindo omitir campos do DTO)
                    dict_data = data.convert_to_dict()

                    # Retornando a resposta da requuisição
                    return (json_dumps(dict_data), 200, {**DEFAULT_RESP_HEADERS})
                else:
                    # Retornando a resposta da requuisição
                    return ('', 201, {**DEFAULT_RESP_HEADERS})
            except JsonLoadException as e:
                get_logger().warning(e)
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(e), 400, {**DEFAULT_RESP_HEADERS})
            except MissingParameterException as e:
                get_logger().warning(e)
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(e), 400, {**DEFAULT_RESP_HEADERS})
            except ValueError as e:
                get_logger().warning(e)
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(e), 400, {**DEFAULT_RESP_HEADERS})
            except ConflictException as e:
                get_logger().warning(e)
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(e), 409, {**DEFAULT_RESP_HEADERS})
            except Exception as e:
                get_logger().exception(e)
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(f'Erro desconhecido: {e}'), 500, {**DEFAULT_RESP_HEADERS})
