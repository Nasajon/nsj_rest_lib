import abc
import typing as ty

from nsj_rest_lib.descriptor.insert_function_field import InsertFunctionField

if ty.TYPE_CHECKING:
    from nsj_rest_lib.dto.dto_base import DTOBase
    from nsj_rest_lib.descriptor.dto_field import DTOField
    from nsj_rest_lib.descriptor.dto_list_field import DTOListField
    from nsj_rest_lib.descriptor.dto_object_field import DTOObjectField
    from nsj_rest_lib.descriptor.dto_one_to_one_field import DTOOneToOneField



class InsertFunctionTypeBase(abc.ABC):
    """
    Classe base para todos os tipos usados em funções de insert via PL/PGSQL.
    Mantém o contrato esperado pelo DAO para identificar campos e nomes do type/
    função.
    """

    fields_map: ty.Dict[str, InsertFunctionField] = {}
    type_name: str = ""
    function_name: str = ""
    _dto_insert_function_mapping_cache: ty.Dict[
        ty.Type["DTOBase"], ty.Dict[str, ty.Tuple[str, ty.Any]]
    ] = {}

    def get_fields_map(self) -> ty.Dict[str, InsertFunctionField]:
        if not hasattr(self.__class__, "fields_map"):
            raise NotImplementedError(
                f"fields_map não definido em {self.__class__.__name__}"
            )
        return self.__class__.fields_map

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
    def get_insert_function_mapping(
        cls,
        dto_class: ty.Type["DTOBase"],
    ) -> ty.Dict[str, ty.Tuple[str, ty.Any]]:
        cache = getattr(cls, "_dto_insert_function_mapping_cache", None)
        if cache is None:
            cache = {}
            setattr(cls, "_dto_insert_function_mapping_cache", cache)

        if dto_class not in cache:
            cache[dto_class] = cls._build_insert_function_mapping(dto_class)

        return cache[dto_class]

    @classmethod
    def _build_insert_function_mapping(
        cls,
        dto_class: ty.Type["DTOBase"],
    ) -> ty.Dict[str, ty.Tuple[str, ty.Any]]:
        lookup = getattr(dto_class, "insert_function_field_lookup", None)
        if not lookup:
            raise ValueError(
                f"DTO '{dto_class.__name__}' não possui insert_function_field_lookup configurado."
            )

        fields_map = getattr(cls, "fields_map", {})
        mapping: ty.Dict[str, ty.Tuple[str, ty.Any]] = {}

        for field_name in fields_map.keys():
            if field_name not in lookup:
                raise ValueError(
                    f"O campo '{field_name}' do InsertFunctionType '{cls.__name__}' não existe no DTO '{dto_class.__name__}'."
                )
            mapping[field_name] = lookup[field_name]

        return mapping
