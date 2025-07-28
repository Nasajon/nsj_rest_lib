
class DTOAggregator:
    _ref_counter: int = 0

    name: str
    storage_name: str
    expected_type: type

    def __init__(self) -> None:
        self.storage_name = f"_{self.__class__.__name__}#{self.__class__._ref_counter}"
        self.__class__._ref_counter += 1
        pass
    pass
