import os
from flask import request
from typing import Callable

from nsj_rest_lib.controller.controller_util import DEFAULT_RESP_HEADERS
from nsj_rest_lib.controller.route_base import RouteBase
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.exception import (
    MissingParameterException,
    NotFoundException,
)
from nsj_rest_lib.injector_factory_base import NsjInjectorFactoryBase
from nsj_rest_lib.settings import get_logger

from nsj_gcf_utils.json_util import json_dumps, JsonLoadException
from nsj_gcf_utils.rest_error_util import format_json_error


class PutRoute(RouteBase):
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
        custom_before_update: Callable = None,
        custom_after_update: Callable = None,
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
        self.custom_before_update = custom_before_update
        self.custom_after_update = custom_after_update

    def _partition_filters(self, data):
        # Montando os filtros de particao de dados
        partition_filters = {}

        for field in data.partition_fields:
            value = getattr(data, field)
            if value is None:
                raise MissingParameterException(field)
            elif value is not None:
                partition_filters[field] = value

        return partition_filters


    def handle_request(
        self,
        id: str = None, 
        query_args: dict[str, any] = None,
        body: dict[str, any] = None,
    ):
        """
        Tratando requisições HTTP Put para inserir uma instância de uma entidade.
        """

        with self._injector_factory() as factory:
            try:
                 # Recuperando os dados do corpo da requisição
                if os.getenv("ENV", "").lower() != "erp_sql":
                    request_data = request.json
                    args = request.args
                else:
                    request_data = body
                    args = query_args

                # Parâmetros da requisição
                is_upsert = args.get('upsert', False, type=lambda value: value.lower() == 'true')

                if not isinstance(request_data, list):
                    request_data = [request_data]

                data_pack = []
                lst_data = []
                partition_filters = None
                for item in request_data:

                    item["generate_default_pk_value"] = False

                    # Convertendo os dados para o DTO
                    data = self._dto_class(**item)

                    # Montando os filtros de particao de dados
                    if partition_filters is None:
                        partition_filters = self._partition_filters(data)

                    data_pack.append(data)

                # Construindo os objetos
                service = self._get_service(factory)

                if len(data_pack)==1:
                    # Chamando o service (método insert)
                    data = service.update(
                        dto=data,
                        id=id if id is not None else getattr(data, data.pk_field),
                        aditional_filters=partition_filters,
                        custom_before_update=self.custom_before_update,
                        custom_after_update=self.custom_after_update,
                        upsert=is_upsert
                    )

                    if data is not None:
                        # Convertendo para o formato de dicionário
                        lst_data.append(data.convert_to_dict())
                else:
                    data = service.update_list(
                        dtos=data_pack,
                        aditional_filters=partition_filters,
                        custom_before_update=self.custom_before_update,
                        custom_after_update=self.custom_after_update,
                        upsert=is_upsert
                    )

                    if data is not None or not len(data)>0:
                        # Convertendo para o formato de dicionário (permitindo omitir campos do DTO)
                        lst_data = [item.convert_to_dict() for item in data]

                if len(lst_data)==1:
                    # Retornando a resposta da requisição
                    return (json_dumps(lst_data[0]), 200, {**DEFAULT_RESP_HEADERS})

                if len(lst_data)>1:
                    # Retornando a resposta da requisição
                    return (json_dumps(lst_data), 200, {**DEFAULT_RESP_HEADERS})

                # Retornando a resposta da requisição
                return ("", 204, {**DEFAULT_RESP_HEADERS})
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
