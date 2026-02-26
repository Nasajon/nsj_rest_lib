# ETag em GET unitario

Este recurso adiciona suporte a ETag nas rotas de GET por ID.

Arquivos relacionados:
- [get_route](src/nsj_rest_lib/controller/get_route.py)
- [route_base](src/nsj_rest_lib/controller/route_base.py)
- [dto_field](src/nsj_rest_lib/descriptor/dto_field.py)
- [dto](src/nsj_rest_lib/dto/dto_base.py)

## Como habilitar
- Marque um unico campo do DTO com `DTOField(etag_field=True)`.
- O decorator `DTO` registra o nome do campo em `etag_field_name`.
- Caso mais de um campo seja marcado, e lancado `ValueError`.

Exemplo:
```python
from nsj_rest_lib.decorator.dto import DTO
from nsj_rest_lib.descriptor.dto_field import DTOField
from nsj_rest_lib.dto.dto_base import DTOBase

@DTO()
class ClienteDTO(DTOBase):
    id: int = DTOField(pk=True)
    version: str = DTOField(etag_field=True)
```

## Resposta com ETag
- Quando o campo configurado possui valor, o GET por ID inclui o header `ETag`.
- O header e sempre retornado como weak etag, com prefixo `W/`.
- O valor e sempre retornado entre aspas e com escape de `"`.

## If-None-Match
- Se o header `If-None-Match` contem o valor atual, a rota retorna `304` com corpo vazio e header `ETag`.
- Se nao houver match, retorna `200` com o payload completo e `ETag` atualizado.
- O header aceita multiplos valores entre aspas, separados por virgula, e suporta valores com `W/` (weak etag).

## Observacoes de execucao
- Para comparar o ETag, o `RouteBase.handle_if_none_match` faz uma leitura rasa com `fields={'root': {etag_field_name, pk_field}}` e sem expands.
- O campo de ETag e sempre incluido no conjunto de fields, mesmo quando nao e solicitado na query.
- O header `ETag` e adicionado via `RouteBase.add_etag_header_if_needed` quando o DTO define `etag_field_name`.
