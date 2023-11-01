from tests.cliente_dto import ClienteDTO
from tests.cliente_entity import ClienteEntity
from nsj_rest_lib.settings import application, APP_NAME, MOPE_CODE

from nsj_rest_lib.controller.get_route import GetRoute
from nsj_rest_lib.controller.list_route import ListRoute
from nsj_rest_lib.controller.post_route import PostRoute
from nsj_rest_lib.controller.put_route import PutRoute
from nsj_rest_lib.controller.delete_route import DeleteRoute

LIST_POST_ROUTE = f'/{APP_NAME}/{MOPE_CODE}/clientes'
GET_PUT_ROUTE = f'/{APP_NAME}/{MOPE_CODE}/clientes/<id>'


@application.route(LIST_POST_ROUTE, methods=['GET'])
@ListRoute(
    url=LIST_POST_ROUTE,
    http_method='GET',
    dto_class=ClienteDTO,
    entity_class=ClienteEntity
)
def get_clientes(request, response):
    return response


@application.route(GET_PUT_ROUTE, methods=['GET'])
@GetRoute(
    url=GET_PUT_ROUTE,
    http_method='GET',
    dto_class=ClienteDTO,
    entity_class=ClienteEntity
)
def get_cliente(request, response):
    return response


@application.route(LIST_POST_ROUTE, methods=['POST'])
@PostRoute(
    url=LIST_POST_ROUTE,
    http_method='POST',
    dto_class=ClienteDTO,
    entity_class=ClienteEntity
)
def post_cliente(request, response):
    return response


@application.route(GET_PUT_ROUTE, methods=['PUT'])
@PutRoute(
    url=GET_PUT_ROUTE,
    http_method='PUT',
    dto_class=ClienteDTO,
    entity_class=ClienteEntity
)
def put_cliente(request, response):
    return response

@application.route(GET_PUT_ROUTE, methods=['DELETE'])
@DeleteRoute(
    url=GET_PUT_ROUTE,
    http_method='DELETE',
    dto_class=ClienteDTO,
    entity_class=ClienteEntity
)
def delete_cliente(request, response):
    return response