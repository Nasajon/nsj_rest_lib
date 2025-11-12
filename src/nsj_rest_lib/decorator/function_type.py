import functools
from typing import Optional, Type

from nsj_rest_lib.descriptor.function_relation_field import FunctionRelationField
from nsj_rest_lib.descriptor.function_field import FunctionField
from nsj_rest_lib.entity.function_type_base import FunctionTypeBase


class FunctionType:
    type_base_class: Type[FunctionTypeBase] = FunctionTypeBase

    def __init__(self, type_name: str, function_name: str) -> None:
        if not type_name or not function_name:
            raise ValueError(
                "Os parâmetros 'type_name' e 'function_name' são obrigatórios."
            )

        self.type_name = type_name
        self.function_name = function_name

    def __call__(self, cls: Type[FunctionTypeBase]):
        functools.update_wrapper(self, cls)

        if not issubclass(cls, self.type_base_class):
            raise ValueError(
                f"Classes decoradas com @{self.__class__.__name__} devem herdar de {self.type_base_class.__name__}."
            )

        self._check_class_attribute(cls, "type_name", self.type_name)
        self._check_class_attribute(cls, "function_name", self.function_name)
        self._check_class_attribute(cls, "fields_map", {})
        self._check_class_attribute(
            cls, "_dto_function_mapping_cache", {}
        )

        annotations = dict(getattr(cls, "__annotations__", {}) or {})

        for key, attr in cls.__dict__.items():
            descriptor: Optional[FunctionField] = None

            if isinstance(attr, (FunctionField, FunctionRelationField)):
                descriptor = attr
            elif key in annotations:
                descriptor = attr
                if not isinstance(
                    attr, (FunctionField, FunctionRelationField)
                ):
                    descriptor = FunctionField()

            if descriptor:
                descriptor.storage_name = key
                descriptor.name = key
                if key in annotations:
                    descriptor.expected_type = annotations[key]
                    if isinstance(descriptor, FunctionRelationField):
                        descriptor.configure_related_type(annotations[key], key)
                cls.fields_map[key] = descriptor

        return cls

    def _check_class_attribute(self, cls: object, attr_name: str, value):
        if attr_name not in cls.__dict__:
            setattr(cls, attr_name, value)
