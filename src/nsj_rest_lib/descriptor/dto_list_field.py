import enum
import typing

from decimal import Decimal

from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.exception import DTOListFieldConfigException


class DTOListField:
    _ref_counter = 0

    def __init__(
        self,
        dto_type: DTOBase,
        entity_type: EntityBase,
        related_entity_field: str,
        not_null: bool = False,
        min: int = None,
        max: int = None,
        validator: typing.Callable = None,
        dto_post_response_type: DTOBase = None
    ):
        """
        -----------
        Parameters:
        -----------
        dto_type: Expected type for the related DTO (must be subclasse from DTOBase).
        entity_type: Expected entity type for the related DTO (must be subclasse from EntityBase).
        not_null: The field cannot be None (or an empty list).
        min: Minimum number of itens in the list.
        max: Maximum number of itens in the list.
        validator: Function that receives the value (to be setted), and returns the same value (after any adjust).
          This function overrides the default behaviour and all default constraints.
        related_entity_field: Fields, from related entity, used for relation in database.
        """
        self.dto_type = dto_type
        self.entity_type = entity_type
        self.related_entity_field = related_entity_field
        self.not_null = not_null
        self.min = min
        self.max = max
        self.validator = validator
        self.dto_post_response_type = dto_post_response_type

        self.storage_name = f"_{self.__class__.__name__}#{self.__class__._ref_counter}"
        self.__class__._ref_counter += 1

        # Checking correct usage
        if self.dto_type is None:
            raise DTOListFieldConfigException(
                'type parameter must be not None.')

        if self.entity_type is None:
            raise DTOListFieldConfigException(
                'entity_type parameter must be not None.')

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            return instance.__dict__[self.storage_name]

    def __set__(self, instance, value):
        if self.validator is None:
            value = self.validate(value)
        else:
            value = self.validator(value)

        # Preenchendo os campos de particionanmento, se necess??rio (normalmente: tenant e grupo_empresarial)
        self.set_partition_fields(instance, value)

        instance.__dict__[self.storage_name] = value

    def set_partition_fields(self, instance, value):
        """
        Preenchendo os campos de particionanmento dos objetos da lista, se necess??rio (normalmente: tenant e grupo_empresarial).
        """

        if hasattr(instance.__class__, 'partition_fields') and value is not None:
            for item in value:
                for partition_field in instance.__class__.partition_fields:
                    if (
                        hasattr(instance, partition_field)
                        and hasattr(item, partition_field)
                        # TODO Analisar se devo descomentar a compara????o abaixo que deixa gravar com campos de parti????o
                        # diferentes entre classe mestre e detalhe (caso se especifique diferente no detalhe)
                        # Talvez falte aqui a compara????o de tipo de relacionamento como composi????o (quando n??o ?? composi????o
                        # a diferen??a pode fazer sentido)
                        # and getattr(item, partition_field) is None
                        and getattr(instance, partition_field) != getattr(item, partition_field)
                    ):
                        partition_value = getattr(instance, partition_field)
                        setattr(item, partition_field, partition_value)

    def validate(self, value):
        """
        Default validator (ckecking default constraints: not null, type, min and max).
        """

        # Checking not null constraint
        if (self.not_null) and (value is None or (isinstance(value, list) and len(value) <= 0)):
            raise ValueError(
                f"O campo {self.storage_name} deve ser preechido. Valor recebido: {value}.")

        # Checking if received value is a list
        if value is not None and not isinstance(value, list):
            raise ValueError(
                f"O valor recebido para o campo {self.storage_name} deveria ser uma lista. Valor recebido: {value}.")

        # Checking type constraint
        # TODO Ver como suportar typing
        if self.dto_type is not None and value is not None and len(value) > 0 and not isinstance(value[0], self.dto_type):
            raise ValueError(
                f"Os items da lista {self.storage_name} deveriam se do tipo {self.dto_type.__name__}. Valor recebido: {value}.")

        # Checking min constraint
        if self.min is not None and len(value) < self.min:
            raise ValueError(
                f"A lista {self.storage_name} deve ter mais do que {self.min} itens. Valor recebido: {value}.")

        # Checking min constraint
        if self.max is not None and len(value) > self.max:
            raise ValueError(
                f"A lista {self.storage_name} deve ter menos do que {self.max} itens. Valor recebido: {value}.")

        return value
