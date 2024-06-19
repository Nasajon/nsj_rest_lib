import re

from typing import Callable, Dict, List, Set

from nsj_rest_lib.controller.funtion_route_wrapper import FunctionRouteWrapper
from nsj_rest_lib.dao.dao_base import DAOBase
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.service.service_base import ServiceBase
from nsj_rest_lib.injector_factory_base import NsjInjectorFactoryBase


class RouteBase:
    url: str
    http_method: str
    registered_routes: List["RouteBase"] = []
    function_wrapper: FunctionRouteWrapper

    _injector_factory: NsjInjectorFactoryBase
    _service_name: str
    _handle_exception: Callable
    _dto_class: DTOBase
    _entity_class: EntityBase
    _dto_response_class: DTOBase

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
        super().__init__()

        self.url = url
        self.http_method = http_method
        self.__class__.registered_routes.append(self)

        self._injector_factory = injector_factory
        self._service_name = service_name
        self._handle_exception = handle_exception
        self._dto_class = dto_class
        self._entity_class = entity_class
        self._dto_response_class = dto_response_class

    def __call__(self, func):
        from nsj_rest_lib.controller.command_router import CommandRouter

        # Criando o wrapper da função
        self.function_wrapper = FunctionRouteWrapper(self, func)

        # Registrando a função para ser chamada via linha de comando
        CommandRouter.get_instance().register(
            func.__name__,
            self.function_wrapper,
            self,
        )

        # Retornando o wrapper para substituir a função original
        return self.function_wrapper

    def _get_service(self, factory: NsjInjectorFactoryBase) -> ServiceBase:
        """
        Return service instance, by service name or using NsjServiceBase.
        """

        if self._service_name is not None:
            return factory.get_service_by_name(self._service_name)
        else:
            return ServiceBase(
                factory,
                DAOBase(factory.db_adapter(), self._entity_class),
                self._dto_class,
                self._entity_class,
                self._dto_response_class,
            )

    def _parse_fields(self, fields: str) -> Dict[str, Set[str]]:
        """
        Trata a lista de fields recebida, construindo um dict, onde as chaves
        serão os nomes das propriedades com objetos aninhados), ou o "root"
        indicando os campos da entidade raíz; e, os valores são listas com os
        nomes das propriedades recebidas.
        """

        # TODO Refatorar para ser recursivo, e suportar qualquer nível de aninhamento de entidades

        if fields is None:
            fields_map = {}
            fields_map.setdefault("root", self._dto_class.resume_fields)
            return fields_map

        fields = fields.split(",")

        matcher_dot = re.compile("(.+)\.(.+)")
        matcher_par = re.compile("(.+)\((.+)\)")

        # Construindo o mapa de retorno
        fields_map = {}

        # Iterando cada field recebido
        for field in fields:
            field = field.strip()

            match_dot = matcher_dot.match(field)
            match_par = matcher_par.match(field)

            if match_dot is not None:
                # Tratando fields=entidade_aninhada.propriedade
                key = match_dot.group(1)
                value = match_dot.group(2)

                # Adicionando a propriedade do objeto interno as campos root
                root_field_list = fields_map.setdefault("root", set())
                if not key in root_field_list:
                    root_field_list.add(key)

                field_list = fields_map.setdefault(key, set())
                field_list.add(value)
            elif match_par is not None:
                # Tratando fields=entidade_aninhada(propriedade1, propriedade2)
                key = match_dot.group(1)
                value = match_dot.group(2)

                field_list = fields_map.setdefault(key, set())

                # Adicionando a propriedade do objeto interno as campos root
                root_field_list = fields_map.setdefault("root", set())
                if not key in root_field_list:
                    root_field_list.add(key)

                # Tratando cada campo dentro do parêntese
                for val in value.split(","):
                    val = val.strip()

                    field_list.add(val)
            else:
                # Tratando propriedade simples (sem entidade aninhada)
                root_field_list = fields_map.setdefault("root", set())
                root_field_list.add(field)

        return fields_map
