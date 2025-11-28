import re
import collections

from typing import Any, Callable, Dict, List, Optional, Set, Type

from nsj_rest_lib.descriptor.dto_list_field import DTOListField

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

    def _get_service(
        self,
        factory: NsjInjectorFactoryBase,
        dto_class: Type[DTOBase] = None,
        entity_class: Type[EntityBase] = None,
        dto_response_class: Type[DTOBase] = None,
        service_name: str = None,
        insert_function_type_class=None,
        update_function_type_class=None,
    ) -> ServiceBase:
        """
        Return service instance, by service name or using NsjServiceBase.
        """

        dto_class = dto_class or self._dto_class
        entity_class = entity_class or self._entity_class
        dto_response_class = (
            dto_response_class
            if dto_response_class is not None
            else self._dto_response_class
        )
        service_name = service_name or self._service_name

        if service_name is not None:
            return factory.get_service_by_name(service_name)
        else:
            return ServiceBase(
                factory,
                DAOBase(factory.db_adapter(), entity_class),
                dto_class,
                entity_class,
                dto_response_class,
                insert_function_type_class,
                update_function_type_class,
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
    def parse_expands(_dto_class: DTOBase, expands: Optional[str]) -> FieldsTree:
        expands_tree = parse_fields_expression(expands)
        #expands_tree["root"] |= dto_class.resume_expands

        return expands_tree

    def _validade_data_override_parameters(self, args, dto_class: Type[DTOBase] = None):
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
        dto_class = dto_class or self._dto_class

        for i in range(1, len(dto_class.data_override_fields)):
            field = dto_class.data_override_fields[-i]
            previous_field = dto_class.data_override_fields[-i - 1]

            value_field = args.get(field)
            previous_value_field = args.get(previous_field)

            # Ensure that if a field has a value, its preceding field must also have a value
            if value_field is not None and previous_value_field is None:
                raise DataOverrideParameterException(field, previous_field)

    def _extract_url_param_value(
        self,
        url_tokens: List[str],
        token_index: int,
        id_value: Any,
        kwargs: Dict[str, Any],
    ) -> Any:
        """
        Extracts the runtime value for a given token position in the route url.
        Returns None for static tokens.
        """

        if token_index < 0 or token_index >= len(url_tokens):
            return None

        token = url_tokens[token_index]
        if not (token.startswith("<") and token.endswith(">")):
            return None

        arg_name = token[1:-1]
        if arg_name in kwargs:
            return kwargs[arg_name]
        if arg_name == "id":
            return id_value

        return None

    def _resolve_nested_route_context(
        self,
        id_value: Any,
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Percorre os tokens da rota procurando relacionamentos aninhados (DTOListField)
        de forma recursiva, retornando o contexto da entidade/DTO alvo.
        """
        context = {
            "matched": False,
            "dto_class": self._dto_class,
            "entity_class": self._entity_class,
            "dto_response_class": self._dto_response_class,
            "service_name": self._service_name,
            "insert_function_type": None,
            "update_function_type": None,
            "relation_filters": {},
            "target_id": id_value,
            "relation_field_name": None,
            "relation_value": None,
        }

        url_tokens = [token for token in self.url.split("/") if token]
        if len(url_tokens) <= 0:
            return context

        current_dto = self._dto_class
        current_entity = self._entity_class
        current_service_name = self._service_name
        current_response_class = self._dto_response_class
        current_insert_function = None
        current_update_function = None
        current_target_id = id_value
        relation_filters: Dict[str, Any] = {}
        last_placeholder_value = None
        matched = False
        last_relation_field_name = None
        last_relation_value = None

        for idx, token in enumerate(url_tokens):
            if token.startswith("<") and token.endswith(">"):
                last_placeholder_value = self._extract_url_param_value(
                    url_tokens, idx, id_value, kwargs
                )
                continue

            list_field = getattr(current_dto, "list_fields_map", {}).get(token)
            if list_field is None:
                continue

            parent_id = last_placeholder_value
            if parent_id is None:
                continue

            matched = True

            # Relação para o nível corrente (substitui as anteriores)
            relation_filters = {}
            relation_field_name = None
            if list_field.related_entity_field is not None:
                relation_field_name = self._resolve_dto_relation_field_name(
                    list_field.dto_type,
                    list_field.related_entity_field,
                )

                if relation_field_name is None:
                    raise ValueError(
                        f"Campo de relação '{list_field.related_entity_field}' não encontrado no DTO '{list_field.dto_type.__name__}'."
                    )

                relation_filters[relation_field_name] = parent_id
                last_relation_field_name = relation_field_name
                last_relation_value = parent_id

            child_id = self._extract_url_param_value(
                url_tokens, idx + 1, id_value, kwargs
            )
            if child_id is not None:
                current_target_id = child_id
            last_placeholder_value = child_id

            current_dto = list_field.dto_type
            current_entity = list_field.entity_type
            current_service_name = list_field.service_name
            current_insert_function = list_field.insert_function_type
            current_update_function = list_field.update_function_type
            if list_field.dto_post_response_type is not None:
                current_response_class = list_field.dto_post_response_type

        context.update(
            {
                "matched": matched,
                "dto_class": current_dto,
                "entity_class": current_entity,
                "dto_response_class": current_response_class,
                "service_name": current_service_name,
                "insert_function_type": current_insert_function,
                "update_function_type": current_update_function,
                "relation_filters": relation_filters,
                "target_id": current_target_id,
                "relation_field_name": last_relation_field_name,
                "relation_value": last_relation_value,
            }
        )
        return context

    def _resolve_nested_list_field(
        self,
        id_value: Any,
        kwargs: Dict[str, Any],
    ) -> Optional[tuple[DTOListField, Any, Any]]:
        """
        Mantido para compatibilidade: retorna apenas o último relacionamento encontrado.
        """
        ctx = self._resolve_nested_route_context(id_value, kwargs)
        if not ctx.get("matched"):
            return None

        # Encontrar o último list_field percorrendo novamente com o DTO inicial
        url_tokens = [token for token in self.url.split("/") if token]
        current_dto = self._dto_class
        last_match = None
        last_parent = None
        last_child = None
        last_placeholder_value = None

        for idx, token in enumerate(url_tokens):
            if token.startswith("<") and token.endswith(">"):
                last_placeholder_value = self._extract_url_param_value(
                    url_tokens, idx, id_value, kwargs
                )
                continue

            list_field = getattr(current_dto, "list_fields_map", {}).get(token)
            if list_field is None:
                continue

            parent_id = last_placeholder_value
            child_id = self._extract_url_param_value(url_tokens, idx + 1, id_value, kwargs)

            last_match = list_field
            last_parent = parent_id
            last_child = child_id
            last_placeholder_value = child_id
            current_dto = list_field.dto_type

        if last_match is None:
            return None

        return last_match, last_parent, last_child

    def _resolve_dto_relation_field_name(
        self,
        dto_class: Type[DTOBase],
        related_entity_field: str,
    ) -> Optional[str]:
        """
        Tries to find the DTO field name that maps to a given entity field.
        """
        if related_entity_field in dto_class.fields_map:
            return related_entity_field

        for field_name, descriptor in dto_class.fields_map.items():
            if descriptor.entity_field == related_entity_field:
                return field_name

        return None
