import os
import typing as ty

from flask import request
from typing import Callable, Optional

from nsj_audit_lib.util.audit_config import AuditConfig
from nsj_gcf_utils.json_util import json_dumps
from nsj_gcf_utils.pagination_util import PaginationException
from nsj_gcf_utils.rest_error_util import format_json_error

from nsj_rest_lib.controller.controller_util import DEFAULT_RESP_HEADERS
from nsj_rest_lib.controller.route_base import RouteBase
from nsj_rest_lib.dao.dao_base import DAOBase
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.exception import (
    DataOverrideParameterException,
    MissingParameterException,
    NotFoundException,
)
from nsj_rest_lib.injector_factory_base import NsjInjectorFactoryBase
from nsj_rest_lib.settings import get_logger
from nsj_rest_lib.util.fields_util import merge_fields_tree


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
        get_function_type_class: type | None = None,
        get_function_name: str | None = None,
        get_function_response_dto_class: type | None = None,
        custom_json_response: bool = False,
        audit_config: AuditConfig | None = None,
    ):
        """
        Rota de GET por ID.

        - ``get_function_type_class``: subclasse de ``GetFunctionTypeBase``
          que representa o TYPE de entrada da função PL/pgSQL. Quando
          informado, o Service chama ``_call_function_with_type`` usando
          uma instância desse FunctionType montada a partir dos
          parâmetros da requisição. Se não for informado, o GET usa o
          modo padrão (select na tabela).
        - ``get_function_name``: nome da função PL/pgSQL para GET por
          função (ex.: ``teste.api_classificacaofinanceiraget``).
        - ``get_function_response_dto_class``: DTO usado para mapear o
          retorno da função (fallback para ``dto_class``).
        """
        super().__init__(
            url=url,
            http_method=http_method,
            dto_class=dto_class,
            entity_class=entity_class,
            dto_response_class=None,
            injector_factory=injector_factory,
            service_name=service_name,
            handle_exception=handle_exception,
            audit_config=audit_config,
        )
        self._get_function_type_class = get_function_type_class
        self._get_function_name = get_function_name
        self._get_function_response_dto_class = (
            get_function_response_dto_class or dto_class
        )
        self.custom_json_response = custom_json_response

    def _get_service(self, factory: NsjInjectorFactoryBase):
        """
        Sobrescreve o _get_service padrão para permitir configurar
        o DTO de resposta de função diretamente no construtor do Service.
        """

        if self._service_name is not None:
            return factory.get_service_by_name(self._service_name)

        from nsj_rest_lib.service.service_base import ServiceBase

        return ServiceBase(
            factory,
            DAOBase(factory.db_adapter(), self._entity_class),
            self._dto_class,
            self._entity_class,
            self._dto_response_class,
            get_function_response_dto_class=self._get_function_response_dto_class,
        )

    def handle_request(
        self,
        id: str,
        query_args: dict[str, any] = None,
        body: dict[str, any] = None,
        **kwargs: ty.Any,
    ):
        """
        Tratando requisições HTTP Get para recuperar uma instância de uma entidade.
        """

        try:
            # Recuperando os parâmetros básicos
            if os.getenv("ENV", "").lower() != "erp_sql":
                args = request.args
            else:
                args = query_args

            fields = RouteBase.parse_fields(
                self._dto_class, args.get("fields", '')
            )
            expands = RouteBase.parse_expands(
                self._dto_class, args.get("expand", '')
            )
            merge_fields_tree(fields, expands)

            partition_fields = kwargs.copy()
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

            # Tratando dos campos de data_override
            self._validade_data_override_parameters(args)

            # Construindo os objetos
            service = self._get_service(self.get_injector_factory())
            function_object = None
            if self._get_function_type_class is not None:
                params = dict(args)
                params.update(partition_fields)
                function_object = RouteBase.build_function_type_from_args(
                    self._get_function_type_class,
                    params,
                    id_value=id,
                )
            function_params = None if function_object is not None else args

            etag_header: Optional[str] = request.headers.get("If-None-Match")
            etag_field_name: Optional[str] = self._dto_class.etag_field_name
            if (
                etag_header is not None
                and etag_field_name is not None
            ):
                fields['root'].add(etag_field_name)
                etag_fields = {
                    'root': {etag_field_name, self._dto_class.pk_field}
                }

                etag_dto = service.get(
                    id=id,
                    partition_fields=partition_fields,
                    fields=etag_fields,
                    expands={'root': set()},
                    function_params=function_params,
                    function_object=function_object,
                    function_name=self._get_function_name,
                    custom_json_response=False,
                )
                etag_value = getattr(etag_dto, etag_field_name, None)
                if etag_value is not None and etag_header == str(etag_value):
                    return (
                        "", 304, {**DEFAULT_RESP_HEADERS, "ETag": etag_value}
                    )

            # Chamando o service (método get)
            # TODO Rever parametro order_fields abaixo
            data = service.get(
                id,
                partition_fields,
                fields,
                expands=expands,
                function_params=function_params,
                function_object=function_object,
                function_name=self._get_function_name,
                custom_json_response=self.custom_json_response,
            )

            if self.custom_json_response and self._get_function_name is not None:
                return (json_dumps(data), 200, {**DEFAULT_RESP_HEADERS})

            # Convertendo para o formato de dicionário (permitindo omitir campos do DTO)
            dict_data = data.convert_to_dict(fields, expands)

            headers = {**DEFAULT_RESP_HEADERS}
            if etag_field_name is not None:
                etag_value = getattr(data, etag_field_name, None)
                if etag_value is not None:
                    headers["ETag"] = str(etag_value)

            # Retornando a resposta da requuisição
            return (json_dumps(dict_data), 200, headers)
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
