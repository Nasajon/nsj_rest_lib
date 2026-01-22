from nsj_rest_lib.decorator.dto import DTO
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.dto.dto_base import DTOBase
from nsj_rest_lib.util.util_normaliza_parametros import get_params_normalizados


@DTO()
class DummyDTO(DTOBase):
    nome: str = DTOField(resume=True)
    segredo: str = DTOField()


def test_get_params_normalizados_dict_body():
    query_args = {"page": "1"}
    body = {"nome": "Ana", "segredo": "x", "extra": "y"}
    path_args = {"id": "123"}

    params = get_params_normalizados(query_args, body, DummyDTO, path_args=path_args)

    assert params["query_args"] == {"page": "1"}
    assert params["body"] == {"nome": "Ana"}
    assert params["path_args"] == {"id": "123"}


def test_get_params_normalizados_list_body():
    query_args = {"q": "ok"}
    body = [
        {"nome": "Ana", "segredo": "x"},
        {"nome": "Bia", "segredo": "y"},
    ]

    params = get_params_normalizados(query_args, body, DummyDTO, path_args=None)

    assert params["query_args"] == {"q": "ok"}
    assert params["body"] == [{"nome": "Ana"}, {"nome": "Bia"}]
    assert params["path_args"] == {}
