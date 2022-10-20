import datetime
import enum
import re
import typing

from decimal import Decimal
import uuid

from nsj_rest_lib.descriptor.filter_operator import FilterOperator


class DTOFieldFilter:

    def __init__(
        self,
        name: str = None,
        operator: FilterOperator = FilterOperator.EQUALS
    ):
        self.name = name
        self.operator = operator
        self.field_name = None

    def set_field_name(self, field_name: str):
        self.field_name = field_name


class DTOField:
    _ref_counter = 0

    def __init__(
        self,
        type: object = None,
        not_null: bool = False,
        resume: bool = False,
        min: int = None,
        max: int = None,
        validator: typing.Callable = None,
        strip: bool = False,
        entity_field: str = None,
        filters: typing.List[DTOFieldFilter] = None,
        pk: bool = False,
        use_default_validator: bool = True,
        default_value: typing.Union[typing.Callable, typing.Any] = None,
        partition_data: bool = False
    ):
        """
        -----------
        Parameters:
        -----------
        type: Expected type for the field. If it is an enum.Enum, the receive value (to set), will be converted.
        not_null: The field cannot be None (or empty, for strings).
        resume: The field is used as a resume field (returned in get list request).
        min: Min value expected (min length for strings, and min value for int, float or Decimal).
        max: Max value expected (max length for strings, and amx value for int, float or Decimal).
        validator: Function that receives the value (to be setted), and returns the same value (after any adjust).
          This function overrides the default behaviour and all default constraints.
        strip: Usefull only for strings. The value will be stript before stored.
        entity_field: Name of equivalent field in entity class.
        """
        self.expected_type = type
        self.not_null = not_null
        self.resume = resume
        self.min = min
        self.max = max
        self.validator = validator
        self.strip = strip
        self.entity_field = entity_field
        self.filters = filters
        self.pk = pk
        self.use_default_validator = use_default_validator
        self.default_value = default_value
        self.partition_data = partition_data

        self.storage_name = f"_{self.__class__.__name__}#{self.__class__._ref_counter}"
        self.__class__._ref_counter += 1

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            return instance.__dict__[self.storage_name]

    def __set__(self, instance, value):
        if self.validator is None:
            if self.use_default_validator:
                value = self.validate(self, value)
        else:
            if self.use_default_validator:
                value = self.validate(self, value)
            value = self.validator(self, value)

        instance.__dict__[self.storage_name] = value

    def validate(self, dto_field: "DTOField", value):
        """
        Default validator (ckecking default constraints: not null, type, min, max and enum types).
        """

        # Checking not null constraint
        if (self.not_null) and (value is None or (isinstance(value, str) and len(value.strip()) <= 0)):
            raise ValueError(
                f"{self.storage_name} deve estar preenchido. Valor recebido: {value}.")

        # Checking type constraint
        # TODO Ver como suportar typing
        if self.expected_type is not None and not isinstance(value, self.expected_type) and value is not None:
            value = self.validate_type(value)

        # Checking min constraint
        if self.min is not None:
            if isinstance(value, str) and (len(value) < self.min):
                raise ValueError(
                    f"{self.storage_name} deve conter no mínimo {self.min} caracteres. Valor recebido: {value}.")
            elif (isinstance(value, int) or isinstance(value, float) or isinstance(value, Decimal)) and (value < self.min):
                raise ValueError(
                    f"{self.storage_name} deve ser maior ou igual a {self.min}. Valor recebido: {value}.")

        # Checking min constraint
        if self.max is not None:
            if isinstance(value, str) and (len(value) > self.max):
                raise ValueError(
                    f"{self.storage_name} deve conter no máximo {self.max} caracteres. Valor recebido: {value}.")
            elif (isinstance(value, int) or isinstance(value, float) or isinstance(value, Decimal)) and (value > self.max):
                raise ValueError(
                    f"{self.storage_name} deve ser menor ou igual a {self.max}. Valor recebido: {value}.")

        # Striping strings (if desired)
        if isinstance(value, str) and self.strip:
            value = value.strip()

        return value

    def validate_type(self, value):
        """
        Valida o value recebido, de acordo com o tipo esperado, e faz as conversões necessárias (se possível).
        """

        # Montando expressões regulares para as validações
        matcher_uuid = re.compile(
            '^[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}$')
        matcher_datetime = re.compile(
            '^(\d\d\d\d)-(\d\d)-(\d\d)[T,t](\d\d):(\d\d):(\d\d)$')
        matcher_date = re.compile('^(\d\d\d\d)-(\d\d)-(\d\d)$')

        # Validação por regex
        if (
            self.expected_type is datetime.datetime
            or self.expected_type is datetime.date
        ) and isinstance(value, str):
            # Verificando se pode ser alterado de str para UUID
            match_datetime = matcher_datetime.search(value)
            match_date = matcher_date.search(value)

            if match_datetime:
                ano = int(match_datetime.group(1))
                mes = int(match_datetime.group(2))
                dia = int(match_datetime.group(3))
                hora = int(match_datetime.group(4))
                minuto = int(match_datetime.group(5))
                segundo = int(match_datetime.group(6))

                value = datetime.datetime(
                    year=ano, month=mes, day=dia, hour=hora, minute=minuto, second=segundo)
            elif match_date:
                ano = int(match_date.group(1))
                mes = int(match_date.group(2))
                dia = int(match_date.group(3))

                value = datetime.date(year=ano, month=mes, day=dia)

        # Validação direta de tipos
        erro_tipo = False
        if isinstance(self.expected_type, enum.EnumMeta):
            # Enumerados
            try:
                value = self.expected_type(value)
            except ValueError as e:
                raise ValueError(
                    f"{self.storage_name} não é um {self.expected_type.__name__} válido. Valor recebido: {value}.")
        elif self.expected_type is bool and isinstance(value, int):
            # Booleanos
            # Converting int to bool (0 is False, otherwise is True)
            value = (value == 0)
        elif self.expected_type is datetime.datetime and isinstance(value, datetime.date):
            # Datetime
            # Assumindo hora 0, minuto 0 e segundo 0 (quanto é recebida uma data para campo data + hora)
            value = datetime.datetime(
                value.year, value.month, value.day, 0, 0, 0)
        elif self.expected_type is datetime.date and isinstance(value, datetime.datetime):
            # Date
            # Desprezando hora , minuto e segundo (quanto é recebida uma data + hora, para campo de data)
            value = datetime.date(
                value.year, value.month, value.day)
        elif self.expected_type is uuid.UUID and isinstance(value, str):
            # UUID
            # Verificando se pode ser alterado de str para UUID
            match_uuid = matcher_uuid.search(value)

            if match_uuid:
                value = uuid.UUID(value)
            else:
                erro_tipo = True
        elif self.expected_type is int:
            # Int
            try:
                value = int(value)
            except:
                erro_tipo = True
        elif self.expected_type is float:
            # Int
            try:
                value = float(value)
            except:
                erro_tipo = True
        elif self.expected_type is Decimal:
            # Int
            try:
                value = Decimal(value)
            except:
                erro_tipo = True
        else:
            erro_tipo = True

        if erro_tipo:
            raise ValueError(
                f"{self.storage_name} deve ser do tipo {self.expected_type.__name__}. Valor recebido: {value}.")

        return value
