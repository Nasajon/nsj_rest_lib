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

        instance.__dict__[self.storage_name] = value

    def validate(self, value):
        """
        Default validator (ckecking default constraints: not null, type, min and max).
        """

        # Checking not null constraint
        if (self.not_null) and (value is None or (isinstance(value, list) and len(value) <= 0)):
            raise ValueError(
                f"{self.storage_name} must be not null (nor empty). Received value: {value}.")

        # Checking if received value is a list
        if value is not None and not isinstance(value, list):
            raise ValueError(
                f"{self.storage_name} is not list. Received value: {value}.")

        # Checking type constraint
        # TODO Ver como suportar typing
        if self.dto_type is not None and value is not None and len(value) > 0 and not isinstance(value[0], self.dto_type):
            raise ValueError(
                f"{self.storage_name} must be of type {self.dto_type.__name__}. Received value: {value}.")

        # Checking min constraint
        if self.min is not None and len(value) < self.min:
            raise ValueError(
                f"{self.storage_name} must have more than {self.min} itens. Received value: {value}.")

        # Checking min constraint
        if self.max is not None and len(value) > self.max:
            raise ValueError(
                f"{self.storage_name} must have less than {self.max} caracters. Received value: {value}.")

        return value
