# Perguntas Frequentes

## Como declarar um DTO (uma entidade ou recurso) que permita usar tanto a PK como outro campo como chave?

Um exemplo desse caso seria um DTO de cliente, para o qual tanto a PK (UUID), como o CPF/CNPJ ou até o código poderiam ser usados como chave (funcionando numa chamada GET por ID, ou funcionando numa chamada do tipo GET List, que permita filtrar por esse campo).

Para alcançar esse comportamento, utilize os seguintes passos:

1. Declare, no DTO os campos de chave, marcando a PK, mas também marcando as demais chaves como chaves candidatas.
2. Declare também um alias de filtro, que permita variar o campo sendo filtrado, de acordo com o tipo do passado no filtro.

Exemplo de código:

```python
@DTO(
    filter_aliases={
        "id": {
            uuid.UUID: "pk",
            str: "id",
        },
    },
)
class ClienteERP3DTO(DTOBase):
    # Atributos gerais
    pk: uuid.UUID = DTOField(
        pk=True,
        entity_field="id",
        ...
    )
    id: str = DTOField(
        candidate_key=True,
        ...
    )
```

## Como declarar uniques no DTO?

Você pode declarar quantas uniques quiser para seus recursos rest (entidades), utilizando a propriedade `unique` do descritor de propriedade `DTOField`, bastando adicionar.

É importante notar que a propriedade `unique` é do tipo `str` e não `bool`, de modo que todos os campos anotados com um mesmo nome participam de um determinada unique, enquanto os campos anotados com outro nome, irão compor outra unique. Exemplo:

```python
@DTO()
class ClienteERP3DTO(DTOBase):
    # Atributos gerais
    id: str = DTOField(
        unique="doc_unique",
        ...
    )
```