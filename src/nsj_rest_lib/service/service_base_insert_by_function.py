import typing as ty

from nsj_rest_lib.descriptor.dto_list_field import DTOListField
from nsj_rest_lib.descriptor.dto_object_field import DTOObjectField
from nsj_rest_lib.descriptor.dto_one_to_one_field import DTOOneToOneField
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.entity.insert_function_type_base import InsertFunctionTypeBase


class ServiceBaseInsertByFunction:
    _insert_function_type_class: ty.Optional[ty.Type[InsertFunctionTypeBase]] = None

    def set_insert_function_type_class(
        self,
        insert_function_type_class: ty.Optional[
            ty.Type[InsertFunctionTypeBase]
        ],
    ):
        if insert_function_type_class is not None and not issubclass(
            insert_function_type_class, InsertFunctionTypeBase
        ):
            raise ValueError(
                "A classe informada em insert_function_type_class deve herdar de InsertFunctionTypeBase."
            )

        self._insert_function_type_class = insert_function_type_class

        if (
            self._insert_function_type_class is not None
            and getattr(self, "_dto_class", None) is not None
        ):
            self._insert_function_type_class.get_insert_function_mapping(
                self._dto_class
            )

    def _build_insert_function_type_object(
        self,
        dto: DTOBase,
        insert_function_type_class: ty.Optional[
            ty.Type[InsertFunctionTypeBase]
        ] = None,
    ):
        target_insert_class = (
            insert_function_type_class or self._insert_function_type_class
        )

        if target_insert_class is None:
            return None

        mapping_dto_class = (
            dto.__class__
            if insert_function_type_class is not None
            else self._dto_class
        )

        mapping = target_insert_class.get_insert_function_mapping(
            mapping_dto_class
        )

        return self._build_insert_function_type_object_from_mapping(
            dto,
            target_insert_class,
            mapping,
        )

    def _build_insert_function_type_object_from_mapping(
        self,
        dto: DTOBase,
        insert_function_type_class: ty.Type[InsertFunctionTypeBase],
        mapping: ty.Dict[str, ty.Tuple[str, ty.Any]],
    ) -> InsertFunctionTypeBase:
        if mapping is None:
            raise ValueError(
                f"InsertFunctionType '{insert_function_type_class.__name__}' não possui mapeamentos configurados."
            )

        insert_object = insert_function_type_class()
        dto_values = dto.__dict__

        for function_field_name, (dto_field_name, descriptor) in mapping.items():
            if not hasattr(dto, dto_field_name):
                raise ValueError(
                    f"DTO '{dto.__class__.__name__}' não possui o campo '{dto_field_name}' utilizado no InsertFunctionType '{insert_function_type_class.__name__}'."
                )

            value = getattr(dto, dto_field_name, None)

            convert_to_function = getattr(descriptor, "convert_to_function", None)
            if convert_to_function is not None:
                converted_values = convert_to_function(value, dto_values) or {}

                if not isinstance(converted_values, dict):
                    raise ValueError(
                        f"A função 'convert_to_function' configurada no campo '{dto_field_name}' deve retornar um dicionário."
                    )

                if function_field_name not in converted_values:
                    converted_values = {
                        function_field_name: None,
                        **converted_values,
                    }

                for target_field, target_value in converted_values.items():
                    setattr(insert_object, target_field, target_value)
                continue

            if isinstance(
                descriptor,
                (DTOListField, DTOObjectField, DTOOneToOneField),
            ):
                relation_value = self._build_insert_function_relation_value(
                    descriptor,
                    value,
                )
                if relation_value is not None:
                    setattr(insert_object, function_field_name, relation_value)
                continue

            setattr(insert_object, function_field_name, value)

        return insert_object

    def _build_insert_function_relation_value(
        self,
        descriptor: ty.Union[DTOListField, DTOObjectField, DTOOneToOneField],
        value: ty.Any,
    ):
        if value is None:
            return None

        insert_type_class = getattr(descriptor, "insert_function_type", None)
        if insert_type_class is None:
            raise ValueError(
                f"O campo '{descriptor.name}' precisa informar 'insert_function_type' para relacionamentos."
            )

        dto_class = self._get_relation_dto_class(descriptor)
        mapping = insert_type_class.get_insert_function_mapping(dto_class)

        if isinstance(descriptor, DTOListField):
            related_values = []
            for item in value:
                dto_instance = self._ensure_dto_instance(item, dto_class)
                if dto_instance is None:
                    continue
                related_values.append(
                    self._build_insert_function_type_object_from_mapping(
                        dto_instance,
                        insert_type_class,
                        mapping,
                    )
                )
            return related_values

        dto_instance = self._ensure_dto_instance(value, dto_class)
        if dto_instance is None:
            return None

        return self._build_insert_function_type_object_from_mapping(
            dto_instance,
            insert_type_class,
            mapping,
        )

    def _get_relation_dto_class(
        self, descriptor: ty.Union[DTOListField, DTOObjectField, DTOOneToOneField]
    ) -> ty.Type[DTOBase]:
        if isinstance(descriptor, DTOListField):
            return descriptor.dto_type
        return descriptor.expected_type

    def _ensure_dto_instance(
        self,
        value: ty.Any,
        dto_class: ty.Type[DTOBase],
    ) -> ty.Optional[DTOBase]:
        if value is None:
            return None

        if isinstance(value, dto_class):
            return value

        if isinstance(value, dict):
            return dto_class(**value)

        raise ValueError(
            f"O valor informado para o relacionamento deveria ser do tipo '{dto_class.__name__}'. Valor recebido: {type(value)}."
        )
