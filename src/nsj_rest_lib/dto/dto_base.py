import abc
import copy
# import uuid

from typing import Any, Dict, List, Set

from nsj_rest_lib.entity.entity_base import EMPTY, EntityBase
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

    def __init__(self, entity: EntityBase = None, **kwargs) -> None:
        super().__init__()

        # Transformando a entity em dict (se houver uma entity)
        if entity is not None:
            kwargs = copy.deepcopy(entity.__dict__)

        # Setando os campos registrados como fields simples
        for field in self.__class__.fields_map:
            # Recuperando a configuração do campo
            dto_field = self.__class__.fields_map[field]

            # Tratando do valor default
            if dto_field.default_value is not None and kwargs.get(field, None) is None:
                default_value = dto_field.default_value
                if callable(dto_field.default_value):
                    default_value = dto_field.default_value()
                kwargs[field] = default_value

            # Verificando se é preciso converter o nome do field para o nome correspondente no Entity
            entity_field = field
            if entity is not None:
                if dto_field.entity_field is not None:
                    entity_field = dto_field.entity_field

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
                            f"O campo {field} deveria ser uma lista do tipo {dto_list_field.dto_type}.")

                    related_itens = []
                    for item in kwargs[field]:
                        # Preenchendo os campos de particionanmento, se necessário (normalmente: tenant e grupo_empresarial)
                        for partition_field in self.__class__.partition_fields:
                            if (
                                (
                                    not (partition_field in item)
                                    or item[partition_field] is None
                                )
                                and partition_field in dto_list_field.dto_type.partition_fields
                            ):
                                partition_value = getattr(
                                    self, partition_field)
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

    def convert_from_entity(self, obj: EntityBase):
        """
        Popula DTO a partir de um objeto de entidade (considerando
        apenas as propriedades descritas como DTOFields).

        Este método retorna self (a própria referencia ao objeto).
        """

        for attribute in self.__dict__:

            # Ignoring non DTO fields
            if not (attribute in self.__class__.fields_map):
                continue

            # Getting DTO field config
            dto_field = self.__class__.fields_map[attribute]

            # Checking if exists a different name to equivalent field in entity class
            attr_name = attribute
            if dto_field.entity_field is not None:
                attr_name = dto_field.entity_field

            # Checking if exists the equivalent attribute in entity object (skiping, if not)
            if not hasattr(obj, attr_name):
                continue

            # Getting entity attribute
            entity_attr = getattr(obj, attr_name, None)

            # Setting value localy
            setattr(self, attribute, entity_attr)

        return self

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

            # Convertendo None para EMPTY (se desejado)
            if value is None and none_as_empty:
                value = EMPTY

            # Setando na entidade
            setattr(entity, entity_field, value)

        return entity

    def convert_to_dict(self, fields: Dict[str, List[str]] = None, just_resume: bool = False):
        """
        Converte DTO para dict
        """

        # Resolving fields to use
        if fields is None:
            fields = {'root': self.resume_fields}

        if just_resume:
            fields = {'root': self.resume_fields}
        else:
            fields['root'] = fields['root'].union(self.resume_fields)

        # Making result maps
        result = {}

        # Converting simple fields
        for field in self.fields_map:
            if not field in fields['root']:
                continue

            result[field] = getattr(self, field)

        # Converting list fields
        for field in self.list_fields_map:
            if not field in fields['root']:
                continue

            # Criando o mapa de fileds para a entidade aninhada
            internal_fields = None
            if field in fields:
                internal_fields = {'root': fields[field]}

            # Recuperando o valor do atributo
            value = getattr(self, field)
            if value is None:
                value = []

            # Convetendo a lista de DTOs aninhados
            result[field] = [item.convert_to_dict(
                internal_fields, just_resume) for item in value]

        return result
