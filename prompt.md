A primeira parte da implementação do uso de funções de banco para insert está, em fim, funcionando. Mas, me arrependi do modo como implementei a definição da função de insert, bem como do tipo, e dos campos do tipo.

Atualmente, estou usando o decorator Entity, e a classe EntityBase para tudo, tendo criado as propriedades "insert_type" e "insert_function" no decorator Entity, e tendo criado as propriedades "insert_type_field" e "insert_by_function", no property descriptor "EntityField". Mas, quero refatorar isso.

Minha ideia é agora separar as coisas... O DTO continua valendo para o formato de entrada e saída das APIs. A Entity cootinua valendo como espelho da tabela do banco de dados. Mas, quero criar agora uma nova parte, chamada de "InsertFunctionType", que também será composta por um decorator, com esse mesmo nome "InsertFunctionType", um property descriptor, chamado "InsertFunctionField", o qual deve conter a propriedade "type_field_name", em vez de "insert_type_field" (já a propriedade "insert_by_function" pode ser extinta, pois, se estiver na classe de um "InsertFunctionType", já se entende que tal propriedade será usada no type do BD), e uma superclasse "InsertFunctionTypeBase", a qual deve conter a lista de fields do type, e que deve ser a superclasse de qualquer classe que use o decorator "InsertFunctionType", servindo para apoiar a definição de funções de insert.

A ideia é seguir os padrões que já existem. Assim, no uso da biblioteca, o usuário terá que definir uma classe, que use o decorator "InsertFunctionType", sempre que quiser que um entidade seja inserida por meio de uma função de banco.

Quanto a lógica em tempo de execução, penso que será preciso criar um DAOBaseInsertByFunction, o qual conterá a lógica que hoje está do DAOBaseInsert, que serve para gravação por meio de funções de banco.

Além disso, para definir que a função de insert será usada, quero que o decorator "PostRoute" ganhe uma propriedade chamada "insert_function_type_class", a qual deve apontar para a classe que estender "InsertFunctionTypeBase", e assim, o ServiceBaseSave não deve mais olhar para a Entity para saber se o fluxo deve seguir pelo insert de função de banco, ou pelo insert normal. Antes, o ServiceBaseSave vai receber o a type da função de insert, e, caso tenha recebido, seguirá pelo fluxo de insert por meio do DAOBaseInsertByFunction.

A título de exemplo, considere o esboço de como podera ficar a classificacao financeira, só com os campos id, descricacao, e codigo:

@PostRoute(
    url=LIST_POST_ROUTE,
    http_method='POST',
    dto_class=ClassificacaoFinanceiraDTO,
    entity_class=ClassificacaoFinanceiraEntity,
    insert_function_type_class=ClassificacaoFinanceiraInsertType
)
def post_classificacao_financeira():
    pass

@DTO()
class ClassificacaoFinanceiraDTO:
    id: uuid.UUID = DTOField(entity_field="classificacaofinanceita", pk=true)
    codigo: str = DTOField()
    descricao: str = DTOField()

@Entity()
class ClassificacaoFinanceiraEntity:
    classificacaofinanceita: uuid.UUID = EntityField()
    codigo: str = EntityField()
    descricao: str = EntityField()

@InsertFunctionType()
class ClassificacaoFinanceiraInsertType:
    id: uuid.UUID = InsertFunctionField(type_field_name="classificacao_financeita")
    codigo: str = InsertFunctionField()
    descricao: str = InsertFunctionField()

Observações:
1. Respeite os padrões do projeto.
2. 2. Se não for passado um "type_field_name" para o "InsertFunctionField", o nome da própriedade será o default.
3. Tente manter o teste atual funcionando, refatorando a definição do controler, para que seja criado a classe ClassificacaoFinanceiraInsertType, a ser usada pelo PostRoute.



@PostRoute(
    url=LIST_POST_ROUTE,
    http_method='POST',
    dto_class=ClienteDTO,
    entity_class=ClienteEntity,
    insert_entity_class=ClienteInsertEntity
)
def post_cliente():
    pass



class ClienteDTO:
    nome: DTOField(entity_field="nome_completo", insert_function_field="nomecompleto")
    enderecos: DTOListField(dto_type=EnderecoDTO, entity_type=EnderecoEntity, insert_function_field="enderecos")


class ClienteEntity:
    nome_completo: str





class ClienteInsertEntity:
    nomecompleto: str
    enderecos: list[EnderecoInsertEntity] = InsertEntityField(...)


class EnderecoInsertEntity:
    logradouro: str





















Me ajude a fazer a seguinte implementação:

Preciso de um recurso que permita unir tabelas que tenham relacionamento 1X1, mas que não representem duas entidades relacionadas, e sim um modo de extender um entidade.

Por exemplo, imagine que eu tenha uma tabela de "produtos", que quero extender para representar produtos de um tipo específico, como fármacos. Então eu crio outra tabela chamada "farmaco", que se relaciona 1X1 com a tabela de produtos.

Mas, no objeto em si de retorno, a API deve deixar transparente o se tratar de duas tabelas. O usuário final não vai saber disso...

Em geral, a ideia é extender aquela outra tabela adicionando propriedades, no exemplo acima, uma fármaco por de ter número de registro da anvisa, flag indicando se é de venda controlada, etc. Propriedades essas que não estarão na tabela principal de produto.

Então, o retorno da API de produtos seria algo como:

GET /rota_base/produtos/{id}

```json
{
    "id": "uuid",
    "codigo": "str",
    "descricao": "str",
    ...
}
```

E, da API de fármacos seria algo como:

GET /rota_base/farmacos/{id}

```json
{
    "id": "uuid",
    "codigo": "str",
    "descricao": "str",
    "registro_anvisa": "str",
    "venda_controlada": bool,
    ...
}
```

Do ponto de vista de execução das queries, porém, a ideia é ser apenas uma, e não duas queries, usando um inner join normal.

Além disso, o join só deve acontecer de fato, caso a API chamada tenha que retornar uma das propriedades da tabela de extensão (o que pode acontecer se algumas dessas propriedades estiver marcada como "resume=true", ou se o usuário, ao chamar a API, passar o nome da propriedade no campo "fields").

No exemplo acima, caso os campos "registro_anvisa" e "venda_controlada" não estejam com "resume=true", e o usuário não os adicionar no fields, o retorno da API seria igual ao da API normal de produtos:

```json
{
    "id": "uuid",
    "codigo": "str",
    "descricao": "str",
    ...
}
```

E, além disso, não é para haver join (visto que não servirá para nada além de atrasar a query).

Por fim, do ponto de vista de como isso será declarado, minha intenção é incrementar o decorator "@DTO" e o decorator "@Entity". de modo que:

## No DTO:

```python
@DTO(
    partial_of={
        "dto": ProdutoDTO,
        "relation_field": "id_produto",
        "related_entity_field": "id", # (OPCIONAL)
    },
    ...
)
class FarmacoDTO(DTOBase):
    registro_anvisa: str = DTOField()
    venda_controlada: bool = DTOField()
```

Onde:
- dto: Indica a classe do DTO principal (extendido pelo DTO atual)
- relation_field: Inidica o campo, da tabela "farmaco", que será usado para no relacionamento 1X1 com a tabela "produto".
- related_entity_field: Propriedade opcional, que indica o campo, na tabela do produto, usado para o relacionamento (por padrão, o campo marcado como "pk=True" será utilizado).

## Na Entity:

```python
@Entity(
    partial_of=ProdutoEntity,
    ...
)
class FarmacoEntity(EntityBase):
    registro_anvisa: str = EntityField()
    venda_controlada: bool = EntityField()
```

Onde:
- partial_of: Indica a classe da Entity principal (extendida pela Entity atual).

## Nas rotas
Na delcaração das rotas (nos controllers), é os DTOs de extensão serão usados diretamenteo. Exemplo:

```python
@application.route(LIST_POST_ROUTE, methods=['GET'])
@ListRoute(
    url=LIST_POST_ROUTE,
    http_method='GET',
    dto_class=FarmacoDTO,
    entity_class=FarmacoEntity
)
def get_farmacos(request, response):
    return response
```

## Pontos de atenção:
- DTOs e Entities que usem "partial_of" não representam entidades sozinhos (precisam estar juntos com as classes "extendidas").
- A extensão compartilha com a entidade principal as propriedades marcadas como "partition_data" (o que interfere nas queries e chamadas às rotas, pois precisam ser passados obrigatoriamente nas chamadas).
- A construção das queries deve ser bem sensível ao uso ou não das propriedades da extensão (evitando joins desnecessários).





Por que usar a cláusula exists?
O _split_partial_fields não deveria tratar os campos reumo, quando vier None no field?
Preciso que implemente a ordenação por campos de extensão
Por que existe aquele tratamento dos nomes dos campos de relacionamento? Está aceitando tanto o nome do campo no DOT, quanto no Entity?