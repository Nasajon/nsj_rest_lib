import datetime
import enum
import re
import typing
import uuid

from decimal import Decimal
from typing import Any

from nsj_rest_lib.descriptor.filter_operator import FilterOperator


class DTOFieldFilter:
    def __init__(
        self, name: str = None, operator: FilterOperator = FilterOperator.EQUALS
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
        partition_data: bool = False,
        convert_to_entity: typing.Callable = None,
        convert_from_entity: typing.Callable = None,
        unique: str = None,
        candidate_key: bool = False,
    ):
        """
        -----------
        Parameters:
        -----------
        type: Tipo esperado para a propriedade. Se for do tipo enum.Enum, o valor recebido, para atribuição à propriedade, será convertido para o enumerado.
        not_null: O campo não poderá ser None, ou vazio, no caso de strings.
        resume: O campo será usado como resumo, isto é, será sempre rotornado num HTTP GET que liste os dados (mesmo que não seja solicitado por meio da query string "fields").
        min: Menor valor permitido (ou menor comprimento, para strings).
        max: Maior valor permitido (ou maior comprimento, para strings)
        validator: Função que recebe o valor (a ser atribuído), e retorna o mesmo valor após algum tipo de tratamento (como adição ou remoção, automática, de formatação).
        strip: O valor da string sofrerá strip (remoção de espaços no início e no fim), antes de ser guardado (só é útil para strings).
        entity_field: Nome da propriedade equivalente na classe de entity (que reflete a estruturua do banco de dados).
        filters: Lista de filtros adicionais suportados para esta propriedade (adicionais, porque todos as propriedades, por padrão, suportam filtros de igualdade, que podem ser passados por meio de uma query string, com mesmo nome da proriedade, e um valor qualquer a ser comparado).
          Essa lista de filtros consiste em objetos do DTOFieldFilter (veja a documentação da classe para enteder a estrutura de declaração dos filtros).
        pk: Flag indicando se o campo corresponde à chave da entidade corresponednte.
        use_default_validator: Flag indicando se o validator padrão deve ser aplicado à propriedade (esse validator padrão verifica o tipo de dados passado, e as demais verificações recebidas no filed, como, por exemplo, valor máximo, mínio, not_null, etc).
        default_value: Valor padrão de preenchimento da propriedade, caso não se receba conteúdo para a mesma (podendo ser um valor estático, ou uma função a ser chamada no preenchimento).
        partition_data: Flag indicando se esta propriedade participa dos campos de particionamento da entidade, isto é, campos sempre usados nas queries de listagem gravação dos dados, inclusíve para recuperação de entidades relacionadas.
        convert_to_entity: Função para converter o valor contido no DTO, para o(s) valor(es) a serem gravados no objeto de entidade (durante a conversão). É útil para casos onde não há equivalência um para um entre um campo do DTO e um da entidade
          (por exemplo, uma chave de cnpj que pode ser guardada em mais de um campo do BD). Outro caso de uso, é quando um campo tem formatação diferente entre o DTO e a entidade, carecendo de conversão customizada.
          A função recebida deve suportar os parâmetros (dto_value: Any, dto: DTOBase), e retornar um Dict[str, Any], como uma coleção de chaves e valores a serem atribuídos na entidade.
        convert_from_entity: Função para converter o valor contido na Entity, para o(s) valor(es) a serem gravados no objeto DTO (durante a conversão). É útil para casos onde não há equivalência um para um entre um campo do DTO e um da entidade
          (por exemplo, uma chave de cnpj que pode ser guardada em mais de um campo do BD). Outro caso de uso, é quando um campo tem formatação diferente entre o DTO e a entidade, carecendo de conversão customizada.
          A função recebida deve suportar os parâmetros (entity_value: Any, entity_fields: Dict[str, Any]), e retornar um Dict[str, Any], como uma coleção de chaves e valores a serem atribuídos no DTO.
        unique: Permite indicar um nome de chave de unicidade. Cada chave de unicidade é considerada no momento de uma inserção no BD (impedindo duplicações indesejadas).
        candidate_key: Permite indicar que este campo se trata de uma chave candidata (útil para operações unitárias, como GTE e DELETE, pois estas irão verificar se o tipo do dado recebido bate com a PK, ou com as chaves candidatas, para resolver como fará a query).
        """
        self.name = None
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
        self.convert_to_entity = convert_to_entity
        self.convert_from_entity = convert_from_entity
        self.unique = unique
        self.candidate_key = candidate_key

        self.storage_name = f"_{self.__class__.__name__}#{self.__class__._ref_counter}"
        self.__class__._ref_counter += 1

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            return instance.__dict__[self.storage_name]

    def __set__(self, instance, value):
        try:
            if self.validator is None:
                if self.use_default_validator:
                    value = self.validate(self, value, instance)
            else:
                if self.use_default_validator:
                    value = self.validate(self, value, instance)
                value = self.validator(self, value)
        except ValueError as e:
            if not (
                "escape_validator" in instance.__dict__
                and instance.__dict__["escape_validator"] == True
            ):
                raise

        instance.__dict__[self.storage_name] = value

    def validate(self, dto_field: "DTOField", value, instance):
        """
        Default validator (ckecking default constraints: not null, type, min, max and enum types).
        """

        # Checking not null constraint
        if (
            self.not_null
            and (value is None or (isinstance(value, str) and len(value.strip()) <= 0))
            and (
                not dto_field.pk
                or (
                    "generate_default_pk_value" in instance.__dict__
                    and instance.__dict__["generate_default_pk_value"]
                )
            )
        ):
            raise ValueError(
                f"{self.storage_name} deve estar preenchido. Valor recebido: {value}."
            )

        # Checking type constraint
        # TODO Ver como suportar typing
        if (
            self.expected_type is not None
            and not isinstance(value, self.expected_type)
            and value is not None
        ):
            value = self.validate_type(value)

        # Checking min constraint
        if self.min is not None:
            if isinstance(value, str) and (len(value) < self.min):
                raise ValueError(
                    f"{self.storage_name} deve conter no mínimo {self.min} caracteres. Valor recebido: {value}."
                )
            elif (
                isinstance(value, int)
                or isinstance(value, float)
                or isinstance(value, Decimal)
            ) and (value < self.min):
                raise ValueError(
                    f"{self.storage_name} deve ser maior ou igual a {self.min}. Valor recebido: {value}."
                )

        # Checking min constraint
        if self.max is not None:
            if isinstance(value, str) and (len(value) > self.max):
                raise ValueError(
                    f"{self.storage_name} deve conter no máximo {self.max} caracteres. Valor recebido: {value}."
                )
            elif (
                isinstance(value, int)
                or isinstance(value, float)
                or isinstance(value, Decimal)
            ) and (value > self.max):
                raise ValueError(
                    f"{self.storage_name} deve ser menor ou igual a {self.max}. Valor recebido: {value}."
                )

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
            "^[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}$"
        )
        matcher_datetime = re.compile(
            "^(\d\d\d\d)-(\d\d)-(\d\d)[T,t](\d\d):(\d\d):(\d\d)$"
        )
        matcher_date = re.compile("^(\d\d\d\d)-(\d\d)-(\d\d)$")

        matcher_time = re.compile("^(\d\d):(\d\d):(\d\d)$")

        # Validação direta de tipos
        erro_tipo = False
        if self.expected_type is datetime.datetime and isinstance(value, str):
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
                    year=ano,
                    month=mes,
                    day=dia,
                    hour=hora,
                    minute=minuto,
                    second=segundo,
                )
            elif match_date:
                ano = int(match_date.group(1))
                mes = int(match_date.group(2))
                dia = int(match_date.group(3))

                value = datetime.datetime(
                    year=ano, month=mes, day=dia, hour=0, minute=0, second=0
                )
            else:
                erro_tipo = True
        elif self.expected_type is datetime.date and isinstance(value, str):
            match_date = matcher_date.search(value)

            if match_date:
                ano = int(match_date.group(1))
                mes = int(match_date.group(2))
                dia = int(match_date.group(3))

                value = datetime.date(year=ano, month=mes, day=dia)
            else:
                erro_tipo = True
        elif self.expected_type is datetime.time and isinstance(value, str):
            match_time = matcher_time.search(value)
            if match_time:
                hor = int(match_time.group(1))
                min = int(match_time.group(2))
                sec = int(match_time.group(3))

                value = datetime.time(hour=hor, minute=min, second=sec)
            else:
                erro_tipo = True
        elif isinstance(self.expected_type, enum.EnumMeta):
            # Enumerados
            try:
                value = self._convert_enum_from_entity(value)
            except ValueError:
                raise ValueError(
                    f"{self.storage_name} não é um {self.expected_type.__name__} válido. Valor recebido: {value}."
                )
        elif self.expected_type is bool and isinstance(value, int):
            # Booleanos
            # Converting int to bool (0 is False, otherwise is True)
            value = bool(value)
        elif self.expected_type is datetime.datetime and isinstance(
            value, datetime.date
        ):
            # Datetime
            # Assumindo hora 0, minuto 0 e segundo 0 (quanto é recebida uma data para campo data + hora)
            value = datetime.datetime(value.year, value.month, value.day, 0, 0, 0)
        elif self.expected_type is datetime.date and isinstance(
            value, datetime.datetime
        ):
            # Date
            # Desprezando hora , minuto e segundo (quanto é recebida uma data + hora, para campo de data)
            value = datetime.date(value.year, value.month, value.day)
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
        elif self.expected_type is str:
            # Int
            try:
                value = str(value)
            except:
                erro_tipo = True
        else:
            erro_tipo = True

        if erro_tipo:
            raise ValueError(
                f"{self.storage_name} deve ser do tipo {self.expected_type.__name__}. Valor recebido: {value}."
            )

        return value

    def _convert_enum_from_entity(self, value: Any):
        lista_enum = list(self.expected_type)

        # Se o enum estiver vazio
        if len(lista_enum) <= 0:
            return None

        # Verificando o tipo dos valores do enum
        if isinstance(lista_enum[0].value, tuple):
            for item in self.expected_type:
                lista_valores = list(item.value)
                for valor in lista_valores:
                    if valor == value:
                        return item
        else:
            return self.expected_type(value)
