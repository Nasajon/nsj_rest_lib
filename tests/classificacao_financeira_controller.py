from tests.classificacao_financeira_dto import ClassificacaoFinanceiraDTO
from tests.classificacao_financeira_entity import ClassificacaoFinanceiraEntity
from tests.classificacao_financeira_insert_function_type import (
    ClassificacaoFinanceiraInsertType,
)
from nsj_rest_lib.settings import application, APP_NAME, MOPE_CODE

from nsj_rest_lib.controller.list_route import ListRoute
from nsj_rest_lib.controller.post_route import PostRoute

LIST_POST_ROUTE = f"/{APP_NAME}/{MOPE_CODE}/classificacoes-financeiras"
GET_PUT_ROUTE = f"/{APP_NAME}/{MOPE_CODE}/classificacoes-financeiras/<id>"


@application.route(LIST_POST_ROUTE, methods=["GET"])
@ListRoute(
    url=LIST_POST_ROUTE,
    http_method="GET",
    dto_class=ClassificacaoFinanceiraDTO,
    entity_class=ClassificacaoFinanceiraEntity,
)
def get_classificacoes_financeiras(request, response):
    return response


@application.route(LIST_POST_ROUTE, methods=["POST"])
@PostRoute(
    url=LIST_POST_ROUTE,
    http_method="POST",
    dto_class=ClassificacaoFinanceiraDTO,
    entity_class=ClassificacaoFinanceiraEntity,
    insert_function_type_class=ClassificacaoFinanceiraInsertType,
)
def post_classificacoes_financeiras(request, response):
    return response
