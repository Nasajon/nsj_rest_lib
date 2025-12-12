import abc
import typing as ty

from nsj_rest_lib.descriptor.function_field import FunctionField

if ty.TYPE_CHECKING:
    from nsj_rest_lib.dto.dto_base import DTOBase
    from nsj_rest_lib.descriptor.dto_field import DTOField
    from nsj_rest_lib.descriptor.dto_list_field import DTOListField
    from nsj_rest_lib.descriptor.dto_object_field import DTOObjectField
    from nsj_rest_lib.descriptor.dto_one_to_one_field import DTOOneToOneField


class FunctionTypeBase(abc.ABC):
    """
    Classe base para todos os tipos usados em funções PL/PGSQL (insert/update),
    mantendo o contrato esperado pelo DAO para identificar campos e referências.
    """

    fields_map: ty.Dict[str, FunctionField] = {}
    type_name: str = ""
    function_name: str = ""
    pk_field_name: ty.Optional[str] = None
    dto_lookup_attribute: str = "function_field_lookup"
    _dto_function_mapping_cache: ty.Dict[
        ty.Type["DTOBase"], ty.Dict[str, ty.Tuple[str, ty.Any]]
    ] = {}

    @classmethod
    def get_fields_map(cls) -> ty.Dict[str, FunctionField]:
        if not hasattr(cls, "fields_map"):
            raise NotImplementedError(
                f"fields_map não definido em {cls.__name__}"
            )
        return cls.fields_map

    def get_type_name(self) -> str:
        if not hasattr(self.__class__, "type_name"):
            raise NotImplementedError(
                f"type_name não definido em {self.__class__.__name__}"
            )
        return self.__class__.type_name

    def get_function_name(self) -> str:
        if not hasattr(self.__class__, "function_name"):
            raise NotImplementedError(
                f"function_name não definido em {self.__class__.__name__}"
            )
        return self.__class__.function_name

    @classmethod
    def get_pk_field_name(cls) -> ty.Optional[str]:
        """
        Retorna o nome do campo marcado como pk no FunctionType, se houver.
        """
        return getattr(cls, "pk_field_name", None)

    @classmethod
    def build_from_params(
        cls,
        params: dict[str, ty.Any],
        id_value: ty.Any = None,
    ) -> "FunctionTypeBase":
        """
        Constrói uma instância preenchida a partir de um dicionário de parâmetros,
        opcionalmente preenchendo o campo pk com id_value.
        """
        instance = cls()
        fields_map = cls.get_fields_map()

        pk_field = cls.get_pk_field_name()
        if id_value is not None:
            if pk_field is None:
                raise ValueError(
                    f"FunctionType '{cls.__name__}' não possui campo pk configurado."
                )
            setattr(instance, pk_field, id_value)

        for key, value in params.items():
            if key in fields_map:
                setattr(instance, key, value)
                continue
            for field_name, descriptor in fields_map.items():
                if descriptor.get_type_field_name() == key:
                    setattr(instance, field_name, value)
                    break

        return instance

    @classmethod
    def get_function_mapping(
        cls,
        dto_class: ty.Type["DTOBase"],
    ) -> ty.Dict[str, ty.Tuple[str, ty.Any]]:
        cache = getattr(cls, "_dto_function_mapping_cache", None)
        if cache is None:
            cache = {}
            setattr(cls, "_dto_function_mapping_cache", cache)

        if dto_class not in cache:
            cache[dto_class] = cls._build_function_mapping(dto_class)

        return cache[dto_class]

    @classmethod
    def _build_function_mapping(
        cls,
        dto_class: ty.Type["DTOBase"],
    ) -> ty.Dict[str, ty.Tuple[str, ty.Any]]:
        lookup = getattr(dto_class, cls.dto_lookup_attribute, None)
        if not lookup:
            raise ValueError(
                f"DTO '{dto_class.__name__}' não possui '{cls.dto_lookup_attribute}' configurado."
            )

        fields_map = getattr(cls, "fields_map", {})
        mapping: ty.Dict[str, ty.Tuple[str, ty.Any]] = {}

        for field_name in fields_map.keys():
            if field_name not in lookup:
                raise ValueError(
                    f"O campo '{field_name}' do FunctionType '{cls.__name__}' não existe no DTO '{dto_class.__name__}'."
                )
            mapping[field_name] = lookup[field_name]

        return mapping


class InsertFunctionTypeBase(FunctionTypeBase):
    dto_lookup_attribute = "insert_function_field_lookup"

    @classmethod
    def get_insert_function_mapping(
        cls,
        dto_class: ty.Type["DTOBase"],
    ) -> ty.Dict[str, ty.Tuple[str, ty.Any]]:
        return cls.get_function_mapping(dto_class)


class UpdateFunctionTypeBase(FunctionTypeBase):
    dto_lookup_attribute = "update_function_field_lookup"

    @classmethod
    def get_update_function_mapping(
        cls,
        dto_class: ty.Type["DTOBase"],
    ) -> ty.Dict[str, ty.Tuple[str, ty.Any]]:
        return cls.get_function_mapping(dto_class)


class GetFunctionTypeBase(FunctionTypeBase):
    dto_lookup_attribute = "get_function_field_lookup"

    @classmethod
    def get_get_function_mapping(
        cls,
        dto_class: ty.Type["DTOBase"],
    ) -> ty.Dict[str, ty.Tuple[str, ty.Any]]:
        return cls.get_function_mapping(dto_class)


class ListFunctionTypeBase(FunctionTypeBase):
    dto_lookup_attribute = "list_function_field_lookup"

    @classmethod
    def get_list_function_mapping(
        cls,
        dto_class: ty.Type["DTOBase"],
    ) -> ty.Dict[str, ty.Tuple[str, ty.Any]]:
        return cls.get_function_mapping(dto_class)


class DeleteFunctionTypeBase(FunctionTypeBase):
    dto_lookup_attribute = "delete_function_field_lookup"

    @classmethod
    def get_delete_function_mapping(
        cls,
        dto_class: ty.Type["DTOBase"],
    ) -> ty.Dict[str, ty.Tuple[str, ty.Any]]:
        return cls.get_function_mapping(dto_class)
