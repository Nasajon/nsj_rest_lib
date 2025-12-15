import re
import collections

from typing import Callable, Dict, List, Set, Optional, Any

from nsj_rest_lib.controller.funtion_route_wrapper import FunctionRouteWrapper
from nsj_rest_lib.dao.dao_base import DAOBase
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.exception import DataOverrideParameterException
from nsj_rest_lib.entity.function_type_base import FunctionTypeBase
from nsj_rest_lib.service.service_base import ServiceBase
from nsj_rest_lib.injector_factory_base import NsjInjectorFactoryBase
from nsj_rest_lib.util.fields_util import FieldsTree, parse_fields_expression


class RouteBase:
    """
    # Examplo de SubRotas

    Tendo um DTO Filho:
    ```python
    @DTO
    class FilhoDTO(DTOBAse):
        id: uuid.UUID = DTOField()
        id_pai: uuid.UUID = DTOField()
    ```
    E um DTO Pai:
    ```python
    @DTO
    class PaiDTO(DTOBAse):
        id: uuid.UUID = DTOField()
    ```
    O Controller seria:
    ```python
    @application.route('/pai/<id_pai>/filho/<id>', methods=['GET'])
    @ListRoute(
        url='/pai/<id_pai>/filho/<id>',
        http_method='GET',
        dto_class=FilhoDTO,
        entity_class=FilhoEntity
    )
    def lista_filhos(_, response):
        return response
    ```

    A parte da rota `<id_pai>` deve ser o nome do campo no FilhoDTO que faz FK com o PaiDTO,
    ou seja, se a relação do FilhoDTO com o PaiDTO é feita pelo campo `pai` a rota ficaria:
    `/pai/<pai>/filho/<id>`

    *Observacao*: No momento a subrota apenas suporta o campo FK no FilhoDTO, e nao usando
    o campos candidatos do PaiDTO.

    Se no PaiDTO conter um `DTOListField` pro FilhoDTO
    ```python
    @DTO
    class PaiDTO(DTOBAse):
        id: uuid.UUID = DTOField()
        filhos: ty.List[FilhoDTO] = DTOListField(
            dto_type=FilhoDTO,
            entity_type=FilhoEntity,
            relation_key_field='id',
            related_entity_field='id_pai',
        )
    ```
    No FilhoDTO o campo de relacionamento é desnecessário:
    ```python
    @DTO
    class FilhoDTO(DTOBAse):
        id: uuid.UUID = DTOField()
    ```
    O campo de relacionamento será criado automaticamente, usando o nome passado no
    atributo `related_entity_field`, nesse exemplo o campo de relacionamento teria o nome `id_pai`.

    E em torno na rota ficaria: `/pai/<id_pai>/filho/<id>`
    """
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
    def parse_expands(_dto_class: DTOBase, expands: Optional[str]) -> FieldsTree:
        expands_tree = parse_fields_expression(expands)
        #expands_tree["root"] |= dto_class.resume_expands

        return expands_tree

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

    @staticmethod
    def build_function_type_from_args(
        function_type_class: type[FunctionTypeBase],
        args: dict[str, any],
        id_value: any = None,
    ) -> FunctionTypeBase:
        """
        Constrói um FunctionType a partir dos args da requisição, incluindo a PK.
        """
        if function_type_class is None:
            return None
        return function_type_class.build_from_params(args or {}, id_value=id_value)

    @staticmethod
    def build_function_object_from_args(
        dto_class: type[DTOBase] | None,
        args: Dict[str, Any] | None,
        extra_params: Dict[str, Any] | None = None,
        id_value: Any | None = None,
    ) -> DTOBase | None:
        """
        Constrói um DTO de parâmetros a partir dos args da requisição,
        incluindo campos adicionais (particionamento / filtros) e, se
        configurado, a PK mapeada a partir de id_value.

        Se dto_class for None, retorna None.
        """
        if dto_class is None:
            return None

        dto_kwargs: Dict[str, Any] = dict(args or {})
        if extra_params:
            dto_kwargs.update(extra_params)

        pk_field = getattr(dto_class, "pk_field", None)
        if pk_field and id_value is not None and pk_field not in dto_kwargs:
            dto_kwargs[pk_field] = id_value

        return dto_class(**dto_kwargs)
