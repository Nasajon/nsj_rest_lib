import typing as ty

# pylint: disable-next=too-few-public-methods
class DTOAggregator:
    _ref_counter: int = 0

    name: str
    storage_name: str
    expected_type: ty.Any # It's a DTOBase but importing it would lead to a
                          #     circular dependency.

    def __init__(self) -> None:
        self.storage_name = f"_{self.__class__.__name__}#{self.__class__._ref_counter}"
        self.__class__._ref_counter += 1
        pass
    pass
