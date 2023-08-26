import abc
import copy
import enum

# import uuid

from typing import Any, Dict, List, Set, Union

from nsj_rest_lib.entity.entity_base import EMPTY, EntityBase
from nsj_rest_lib.descriptor.conjunto_type import ConjuntoType
from nsj_rest_lib.descriptor.dto_field import DTOField, DTOFieldFilter


class DTOBase(abc.ABC):
    resume_fields: Set[str] = set()
    partition_fields: Set[str] = set()
    fields_map: Dict[str, DTOField] = {}
    list_fields_map: dict = {}
    field_filters_map: Dict[str, DTOFieldFilter]
    # TODO Refatorar para suportar PK composto
    pk_field: str
    fixed_filters: Dict[str, Any]
    conjunto_type: ConjuntoType
    conjunto_field: str
    escape_validator: bool
    uniques: Dict[str, Set[str]]
    candidate_keys: List[str]

    def __init__(
        self,
        entity: Union[EntityBase, dict] = None,
        escape_validator: bool = False,
        generate_default_pk_value: bool = True,
        **kwargs,
    ) -> None:
        super().__init__()

        self.escape_validator = escape_validator
        self.generate_default_pk_value = generate_default_pk_value

        # Transformando a entity em dict (se houver uma entity)
        if entity is not None:
            kwargs = (
                copy.deepcopy(entity)
                if type(entity) is dict
                else copy.deepcopy(entity.__dict__)
            )

        # Setando os campos registrados como fields simples
        for field in self.__class__.fields_map:
            # Recuperando a configuração do campo
            dto_field = self.__class__.fields_map[field]

            # Tratando do valor default
            if (
                dto_field.default_value is not None
                and kwargs.get(field, None) is None
                and (not dto_field.pk or generate_default_pk_value)
            ):
                default_value = dto_field.default_value
                if callable(dto_field.default_value):
                    default_value = dto_field.default_value()
                kwargs[field] = default_value

            # Verificando se é preciso converter o nome do field para o nome correspondente no Entity
            entity_field = field
            if entity is not None:
                if dto_field.entity_field is not None:
                    entity_field = dto_field.entity_field

                # Verificando se o campo carece de conversão customizada
                if dto_field.convert_from_entity is not None:
                    fields_converted = dto_field.convert_from_entity(
                        kwargs[entity_field], kwargs
                    )
                    if field not in fields_converted:
                        setattr(self, field, None)

                    for converted_key in fields_converted:
                        setattr(self, converted_key, fields_converted[converted_key])

                    continue

            # Atribuindo o valor à propriedade do DTO
            if entity_field in kwargs:
                setattr(self, field, kwargs[entity_field])
            else:
                setattr(self, field, None)

        # Setando os campos registrados como fields de lista
        if entity is None:
            for field in self.__class__.list_fields_map:
                dto_list_field = self.__class__.list_fields_map[field]

                if field in kwargs:
                    if not isinstance(kwargs[field], list):
                        raise ValueError(
                            f"O campo {field} deveria ser uma lista do tipo {dto_list_field.dto_type}."
                        )

                    related_itens = []
                    for item in kwargs[field]:
                        # Preenchendo os campos de particionanmento, se necessário (normalmente: tenant e grupo_empresarial)
                        for partition_field in self.__class__.partition_fields:
                            if (
                                (
                                    partition_field not in item
                                    or item[partition_field] is None
                                )
                                and partition_field
                                in dto_list_field.dto_type.partition_fields
                            ):
                                partition_value = getattr(self, partition_field)
                                item[partition_field] = partition_value

                        # Criando o DTO relacionado
                        item_dto = dto_list_field.dto_type(**item)

                        # Adicionando o DTO na lista do relacionamento
                        related_itens.append(item_dto)

                    setattr(self, field, related_itens)
                else:
                    setattr(self, field, None)

        # Tratando do ID automático
        # if generate_pk_uuid:
        #     if getattr(self, self.__class__.pk_field) is None:
        #         setattr(self, self.__class__.pk_field, uuid.uuid4())

    def convert_to_entity(self, entity_class: EntityBase, none_as_empty: bool = False):
        """
        Cria uma instância da entidade, e a popula com os dados do DTO
        corrente.

        É importante notar que as equivalências dos nomes dos campos
        são tratadas neste método.
        """

        entity = entity_class()

        for field, dto_field in self.__class__.fields_map.items():
            # Verificando se é preciso realizar uma tradução de nome do campo
            entity_field = field
            if dto_field.entity_field is not None:
                entity_field = dto_field.entity_field

            # Verificando se o campo existe na entity
            if not hasattr(entity, entity_field):
                continue

            # Recuperando o valor
            value = getattr(self, field)

            # Verificando se é necessária alguma conversão customizada
            custom_value_conveted = DTOBase.custom_convert_value_to_entity(
                value,
                dto_field,
                entity_field,
                none_as_empty,
                self.__dict__,
            )
            for key in custom_value_conveted:
                setattr(entity, key, custom_value_conveted[key])

            if len(custom_value_conveted) > 0:
                continue

            # Convertendo o value para o correspondente nos fields
            value = DTOBase.convert_value_to_entity(
                value,
                dto_field,
                none_as_empty,
                entity_class,
            )

            # Setando na entidade
            setattr(entity, entity_field, value)

        return entity

    def custom_convert_value_to_entity(
        value: Any,
        dto_field: DTOField,
        entity_field: str,
        none_as_empty: bool,
        dto_values: Dict[str, any],
    ):
        # Verificando se é necessária uma conversão customizada
        retorno = {}
        if value is not None and dto_field.convert_to_entity is not None:
            fields_converted = dto_field.convert_to_entity(value, dto_values)
            if entity_field not in fields_converted:
                retorno[entity_field] = None if not none_as_empty else EMPTY

            for converted_key in fields_converted:
                value = fields_converted[converted_key]
                if value is None and none_as_empty:
                    value = EMPTY
                retorno[converted_key] = value

        return retorno

    def convert_value_to_entity(
        value: Any,
        dto_field: DTOField,
        none_as_empty: bool,
        entity_class: EntityBase,
    ) -> Any:
        # Enumerados
        if isinstance(dto_field.expected_type, enum.EnumMeta):
            try:
                return DTOBase._convert_enum_to_entity(value, dto_field)
            except ValueError:
                # Retornando o pórpio valor, caso se deseje converter um enumerado que não seja válido
                # Isso é, aceitando enumerados inválidos (só para os filtros)
                return value.value if isinstance(value, enum.Enum) else str(value)

        # Bool to int
        entity_fields_map = getattr(entity_class, "fields_map", {})
        entity_field_name = dto_field.entity_field or dto_field.name
        if (
            isinstance(value, bool)
            and entity_field_name in entity_fields_map
            and entity_fields_map[entity_field_name].expected_type == int
        ):
            return 1 if value else 0

        # Convertendo None para EMPTY (se desejado)
        if value is None:
            if none_as_empty:
                return EMPTY
            else:
                return value

        return value

    def _convert_enum_to_entity(
        value: Any,
        dto_field: DTOField,
    ):
        lista_enum = list(dto_field.expected_type)

        # Se o enum estiver vazio
        if len(lista_enum) <= 0:
            return None

        # Verificando o tipo dos valores do enum
        if isinstance(lista_enum[0].value, tuple):
            # Recuperando o item correspondente do enumerado
            enumerado = value
            if not isinstance(value, dto_field.expected_type):
                for item in dto_field.expected_type:
                    lista_valores = list(item.value)
                    for valor in lista_valores:
                        if valor == value:
                            enumerado = item

            # Convertendo do enumerado para o valor desejado na entidade
            if "get_entity_index" in enumerado.__dict__:
                tuple_index = enumerado.get_entity_index()
            else:
                tuple_index = 1

            return enumerado.value[tuple_index]
        else:
            return dto_field.expected_type(value)

    def convert_to_dict(
        self, fields: Dict[str, List[str]] = None, just_resume: bool = False
    ):
        """
        Converte DTO para dict
        """

        # Resolving fields to use
        if fields is None:
            fields = {"root": self.resume_fields}

        if just_resume:
            fields = {"root": self.resume_fields}
        else:
            fields["root"] = fields["root"].union(self.resume_fields)

        # Making result maps
        result = {}

        # Converting simple fields
        for field in self.fields_map:
            if not field in fields["root"]:
                continue

            result[field] = getattr(self, field)

        # Converting list fields
        for field in self.list_fields_map:
            if not field in fields["root"]:
                continue

            # Criando o mapa de fileds para a entidade aninhada
            internal_fields = None
            if field in fields:
                internal_fields = {"root": fields[field]}

            # Recuperando o valor do atributo
            value = getattr(self, field)
            if value is None:
                value = []

            # Convetendo a lista de DTOs aninhados
            result[field] = [
                item.convert_to_dict(internal_fields, just_resume) for item in value
            ]

        return result
