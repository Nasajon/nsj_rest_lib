# APIs Desktop

A partir da versão 2.9.0, o RestLib tem suporte ao empacotamento de APIs em arquivo executável (CLI: Command Line Interface), com o objetivo de viabilizar uma arquitetura de implementação onde um mesmo código fonte python passa ser usado tanto para distribuição como API Rest normal, como para uso vinha linha de comando (sem necessidade de nenhum tpo de refatoração).

## Ideia Básica
Em resumo, a biblioteca foi adaptada para que todas as rotas genéricas (ListRoute, GetRoute, PostRoute, PutRoute e PatchRoute) possam ser executadas por meio da passagem de parâmetros que representem as três formas de entrada de dados nas APIs HTTP. A saber:

* **url_pars:** Dados contidos no path da URL.
* **query_args:** Dados contidos após o caracter "?" da URL (passados como par x valor).
* **body:** Dados contidos no corpo da requisição (json).

A ideia básica então, é que na execução da API empacotada como CLI, é necessário passar um parâmetro do tipo JSON, o qual deve ser construído da seguinte maneira:

```json
{
    "url_pars": {...},
    "query_args": {...},
    "body": {...}
}
```

Assim, a aplicação CLI será capaz de dispensar o uso dos recursos do Flask, e passará os dados necessários à execução do código fonte, direto pelo dicionário passado na entrada.

## Parâmetros da linha de comando

Além do JSON com as entradas, o CLI também precisará receber um parâmetro com as informações necessárias à conexão com o BD, e, é claro, uma string de indentificação do comando em si a ser executado (isso é, da rota REST a ser chamada). Os parâmetros de entrada suportados, portanto, serão:

* **-t ou --host:** IP ou nome do servidor de banco de dados.
* **-p ou --port:** Porta do servidor de banco de dados.
* **-n ou --name:** Nome do banco de dados.
* **-u ou --user:** Usuário para conexão com banco de dados.
* **-s ou --password:** Senha para conexão com o banco de dados.
* **-c ou --command:** Identificador do comando a ser executado (exemplo 'list_empresa_erp3').
* **-j ou --json:** Json das entradas (conforme explicado antes).

### Parâmetro _command_

Tradicionalmente, para criação de uma rota com o RestLib, é necessário decorar um método python com um dos decorators de rotas genéricas: _ListRoute, GetRoute, PostRoute, PutRoute ou PatchRoute_.

Portanto, para simplificar a implementação, o próprio nome dos métodos sendo decorados será usado como parâmetro command. Por exemplo, na declaração da rota de recuperação de uma empresa, pelo ID, mostrado abaixo, o comando a ser passado seria `--command get_empresa_erp3`:

```python
@application.route(f"{ROUTE}/<id>", methods=["GET"])
@auth.requires_api_key_or_access_token()
@multi_database()
@GetRoute(
    url=f"{ROUTE}/<id>",
    http_method="GET",
    dto_class=EmpresaERP3DTO,
    entity_class=EmpresaERP3Entity,
    injector_factory=InjectorFactoryMultibanco,
)
def get_empresa_erp3(_, response):
    return response
```

### Parâmetro _json_

Embora já tenhamos exmplicado esse parâmetro na seção de "Ideia Básica", vale dar um exemplo compatível com o exemplo de recuperação de uma empresa, da seção imediatamente acima:

```json
{
    "url_pars": {"id": "13485926000166"},
    "query_args": {"fields":"enderecos", "grupo_empresarial":"NASAJON"},
    "body":{}
}
```

Nesse caso, estaríamos recuperando a empresa com ID "13485926000166", trazendo a propriedade "enderecos" (mesmo que esta não esteja no resumo da entidade), e filtrando os dados pelo grupo_empresarial "NASAJON".

## Passo a passo para usar o recurso (na implementação)

