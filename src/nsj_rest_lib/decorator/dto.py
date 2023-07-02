from typing import Any, Dict

from nsj_rest_lib.descriptor.conjunto_type import ConjuntoType
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.descriptor.dto_list_field import DTOListField


class DTO:
    def __init__(
        self,
        fixed_filters: Dict[str, Any] = None,
        conjunto_type: ConjuntoType = None,
        conjunto_field: str = None,
    ) -> None:
        super().__init__()

        self._fixed_filters = fixed_filters
        self._conjunto_type = conjunto_type
        self._conjunto_field = conjunto_field

        if (self._conjunto_type is None and self._conjunto_field is not None) or (
            self._conjunto_type is not None and self._conjunto_field is None
        ):
            raise Exception(
                "Os parâmetros conjunto_type e conjunto_field devem ser preenchidos juntos (se um for não nulo, ambos devem ser preenchidos)."
            )

    def __call__(self, cls: object):
        """
        Iterating DTO class to handle DTOFields descriptors.
        """

        # Creating resume_fields in cls, if needed
        self._check_class_attribute(cls, "resume_fields", set())

        # Creating fields_map in cls, if needed
        self._check_class_attribute(cls, "fields_map", {})

        # Creating list_fields_map in cls, if needed
        self._check_class_attribute(cls, "list_fields_map", {})

        # Creating field_filters_map in cls, if needed
        self._check_class_attribute(cls, "field_filters_map", {})

        # Creating pk_field in cls, if needed
        # TODO Refatorar para suportar PKs compostas
        self._check_class_attribute(cls, "pk_field", None)

        # Criando a propriedade "partition_fields" na classe "cls", se necessário
        self._check_class_attribute(cls, "partition_fields", set())

        # Iterating for the class attributes
        for key, attr in cls.__dict__.items():
            # Test if the attribute uses the DTOFiel descriptor
            if isinstance(attr, DTOField):
                # Storing field in fields_map
                getattr(cls, "fields_map")[key] = attr

                # Setting a better name to storage_name
                attr.storage_name = f"{key}"

                # Checking filters name
                self._check_filters(cls, key, attr)

                # Copying type from annotation (if exists)
                if key in cls.__annotations__:
                    attr.expected_type = cls.__annotations__[key]

                # Checking if it is a resume field (to store)
                if attr.resume:
                    resume_fields = getattr(cls, "resume_fields")
                    if not (key in resume_fields):
                        resume_fields.add(key)

                # TODO Refatorar para suportar PKs compostas
                # Setting PK info
                if attr.pk:
                    setattr(cls, "pk_field", f"{key}")

                # Verifica se é um campo de particionamento, e o guarda em caso positivo
                if attr.partition_data:
                    partition_fields = getattr(cls, "partition_fields")
                    if not (key in partition_fields):
                        partition_fields.add(key)

            elif isinstance(attr, DTOListField):
                # Storing field in fields_map
                getattr(cls, "list_fields_map")[key] = attr

                # Setting a better name to storage_name
                attr.storage_name = f"{key}"

        # Setting fixed filters
        setattr(cls, "fixed_filters", self._fixed_filters)

        # Setting tipo de Conjunto
        setattr(cls, "conjunto_type", self._conjunto_type)
        setattr(cls, "conjunto_field", self._conjunto_field)

        return cls

    def _check_filters(self, cls: object, field_name: str, dto_field: DTOField):
        """
        Check filters (if exists), and setting default filter name.
        """

        if dto_field.filters is None:
            return

        # Handling each filter
        for filter in dto_field.filters:
            # Resolving filter name
            filter_name = field_name
            if filter.name is not None:
                filter_name = filter.name

            # Storing field filter name
            filter.field_name = field_name

            # Adding into field filters map
            field_filters_map = getattr(cls, "field_filters_map")
            field_filters_map[filter_name] = filter

    def _check_class_attribute(self, cls: object, attr_name: str, default_value: Any):
        """
        Add attribute "attr_name" in class "cls", if not exists.
        """

        if attr_name not in cls.__dict__:
            setattr(cls, attr_name, default_value)
