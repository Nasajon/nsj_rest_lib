# RestLib (nsj_rest_lib)

Ver [Histórico de Versões](historico_versoes.md) da biblioteca.

# QuickStart

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
