from tests.classificacao_financeira_dto import ClassificacaoFinanceiraDTO
from tests.classificacao_financeira_entity import ClassificacaoFinanceiraEntity
from tests.classificacao_financeira_function_types import (
    ClassificacaoFinanceiraInsertType,
    ClassificacaoFinanceiraUpdateType,
    ClassificacaoFinanceiraGetType,
    ClassificacaoFinanceiraListType,
    ClassificacaoFinanceiraDeleteType,
)
from nsj_rest_lib.settings import application, APP_NAME, MOPE_CODE

from nsj_rest_lib.controller.list_route import ListRoute
from nsj_rest_lib.controller.post_route import PostRoute
from nsj_rest_lib.controller.put_route import PutRoute
from nsj_rest_lib.controller.get_route import GetRoute
from nsj_rest_lib.controller.delete_route import DeleteRoute

LIST_POST_ROUTE = f"/{APP_NAME}/{MOPE_CODE}/classificacoes-financeiras"
GET_PUT_ROUTE = f"/{APP_NAME}/{MOPE_CODE}/classificacoes-financeiras/<id>"


@application.route(LIST_POST_ROUTE, methods=["GET"])
@ListRoute(
    url=LIST_POST_ROUTE,
    http_method="GET",
    dto_class=ClassificacaoFinanceiraDTO,
    entity_class=ClassificacaoFinanceiraEntity,
    list_function_type_class=ClassificacaoFinanceiraListType,
    list_function_name="teste.api_classificacaofinanceiralist",
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
    insert_function_name="teste.api_classificacaofinanceiranovo",
)
def post_classificacoes_financeiras(request, response):
    return response


@application.route(GET_PUT_ROUTE, methods=["PUT"])
@PutRoute(
    url=GET_PUT_ROUTE,
    http_method="PUT",
    dto_class=ClassificacaoFinanceiraDTO,
    entity_class=ClassificacaoFinanceiraEntity,
    update_function_type_class=ClassificacaoFinanceiraUpdateType,
    update_function_name="teste.api_classificacaofinanceiraalterar",
)
def put_classificacoes_financeiras(request, response):
    return response


@application.route(GET_PUT_ROUTE, methods=["GET"])
@GetRoute(
    url=GET_PUT_ROUTE,
    http_method="GET",
    dto_class=ClassificacaoFinanceiraDTO,
    entity_class=ClassificacaoFinanceiraEntity,
    get_function_type_class=ClassificacaoFinanceiraGetType,
    get_function_name="teste.api_classificacaofinanceiraget",
)
def get_classificacao_financeira(request, response):
    return response


@application.route(GET_PUT_ROUTE, methods=["DELETE"])
@DeleteRoute(
    url=GET_PUT_ROUTE,
    http_method="DELETE",
    dto_class=ClassificacaoFinanceiraDTO,
    entity_class=ClassificacaoFinanceiraEntity,
    delete_function_type_class=ClassificacaoFinanceiraDeleteType,
    delete_function_name="teste.api_classificacaofinanceiraexcluir",
)
def delete_classificacao_financeira(request, response):
    return response
