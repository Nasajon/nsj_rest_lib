import typing

from nsj_rest_lib.descriptor.dto_left_join_field import EntityRelationOwner
from nsj_rest_lib.entity.entity_base import EntityBase


class DTOObjectField:
    _ref_counter = 0

    def __init__(
        self,
        entity_type: EntityBase = None,
        relation_field: str = None,
        entity_relation_owner: EntityRelationOwner = EntityRelationOwner.SELF,
        not_null: bool = False,
        resume: bool = False,
        validator: typing.Callable = None,
    ):
        """
        -----------
        Parameters:
        -----------
        entity_type: Expected entity type for the related DTO (must be subclasse from EntityBase).
        relation_field: Nome do campo, usado na query, para correlacionar as entidades (correspondete
            ao campo usado no "on" de um "join").
        entity_relation_owner: Indica qual entidade contém o campo que aponta o relacionamento (
            se for EntityRelationField.OTHER, implica que a entidade apontada pela classe de DTO
            passada no decorator, é que contem o campo; se for o EntityRelationField.SELF, indica
            que o próprio DTO que contém o campo).
        type: Tipo esperado para a propriedade. Se for do tipo enum.Enum, o valor recebido, para atribuição à propriedade, será convertido para o enumerado.
        not_null: O campo não poderá ser None, ou vazio, no caso de strings.
        resume: O campo será usado como resumo, isto é, será sempre rotornado num HTTP GET que liste os dados (mesmo que não seja solicitado por meio da query string "fields").
        validator: Função que recebe o valor (a ser atribuído), e retorna o mesmo valor após algum
            tipo de tratamento (como adição ou remoção, automática, de formatação).
        """
        self.name = None
        self.entity_type = entity_type
        self.relation_field = relation_field
        self.entity_relation_owner = entity_relation_owner
        self.expected_type = type
        self.not_null = not_null
        self.resume = resume
        self.validator = validator

        self.storage_name = f"_{self.__class__.__name__}#{self.__class__._ref_counter}"
        self.__class__._ref_counter += 1

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            return instance.__dict__[self.storage_name]

    def __set__(self, instance, value):
        try:
            # Checking not null constraint
            if self.not_null and value is None:
                raise ValueError(
                    f"{self.storage_name} deve estar preenchido. Valor recebido: {value}."
                )

            if value is not None:
                if not isinstance(value, self.expected_type):
                    raise ValueError(
                        f"O Objeto não é do tipo informado. Valor recebido: {value}."
                    )

            if self.validator is not None:
                value = self.validator(self, value)
        except ValueError:
            if not (
                "escape_validator" in instance.__dict__
                and instance.__dict__["escape_validator"] == True
            ):
                raise

        instance.__dict__[self.storage_name] = value
