import re
import collections

from typing import Callable, Dict, List, Set, Optional

from nsj_rest_lib.controller.funtion_route_wrapper import FunctionRouteWrapper
from nsj_rest_lib.dao.dao_base import DAOBase
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.exception import DataOverrideParameterException
from nsj_rest_lib.service.service_base import ServiceBase
from nsj_rest_lib.injector_factory_base import NsjInjectorFactoryBase
from nsj_rest_lib.util.fields_util import FieldsTree, parse_fields_expression


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

    @staticmethod
    def parse_fields(dto_class: DTOBase, fields: str) -> FieldsTree:
        """
        Converte a expressão de fields recebida (query string) em uma estrutura
        em árvore, garantindo que os campos de resumo do DTO sejam considerados.
        """

        fields_tree = parse_fields_expression(fields)
        fields_tree["root"] |= dto_class.resume_fields

        return fields_tree

    @staticmethod
    def parse_expands(expands: Optional[str]) -> Dict[str, Set[str]]:
        if expands is None:
            return {'root': set()}

        expands_map: Dict[str, Set[str]] = collections.defaultdict(set)

        for field in expands.split(','):
            field = field.strip()

            if '.' in field:
                key = field[:field.index('.')]
                value = field[field.index('.')+1:]
                expands_map['root'].add(key)
                expands_map[key].add(value)
            elif '(' in field and ')' in field:
                key = field[:field.index('(')]
                values = field[field.index('(')+1:field.index(')')]
                expands_map['root'].add(key)
                for value in values.split(','):
                    expands_map[key].add(value.strip())
            else:
                expands_map['root'].add(field)

        return expands_map

    def _validade_data_override_parameters(self, args):
        """
        Validates the data override parameters provided in the request arguments.

        This method ensures that if a field in the data override fields list has a value (received as args),
        the preceding field in the list must also have a value. If this condition is not met,
        a DataOverrideParameterException is raised.

        Args:
            args (dict): The request arguments containing the data override parameters.

        Raises:
            DataOverrideParameterException: If a field has a value but the preceding field does not.
        """
        for i in range(1, len(self._dto_class.data_override_fields)):
            field = self._dto_class.data_override_fields[-i]
            previous_field = self._dto_class.data_override_fields[-i - 1]

            value_field = args.get(field)
            previous_value_field = args.get(previous_field)

            # Ensure that if a field has a value, its preceding field must also have a value
            if value_field is not None and previous_value_field is None:
                raise DataOverrideParameterException(field, previous_field)
