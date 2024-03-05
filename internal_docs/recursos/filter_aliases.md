# filter_aliases

Essa propriedade do decorator "DTO" permite criar um mapeamento entre nomes de filtros, de acordo com o tipo do dado recebido na URL de GET (GET List, e não GET por ID).

Na prática, o filtro declarado como alias, é trocado pelo seu correspondente, de acordo com o tipo do dado recebido na URL (como conteúdo do filtro).

Para entender melhor, considere um exemplo onde se deseja suportar que o filtro "grupo_empresarial" (passado na URL) receba um UUID ou uma string (código do Grupo Empresarial). No entanto, a propriedade com o código do grupo pode se chamar "grupo_empresarial", e a propriedade com o UUID "grupo_empresarial_id". E, é o "filter_aliases" que permitirá fazer essa seleção de filtro a ser aplicado, de acordo com o tipo do dado recebido.

No exemplo acima, a URL da chamada seria algo como:

```http
GET /endpoint?grupo_empresarial=XXXX
```

## Sintaxe básica:

Segue a sintaxe do mesmo exemplo dado na introdução:

```py
@DTO(
    filter_aliases={
        "grupo_empresarial": {
            uuid.UUID: "grupo_empresarial_id",
            str: "grupo_empresarial",
        },
    },
)
```

No exemplo acima, se o filtro recebido na URL for do tipo UUID, a propriedade "grupo_empresarial_id" será a usada. E, se for do tipo str, a propriedade "grupo_empresarial" será a usada.

_Obs. 1: A correspondenência é feita entre filtros, e, portanto, pode-se apontar para filtros definidos manualmente (como os filtros que usam operadores que não a igualdade). Não é necessário sempre apontar para filtros que correspondem diretamente a uma propriedade._

_Obs. 2: Note que o nome do filtro recebido na URL pode ter o mesmo nome de um dos filtros a serem direcionados._
