import functools

from typing import Any, List



class EntityField:
    expected_type: object


class Entity:
    def __init__(
        self,
        table_name: str,
        pk_field: str,
        default_order_fields: List[str]
    ) -> None:
        super().__init__()

        self.table_name = table_name
        self.pk_field = pk_field
        self.default_order_fields = default_order_fields

    def __call__(self, cls):
        """
        Tratando dos tipos de dados dos atributos, e criando os getters necessários.
        """

        # Mantém metadados da classe original
        functools.update_wrapper(self, cls)

        # Guardando o nome da tabela na classe
        self._check_class_attribute(cls, "table_name", self.table_name)

        # Guardando o nome do campo PK na classe
        self._check_class_attribute(cls, "pk_field", self.pk_field)

        # Guardando a lista default de ordenação, na classe
        self._check_class_attribute(
            cls, "default_order_fields", self.default_order_fields
        )

        # Creating fields_map in cls, if needed
        self._check_class_attribute(cls, "fields_map", {})

        # Iterando pelos atributos de classe
        for key, attr in cls.__dict__.items():
            # Copiando o tipo a partir da anotação de tipo (se existir)
            if key in cls.__annotations__:
                atributo = attr
                if not isinstance(attr, EntityField):
                    atributo = EntityField()

                atributo.expected_type = cls.__annotations__[key]

                # Guardando o atributo no fields_map
                getattr(cls, "fields_map")[key] = atributo

        return cls

    def _check_class_attribute(self, cls: object, attr_name: str, default_value: Any):
        """
        Add attribute "attr_name" in class "cls", if not exists.
        """

        if attr_name not in cls.__dict__:
            setattr(cls, attr_name, default_value)