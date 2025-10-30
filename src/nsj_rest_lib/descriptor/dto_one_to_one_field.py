import enum
import typing as ty

from nsj_rest_lib.entity.entity_base import EntityBase

from .dto_field import DTOField

if ty.TYPE_CHECKING is True:
    from nsj_rest_lib.dto.dto_base import DTOBase
    from .dto_left_join_field import EntityRelationOwner
    pass

T = ty.TypeVar('T')

class OTORelationType(enum.IntEnum):
    """The enum for Relation Type for One to One relations."""
    COMPOSITION = 0
    AGGREGATION = 1
    pass

# pylint: disable=too-many-instance-attributes
class DTOOneToOneField:
    _ref_counter = 0

    expected_type: ty.Type['DTOBase']
    relation_type: OTORelationType
    relation_field: ty.Optional[str]
    field: ty.Optional[DTOField]
    entity_relation_owner: 'EntityRelationOwner'
    not_null: bool
    resume: bool
    validator: ty.Optional[ty.Callable[..., ty.Any]]
    description: str
    is_self_related: bool
    entity_field: str

    def __init__(
        self,
        entity_type: ty.Type[EntityBase],
        relation_type: OTORelationType,
        relation_field: ty.Optional[str] = None,
        field: ty.Optional[DTOField] = None,
        entity_relation_owner: 'EntityRelationOwner' = 'self', # type: ignore
        not_null: bool = False,
        resume: bool = False,
        validator: ty.Optional[ty.Callable[['DTOOneToOneField', T], T]] = None,
        description: str = '',
    ):
        """Descriptor used for One to One relations.
        ---------
        Glossary:
        ---------
        - Current DTO: Refers to the DTO that this field is a part of.
        - Related DTO: Refers to the DTO in the annotation of this field.


        -----
        NOTE:
        -----
        At the moment only `entity_relation_owner=EntityRelationOwner.SELF` is
            supported.

        -----------
        Parameters:
        -----------

        - entity_type: Entity type of the `Related DTO`
            (must be a subclasse from EntityBase).

        - relation_type: The type of relation of this field, one of:
            - OTORelationType.COMPOSITION:
                - During POST requests, it attempts to insert the data into the
                    `entity_type` table.
                - During PUT or PATCH requests, it attempts to update the
                    existing records in the `entity_type` table.
            - OTORelationType.AGGREGATION:
                - This type does not interact with the `entity_type` table.
                - It is relevant only in POST, PUT, or PATCH requests if the
                    `relation_field` is `None`. In this case, the value in the
                    `pk_field` of the `Related DTO` will be used in place of
                    the object.

        - relation_field: Name of the field in the `Current DTO` for which the
            value will be used when acquiring the `Related DTO`.
            When it's `None`:
                - It will use the name of the field it was given in
                    the `Current DTO`.
                - It will require `field` have a value.
                - `validator` HAS to be None.
                - At the moment it's not supported when `entity_relation_owner`
                    is NOT EntityRelationField.SELF.

        - field: It is the DTOField that represents the field when
            `relation_field` is None. `field` is ignored when `relation_field`
            is NOT `None`.

        - entity_relation_owner: Indicates which entity contain the
            `relation_field`, it must be one of:
                - EntityRelationField.SELF: The `relation_field` is part of the
                    `Current DTO`.
                - EntityRelationField.OTHER: The `relation_field` is part os the
                    `Related DTO`. NOT Supported when `relation_field` is `None`.

        - not_null: If the field can not be `None`. Only relevant in POST, PUT
            or PATCH requests.

        - resume: If this field will be included by default on GET requests.
            When it's False it becomes required for the field name to be on the
            query string "fields" for it to be returned.

        - validator: Function that receives the instance of this class and the
            value to be checked and returns it. For validation erros MUST throw
            ValueError. Errors are only honored on POST, PUT or PATCH requests.
            HAS to be `None` when `relation_field` is `None`

        - description: Description of this field that can be used in
            documentation.
        """
        self.entity_type = entity_type
        self.relation_type = relation_type
        self.relation_field = relation_field
        self.field = field
        self.entity_relation_owner = entity_relation_owner
        self.not_null = not_null
        self.resume = resume
        self.validator = validator
        self.description = description
        self.entity_field = ''

        self.name = None
        self.expected_type = ty.cast(ty.Type['DTOBase'], type)

        self.storage_name = f"_{self.__class__.__name__}#{self.__class__._ref_counter}"
        self.__class__._ref_counter += 1

        # NOTE: To support EntityRelationOwner.OTHER you will have to modify
        #           `_retrieve_one_to_one_fields in ServiceBase`. do NOT forget
        #           to change the documentation.
        assert self.entity_relation_owner == 'self', \
            "At the moment only `EntityRelationOwner.SELF` is supported."

        assert issubclass(self.entity_type, EntityBase), \
            f"Argument `entity_type` of `DTOOneToOneField` HAS to be" \
            f" a `EntityBase`. Is {repr(self.entity_type)}."

        assert self.relation_field is None \
               or isinstance(self.relation_field, str), \
            f"Argument `entity_type` of `DTOOneToOneField` HAS to be" \
            f" a `str` or `None`. Is {repr(self.entity_type)}."

        self.is_self_related = False
        if self.relation_field is None:
            assert self.entity_relation_owner == 'self', \
                "Self related `DTOOneToOneField` only support" \
                " `EntityRelationOwner.SELF` for now."
            # NOTE: The functions that need to be modified to support relation
            #           owner other than self is:
            #               - _retrieve_one_to_one_fields in ServiceBase;
            #           It's also needed to change the documentation.

            self.is_self_related = True
            assert isinstance(self.field, DTOField), \
                f"Argument `field` of `DTOOneToOneField` HAS to be" \
                f" a `DTOField` when `relation_field` is `None`." \
                f" Is {repr(self.field)}."

            assert self.validator is None, \
                f"Argument `validator` of `DTOOneToOneField` HAS to be `None`" \
                f" when `relation_field` is `None`. Is {repr(self.validator)}."
            pass
        pass

    def __get__(self, instance: ty.Optional['DTOBase'], owner: ty.Any):
        if instance is None:
            return self
        return instance.__dict__[self.storage_name]

    def __set__(self, instance: ty.Optional['DTOBase']
                    , value: ty.Optional[ty.Any]) -> None:
        escape_validator: bool = False
        if 'escape_validator' in instance.__dict__ \
           and instance.__dict__['escape_validator'] is True:
            escape_validator = True
            pass

        try:
            if self.not_null is True and value is None:
                raise ValueError(f"{self.storage_name} deve ser preenchido.")

            if self.relation_type == OTORelationType.AGGREGATION:
                if self.is_self_related is False:
                    # NOTE: This is a path that only makes sense on GET or LIST
                    #           because in POST, PUT or PATCH the value will be
                    #           ignored.
                    instance.__dict__[self.storage_name] = value
                    return
                assert self.field is not None, 'UNREACHABLE: This is just for type checking.'

                if escape_validator is True:
                    if isinstance(value, dict):
                        value = self.expected_type(**value)
                        pass
                else:
                    if isinstance(value, self.expected_type):
                        value = getattr(value, self.expected_type.pk_field, None)
                    elif isinstance(value, dict):
                        value = value.get(self.expected_type.pk_field, None)
                        pass
                    pass

                if isinstance(value, self.expected_type):
                    pk = getattr(value, self.expected_type.pk_field)
                    if self.field.use_default_validator:
                        # NOTE: This may throw
                        pk = self.field.validate(self.field, pk, instance)
                        pass

                    if self.field.validator is not None:
                        # NOTE: This may throw
                        pk = self.field.validator(self.field, pk)
                        pass

                    setattr(value, self.expected_type.pk_field, pk)
                else:
                    if self.field.use_default_validator:
                        # NOTE: This may throw
                        value = self.field.validate(self.field, value, instance)
                        pass

                    if self.field.validator is not None:
                        # NOTE: This may throw
                        value = self.field.validator(self.field, value)
                        pass
                    pass
            else: # self.relation_type == RelationType.COMPOSITION
                if isinstance(value, dict):
                    value = self.expected_type(**value)  # NOTE: This may throw
                    pass

                if not isinstance(value, self.expected_type):
                    if self.is_self_related is False:
                        raise ValueError(
                            f"O Objeto não é do tipo informado. Valor recebido: {value}."
                        )

                    assert self.field is not None, 'UNREACHABLE: This is just for type checking.'

                    if self.field.use_default_validator:
                        value = self.field.validate(self, value, instance)  # NOTE: This may throw
                        pass

                    if self.field.validator is not None:
                        value = self.field.validator(self.field, value)  # NOTE: This may throw
                        pass
                    pass
                else:
                    if self.validator is not None:
                        value = self.validator(self, value)  # NOTE: This may throw
                        pass
                    pass
                pass
        except ValueError:
            if escape_validator is False:
                raise
            pass

        instance.__dict__[self.storage_name] = value
        pass
