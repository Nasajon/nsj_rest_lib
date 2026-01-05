import pytest
from nsj_rest_test_util.util.enum_http_method import HTTPMethod
from nsj_rest_test_util.util.tcase_util import TCaseUtil

test_util = TCaseUtil(
    __file__,
    "2531",
    "classificacoes-financeiras2",
    port=80,
)


@pytest.mark.parametrize(
    argnames="json_entrada_nome, json_entrada",
    argvalues=test_util.argvalues,
    scope="class",
)
class TestClassificacaoFinanceiraPOST:
    @pytest.fixture(scope="class", autouse=True)
    def setup(self, json_entrada_nome):
        test_util.pre_setup(json_entrada_nome, False)
        yield
        test_util.pos_setup(json_entrada_nome)

    def test_post(self, json_entrada, json_entrada_nome):
        test_util.common_request_test(json_entrada, json_entrada_nome, HTTPMethod.POST)
