# RestLib (nsj_rest_lib)

## QuickStart

Biblioteca para construção de APIs Rest Python, de acordo com o guidelines interno, e com paradigma declarativo.

Em resumo, com o RestLib, é possível construir APIs Rest completas para CRUD de entidades (GET, POST, PUT e DELETE), bastando escrever arquivos declarativos de DTO, Entity e das rotas em si, sem implementar a lógica de negócio ou acesso a banco de dados.

No entanto, diferentemente de frameworks web complexos, o RestLib é apenas uma biblioteca que pode ser usada em conjunto, ou até mesmo como coadjuvante, de uma implementação completamente manual, não "dominando" o ciclo de vida das requisições WEB (e sendo dependente do Flask enquanto framework HTTP).

### Para que mais uma biblioteca no estilo framework web?

Os padrões de desenvolvimento da Nasajon contam com particularidades que são melhor atendidas por bilbiotecas próprias, sejam elas:

* APIs Enxutas
  * Retorno exclusivo dos campos de resumo.
  * Suporte ao parâmetro fields.
  * Paginação obrigatória.
  * Recuperação de dados (do banco) somente sob demanda.
* APIs Multi Tenant
  * Particinamento de dados por tenant (e/ou grupo empresarial)
* APIs Multi Banco
  * A mesma API pode ser conectar a qualquer BD do ambiente web, de acordo com o tenant recebido.
* Suporte ao padrão de isolamento de dados do ERP Desktop (Conjuntos)
* Logs de auditoria e telemetria próprios
* Integração nativa com o motor de webhooks interno

Assim, para não exigir excesso de trabalho repetitivo na implementação das APIs internas, optou-se pelo desenvolvimento de uma biblioteca auxiliar própria.

A grande diferença, na filosofia de desenvolvimento, é que se prioriza um esforço para que a biblioteca possa ser usada como auxiliar de fluxos implementados na mão, assim como não impeça as customizações desejadas pelo programador (além de deixá-lo livre para misturar com outras soluções e bibliotecas).

### Passos básicos para desenvolver um CRUD completo usando o RestLib

1. Escrever a classe Entity, que reflita a entidade desejada (o formato deve ser plenamento correspondete À estrutura de banco desejada). [Exemplo](tests/cliente_dto.py).
2. Escrever a classe DTO, que reflita o formato desejado do JSON de entrada e saída (podem haver diferentes formatos em diferentes rotas). [Exemplo](tests/cliente_entity.py).
3. Escrever o módulo Controler, que será declarativo das rotas que se desejam expôr (o qual segue, em grande parte, o padrão do Flask). [Exemplo](tests/cliente_controller.py).

**Para facilitar ainda mais o trabalho, foi criado um [utilitário de linha de comando](https://github.com/Nasajon/arquitetura-cmd), que, por meio das APIs do ChatGPT, é capaz de escrever as classes de DTO e Entity, a partir do DDL da entidade desejada.**

## Índice de conteúdos (documentação geral)

* [Variáveis de ambiente](internal_docs/variaveis_ambiente.md)
* [Colaborando com o projeto](internal_docs/colaborando_projeto.md)
* Principais Recursos
  * [DTO](internal_docs/recursos/dto.md)
    * Fields (descritores de propriedades)
      * [DTOField](internal_docs/recursos/dto_field.md)
      * DTOListField (TODO)
      * [DTOSQLJoinField](internal_docs/recursos/dto_sql_join_field.md)
      * DTOLeftJoinField (TODO)
      * [Filters (filtros nos campos)](internal_docs/recursos/filters.md)
    * Filtros no DTO
      * fixed_filters (TODO)
      * [filter_aliases](internal_docs/recursos/filter_aliases.md)
    * Suporte a conjuntos (do ERP SQL) (TODO)
  * [Entity](internal_docs/recursos/entity.md) (TODO Atualizar)
  * [Controller](internal_docs/recursos/controller.md)
  * Menos usados
    * [DAO](internal_docs/recursos/dao.md)
* Outros Recursos
  * [Utilitário para Healthcheck](internal_docs/outros_recursos/healthcheck.md)
  * Integeração com o MultiDatabaseLib (TODO)
  * Validação de DTOs isolados (campos, tipos de dadose, etc) (TODO)
  * Uso manual do DAO (para queries manuais) (TODO)
  * Uso manual do Service (para consultas ou inserts manuais) (TODO)
  * Customizando comportamentos (TODO)
  * [Gravação de Telemetria (com o OpenTelemetry)](internal_docs/opentelemetry.md)

## Testes automatizados

Há dois conjuntos distintos de teste:

### Testes com BD e API
1. Precisa ser instalada por meio do arquivo requirements-dev.txt

```sh
pip install -r requirements-dev.txt
```

2. Consiste em testes mais completos, rodando de fato chamadas à APIs fake
3. Dependem de BD e API em execução (o comando abaixo também inicializa BD e API)

```sh
docker compose up test
```

4. Por fim, deburre o ambiente:
```sh
docker compose stop
docker compose rm
```

Observações:
* Estes testes estão totalmente paramentrizados para funcionar por dentro do docker (e não pela aplicação local).
* As configurações usadas nos testes consideram o arquivo `.env.dist`(e não o `.env`).
* A porta usada nos testes, depende do construtor da classe `TCaseUtil` (superclasse dos casos de teste).

### Testes somente código

1. Utiliza apenas o pytest
2. Equivalem ao que é popularmente chamado de testes unitários
3. Rodar sem dependências de processos em execução

```sh
make code_tests
```

Obsevações:
* Este tipo de teste faz mock de BD e etc.
  
## Histórico de versões

### 4.17.2

- Ajuste para que as colunas tenant sejam ignoradas caso uma variável de ambiente, chamada "ENV_MULTIDB", seja igual a "true".
  - A ideia é permitir que um mesmo DTO seja usado para ambiente nuvem e desktop (multibanco).

### 4.17.1

- Ajuste para o DTOOneToOneField suportar o parâmetro `entity_field`.

### 4.17.0

- Gravação de classes com extensões parciais (POST, PUT e PATCH).
- Novo descriptor de propriedades DTOOneToOneField, para substituir o antigo DTOObjectField (permitindo tanto agregação quanto composição, e evitando necessidade de duplicar a propriedade de FK nos DTOs).

### 4.16.0

- Implementação de extensões parciais (de modo que um DTO e um Entity) "herdem" tudo de outra entidade, mas permita definir propriedades adicionais, que serão buscadas em outra tabela, por meio de JOIN. Essa alteração ainda não suporta escrita na tabela de extensão.

### 4.15.0

- Suporte a alteração dos campos resumo padrão na definição de relacionamentos, seja por DTOObject ou DTOListField.

### 4.14.0

- Possibilidade de marcar um campo do tipo SQLJoinFiel como partition-field.
- Possibilidade de marcar um campo como parte de uma rota de verificação de integridade.
- Ajustes diversos

### 4.13.0

- Suporte a retorno no custom_after_insert ou custom_after_update
  - Se o retorno for um dict
    - Se houver um DTO de retorno, ele tentará adicionar propriedades ao mesmo DTO.
    - Se não , ele retorna apenas o dict
  - Se não
    - Se houver um DTO de retorno, então o retorno do custom_after é ignorado.
    - Se não, o retorno do custom_after é retornado como recebido.
- Suporte a notificações de enfileiramento a partir do custom_after_insert ou custom_after_update
  - Se o retorno de um desses métodos for um objeto do tipo nsj_rest_lib.dto.queued_data_dto.QueuedDataDTO, a requisição de POST, PUT ou PATCH irá retornar um HTTP 202, com um location (de acordo com a URL escrita no objeto), para notificar como acompanhar o resultado do enfileiramento.

### 4.12.0

- Suporte a campos, DTOField, marcados com flag ```no_update```, a qual faz com que um campo possa ser gravado, mas nunca atualizado.
- Ajustes na funcionalidade DTOAggregator

### 4.11.0

- Suporte a filtro do tipo is null:

```python
    email: str = DTOField(
        filters=[
            DTOFieldFilter("email_vazio", FilterOperator.NULL),
        ],
    )
```
