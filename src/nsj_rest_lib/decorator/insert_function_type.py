import functools
from typing import Optional, Type

from nsj_rest_lib.descriptor.insert_function_relation_field import (
    InsertFunctionRelationField,
)
from nsj_rest_lib.descriptor.insert_function_field import InsertFunctionField
from nsj_rest_lib.entity.insert_function_type_base import InsertFunctionTypeBase


class InsertFunctionType:
    def __init__(self, type_name: str, function_name: str) -> None:
        if not type_name or not function_name:
            raise ValueError(
                "Os parâmetros 'type_name' e 'function_name' são obrigatórios."
            )

        self.type_name = type_name
        self.function_name = function_name

    def __call__(self, cls: Type[InsertFunctionTypeBase]):
        functools.update_wrapper(self, cls)

        if not issubclass(cls, InsertFunctionTypeBase):
            raise ValueError(
                "Classes decoradas com @InsertFunctionType devem herdar de InsertFunctionTypeBase."
            )

        self._check_class_attribute(cls, "type_name", self.type_name)
        self._check_class_attribute(cls, "function_name", self.function_name)
        self._check_class_attribute(cls, "fields_map", {})
        self._check_class_attribute(
            cls, "_dto_insert_function_mapping_cache", {}
        )

        annotations = dict(getattr(cls, "__annotations__", {}) or {})

        for key, attr in cls.__dict__.items():
            descriptor: Optional[InsertFunctionField] = None

            if isinstance(attr, (InsertFunctionField, InsertFunctionRelationField)):
                descriptor = attr
            elif key in annotations:
                descriptor = attr
                if not isinstance(
                    attr, (InsertFunctionField, InsertFunctionRelationField)
                ):
                    descriptor = InsertFunctionField()

            if descriptor:
                descriptor.storage_name = key
                descriptor.name = key
                if key in annotations:
                    descriptor.expected_type = annotations[key]
                    if isinstance(descriptor, InsertFunctionRelationField):
                        descriptor.configure_related_type(annotations[key], key)
                cls.fields_map[key] = descriptor

        return cls

    def _check_class_attribute(self, cls: object, attr_name: str, value):
        if attr_name not in cls.__dict__:
            setattr(cls, attr_name, value)
