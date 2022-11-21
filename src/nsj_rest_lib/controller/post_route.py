from flask import request
from typing import Callable

from nsj_rest_lib.controller.route_base import RouteBase
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.exception import DTOConfigException, MissingParameterException, ConflictException
from nsj_rest_lib.injector_factory_base import NsjInjectorFactoryBase

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
        require_tenant: bool = True,
        require_grupo_emprearial: bool = True
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
            require_tenant=require_tenant,
            require_grupo_emprearial=require_grupo_emprearial,
        )

    def handle_request(self):
        """
        Tratando requisições HTTP Post para inserir uma instância de uma entidade.
        """

        with self._injector_factory() as factory:
            try:
                # Recuperando os dados do corpo da rquisição
                data = request.get_data(as_text=True)
                data = json_loads(data)

                # Tratando do tenant e do grupo_empresarial
                tenant = data.get('tenant')
                grupo_empresarial = data.get('grupo_empresarial')

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
                    return (json_dumps(dict_data), 200, {})
                else:
                    # Retornando a resposta da requuisição
                    return ('', 201, {})
            except JsonLoadException as e:
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(e), 400, {})
            except MissingParameterException as e:
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(e), 400, {})
            except ValueError as e:
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(e), 400, {})
            except ConflictException as e:
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else: 
                    return (format_json_error(e), 409, {})
            except Exception as e:
                if self._handle_exception is not None:
                    return self._handle_exception(e)
                else:
                    return (format_json_error(f'Erro desconhecido: {e}'), 500, {})
