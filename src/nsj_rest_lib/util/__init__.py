import typing

# NOTE: If you're going to add a new resumable verb don't forget to add it
#           to the DTOBase.
ResumableVerbsTy = typing.Union[
    typing.Literal['LIST'],
    typing.Literal['GET'],
    typing.Literal['POST'],
    typing.Literal['PATCH'],
    typing.Literal['PUT'],
]
AllResumableVerbs: typing.List[ResumableVerbsTy] = [
    'LIST',
    'GET',
    'POST',
    'PATCH',
    'PUT',
]
