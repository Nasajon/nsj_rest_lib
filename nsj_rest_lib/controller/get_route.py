from flask import request
from typing import Callable

from nsj_rest_lib.controller.route_base import RouteBase
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.exception import DTOConfigException, MissingParameterException, NotFoundException
from nsj_rest_lib.injector_factory_base import NsjInjectorFactoryBase

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
        require_tenant: bool = True,
        require_grupo_emprearial: bool = True
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
            require_tenant=require_tenant,
            require_grupo_emprearial=require_grupo_emprearial,
        )

    def handle_request(self, id):
        """
        Tratando requisições HTTP Get para recuperar uma instância de uma entidade.
        """

        with self._injector_factory() as factory:
            try:
                # Recuperando os parâmetros básicos
                args = request.args

                # Tratando dos fields
                fields = args.get('fields')
                fields = self._parse_fields(fields)

                # Tratando do tenant e do grupo_empresarial
                # TODO Refatorar para exibir os dois erros ao mesmo tempo
                tenant = args.get('tenant')
                grupo_empresarial = args.get('grupo_empresarial')

                if self._require_tenant:
                    if tenant is None:
                        raise MissingParameterException('tenant')

                    if not ('tenant' in self._dto_class.fields_map):
                        raise DTOConfigException(
                            f"Missing 'tenant' field declaration on DTOClass: {self._dto_class}")

                if self._require_grupo_emprearial:
                    if grupo_empresarial is None:
                        raise MissingParameterException('grupo_empresarial')

                    if not ('grupo_empresarial' in self._dto_class.fields_map):
                        raise DTOConfigException(
                            f"Missing 'grupo_empresarial' field declaration on DTOClass: {self._dto_class}")

                # Construindo os objetos
                service = self._get_service(factory)

                # Chamando o service (método get)
                # TODO Rever parametro order_fields abaixo
                data = service.get(id, grupo_empresarial, tenant, fields)

                # Convertendo para o formato de dicionário (permitindo omitir campos do DTO)
                dict_data = data.convert_to_dict(fields)

                # Retornando a resposta da requuisição
                return (json_dumps(dict_data), 200, {})
            except MissingParameterException as e:
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(e), 400, {})
            except PaginationException as e:
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(e), 400, {})
            except NotFoundException as e:
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(e), 404, {})
            except Exception as e:
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(f'Erro desconhecido: {e}'), 500, {})
