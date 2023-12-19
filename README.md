# RestLib (nsj_rest_lib)
Biblioteca para construção de APIs Rest Python, de acordo com o guidelines interno, e com paradigma declarativo.

## Variáveis de ambiente

#### Variáveis gerais

| Variável                 | Obrigatória        | Descrição                                                  |
| ------------------------ | ------------------ | ---------------------------------------------------------- |
| APP_NAME                 | Sim                | Nome da aplicação.                                         |
| DEFAULT_PAGE_SIZE        | Não (padrão: 20)   | Quantidade máxima de items retonardos numa página de dados |
| USE_SQL_RETURNING_CLAUSE | Não (padrão: true) | Montagem das cláusulas returning                           |

#### Variáveis de banco

| Variável        | Obrigatória            | Descrição                                  |
| --------------- | ---------------------- | ------------------------------------------ |
| DATABASE_HOST   | Sim                    | IP ou nome do host, para conexão com o BD. |
| DATABASE_PASS   | Sim                    | Senha para conexão com o BD.               |
| DATABASE_PORT   | Sim                    | Porta para conexão com o BD.               |
| DATABASE_NAME   | Sim                    | Nome do BD.                                |
| DATABASE_USER   | Sim                    | Usuário para conexão com o BD.             |
| DATABASE_DRIVER | Não (padrão: POSTGRES) | Driver para conexão com o BD.              |

#### Variáveis do RabbitMQ

| Variável           | Obrigatória           | Descrição           |
| ------------------ | --------------------- | ------------------- |
| RABBITMQ_HOST      | Não                   | IP ou nome do host. |
| RABBITMQ_HTTP_PORT | Não (padrão: 15672)   | Porta para conexão. |
| RABBITMQ_USER      | Não   (padrão: guest) | Senha para conexão. |
| RABBITMQ_PASS      | Não (padrão: guest)   | Senha para conexão. |

## Como instalar


## Montando ambiente de desenvolvimento
Para rodar a biblioteca localmente, após a configuração da sua aplicação principal, siga os passos:
1. Clone a biblioteca:
`git clone git@github.com:Nasajon/nsj_rest_lib.git`
2. Desinstale a biblioteca no seu ambiente virtual da aplicação:
`pip uninstall nsj-rest-lib`
3. Na variável de ambiente PYTHONPATH localizado no .env da aplicação principal, coloque o caminho da biblioteca após o caminho da aplicação, entre :
`PYTHONPATH=/home/@work/dados-mestre-api:/home/@work/nsj_rest_lib/src`

## [HealthCheck](src/nsj_rest_lib/healthcheck_config.py)
A classe `HealthCheckConfig` oferece uma configuração para verificação da saúde em uma aplicação Flask. Verificando o status do banco de dados e do servidor RabbitMQ. Parâmetro obrigatório na inicialização é o _flask_application_, outros parâmetros como: _injector_factory_class_, _app_name_, _rabbitmq_host_, _rabbitmq_http_port_, _rabbitmq_user_, _rabbitmq_pass_, serão recuperados das variáveis de ambiente e/ou nulos. Na `config` por padrão os parâmetros _check_database_ e _check_rabbit_mq_ virão True e False, podendo ser ajustados na chamada.

**Exemplo:**
```
#importando a classe
from nsj_rest_lib.healthcheck_config import HealthCheckConfig

HealthCheckConfig(
    flask_application=application
).config(check_database=True, check_rabbit_mq=False)
```

### [EntityBase](src/nsj_rest_lib/entity/entity_base.py)
`EntityBase` é uma classe abstrata genérica para representar entidades no banco de dados. Ele fornece um modelo flexível para criar classes de entidade específicas. As subclasses devem herdar desta classe e implementar os métodos para configurar os detalhes da tabela no banco de dados.

<!-- #### Atributos:

- `fields_map (dict)`: Um dicionário que mapeia os nomes dos campos da entidade.
- `table_name (str)`: O nome correspondente da tabela no banco de dados.
- `default_order_fields (List[str])`: Uma lista de campos para ordenação em consultas.
- `pk_field (str)`: O nome do campo que representa a chave primária da entidade. -->

#### Métodos

- `get_table_name(self) -> str`: Método que deve ser implementado pela subclasse para retornar o nome da tabela associada à entidade no banco de dados.

- `get_default_order_fields(self) -> List[str]`: Método que deve ser implementado pela subclasse para retornar uma lista de campos para ordenação padrão quando não for especificada uma ordenação personalizada.

- `get_pk_field(self) -> str`: Método que deve ser implementado pela subclasse para retornar o nome do campo chave primária na tabela do banco de dados.

- `get_fields_map(self) -> dict`: Método que deve ser implementado pela subclasse para retornar um dicionário mapeando nomes de atributos para nomes de campos no banco de dados. 

- `get_insert_returning_fields(self) -> List[str]`: Método que pode ser implementado pela subclasse para retornar uma lista de campos que devem ser retornados após uma operação de inserção no banco de dados.

- `get_update_returning_fields(self) -> List[str]`: Método que pode ser implementado pela subclasse para retornar uma lista de campos que devem ser retornados após uma operação de atualização no banco de dados.


**Exemplo:**
```
from nsj_rest_lib.entity.entity_base import EntityBase

class ClienteEntity(EntityBase):
    id: str
    estabelecimento: str
    cliente: str

    def __init__(self) -> None:
        self.id: str = None
        self.estabelecimento: str = None
        self.cliente: str = None

    def get_table_name(self) -> str:
        return 'cliente'

    def get_pk_field(self) -> str:
        return 'id'

    def get_default_order_fields(self) -> List[str]:
        return ['estabelecimento', 'cliente', 'id']

    def get_fields_map(self) -> dict: #rever
        return {
            "estabelecimento": "estabelecimento",
            "cliente": "cliente"
        }
```
### [Filter](src/nsj_rest_lib/entity/filter.py)
A classe `Filter` é uma representação de um filtro que pode ser aplicado a uma consulta em um banco de dados ou a uma coleção de dados. Um filtro é composto por um FilterOperator e um valor que será usado para realizar a comparação.

#### Enumeração FilterOperator
```
EQUALS = "equals"
DIFFERENT = "diferent"
GREATER_THAN = "greater_than"
LESS_THAN = "less_than"
GREATER_OR_EQUAL_THAN = "greater_or_equal_than"
LESS_OR_EQUAL_THAN = "less_or_equal_than"
LIKE = "like"
ILIKE = "ilike"
NOT_NULL = "not_null"
```

**Exemplo:**
```
from nsj_rest_lib.entity.filter import Filter, FilterOperator

Filter(FilterOperator.EQUALS, 'value')
```

### [DAO](src/nsj_rest_lib/dao/dao_base.py)
`DAOBase` é uma classe genérica que serve como um Data Access Object (DAO) para simplificar o processo de interação com o banco de dados.
#### Métodos:
- `__init__`(self, db: DBAdapter2, entity_class: EntityBase) -> None: Construtor da classe DAOBase. Inicializa um objeto DAOBase com uma instância de DBAdapter2 e uma classe de entidade (EntityBase) associada.

- `begin(self)` -> None: Inicia uma nova transação no banco de dados.

- `commit(self)` -> None: Realiza commit na transação corrente no banco de dados, se houver uma transação em andamento. Não gera erro se não houver uma transação.

- `rollback(self)` -> None: Realiza rollback na transação corrente no banco de dados, se houver uma transação em andamento. Não gera erro se não houver uma transação.

- `in_transaction(self)` -> bool: Verifica se há uma transação em andamento no DBAdapter. Retorna True se houver uma transação, caso contrário, retorna False.

- `get(self, key_field: str, id: uuid.UUID, fields: List[str] = None, filters: Dict[str, List[Filter]] = None, conjunto_type: ConjuntoType = None, conjunto_field: str = None)` -> EntityBase: Retorna uma instância de entidade com base no seu ID. Aceita parâmetros opcionais para especificar campos específicos, filtros adicionais ou junções de conjuntos.

- `list(self, after: uuid.UUID, limit: int, fields: List[str], order_fields: List[str], filters: Dict[str, List[Filter]], conjunto_type: ConjuntoType = None, conjunto_field: str = None)` -> List[EntityBase]: Retorna uma lista paginada de entidades. Aceita parâmetros para especificar a partir de qual registro (after) começar a paginar, o número máximo de registros (limit), campos a serem incluídos, campos pelos quais ordenar (order_fields), filtros adicionais e junções de conjuntos.

- `insert_relacionamento_conjunto(self, id: str, conjunto_field_value: str, conjunto_type: ConjuntoType = None)` -> None: Insere um relacionamento com um conjunto para uma entidade específica com base no seu ID e no valor do campo de conjunto. Permite especificar o tipo de conjunto, caso necessário.

- `delete_relacionamento_conjunto(self, id: str, conjunto_type: ConjuntoType = None)` -> None: Remove um relacionamento com um conjunto para uma entidade específica com base no seu ID. Permite especificar o tipo de conjunto, caso necessário.

- `insert(self, entity: EntityBase)` -> EntityBase: Insere um objeto de entidade no banco de dados. Retorna a entidade inserida com os dados atualizados, incluindo a chave primária, se for gerada automaticamente pelo banco de dados.

- `update(self, key_field: str, key_value: Any, entity: EntityBase, filters: Dict[str, List[Filter]], partial_update: bool = False)` -> EntityBase: Atualiza um objeto de entidade no banco de dados com base no campo de chave, valor de chave, filtros e entidade fornecidos. Permite a opção partial_update para atualização parcial de campos. Retorna a entidade atualizada com os dados mais recentes do banco de dados.

- `list_ids(self, filters: Dict[str, List[Filter]])` -> Optional[List[Any]]: Lista os IDs das entidades que correspondem aos filtros fornecidos. Retorna uma lista de IDs ou None se não houver correspondência.

- `delete(self, filters: Dict[str, List[Filter]])` -> None: Exclui registros do banco de dados com base nos filtros fornecidos. Gera uma exceção NotFoundException se nenhum registro for encontrado para exclusão.

- `is_valid_uuid(self, value)` -> bool: Verifica se um valor é um UUID válido.

### [DTO](src/nsj_rest_lib/dto/dto_base.py)
`DTOBase` é uma classe abstrata que representa um Data Transfer Object (DTO) usado para transferir dados entre a camada de apresentação e a camada de serviço de uma aplicação. É especialmente útil em operações onde uma entidade de banco de dados precisa ser convertida em um formato adequado para interações com a interface do usuário.

#### Atributos:
- `resume_fields: Set[str]` - Conjunto de campos que devem ser incluídos na visualização resumida do DTO.
- `partition_fields: Set[str]` - Conjunto de campos utilizados para particionamento de dados.
- `fields_map: Dict[str, DTOField]` - Dicionário mapeando nomes de atributos do DTO para configurações de campos correspondentes.
- `list_fields_map: dict` - Dicionário mapeando nomes de atributos do DTO para configurações de campos de lista.
- `field_filters_map: Dict[str, DTOFieldFilter]` - Dicionário mapeando nomes de atributos do DTO para configurações de filtros de campo.
- `pk_field: str` - Nome do campo chave primária na entidade associada ao DTO.
- `fixed_filters: Dict[str, Any]` - Dicionário contendo filtros fixos que devem ser aplicados ao recuperar dados da base de dados.
- `conjunto_type: ConjuntoType` - Tipo de conjunto utilizado para junções de dados relacionados.
- `conjunto_field: str` - Nome do campo utilizado para junções de dados relacionados.
- `escape_validator: bool` - Indica se a validação de dados deve ser ignorada.
- `uniques: Dict[str, Set[str]]` - Dicionário mapeando nomes de campos únicos para um conjunto de valores únicos.
- `candidate_keys: List[str]` - Lista de nomes de campos que juntos formam uma chave candidata única.

#### Métodos:
- `__init__(self, entity: Union[EntityBase, dict] = None, escape_validator: bool = False, generate_default_pk_value: bool = True, **kwargs)` -> None: Construtor da classe DTOBase que inicializa um objeto DTOBase com base em uma entidade ou um dicionário de dados, permitindo determinar se a validação deve ser ignorada e se o valor da PK deve ser gerado se não for fornecido.
- `convert_to_entity(self, entity_class: EntityBase, none_as_empty: bool = False)` -> EntityBase - Converte o DTO para uma instância da entidade associada.
- `convert_to_dict(self, fields: Dict[str, List[str]] = None, just_resume: bool = False)` -> Dict - Converte o DTO para um dicionário, permitindo especificar campos para inclusão e se deve ser uma visualização resumida.

#### DTOField
A classe `DTOField` representa uma propriedade de um objeto DTO e define várias configurações para essa propriedade, como tipo esperado, validações, formatações, entre outras. As validações personalizadas são acessadas em [DTOFieldValidators](src/nsj_rest_lib/descriptor/dto_field_validators.py). A classe `DTOFieldFilter` representa um filtro que pode ser aplicado a uma propriedade DTO para consultas.

##### Parâmetros:
- `type [object = None]`: Tipo esperado para a propriedade. Se for do tipo enum.Enum, o valor recebido será convertido para o enumerado.
- `not_null [bool = False]`: Indica se o campo não pode ser None ou vazio (no caso de strings).
- `resume [bool = False]`: Indica se o campo será usado como resumo, sempre retornado em consultas GET que listam os dados.
- `min [int = None]`: Menor valor permitido (ou menor comprimento, para strings).
- `max [int = None]`: Maior valor permitido (ou maior comprimento, para strings).
- `validator [typing.Callable = None]`: Função que valida o valor da propriedade antes de atribuí-lo.
- `strip [bool = False]`: Indica se espaços no início e no fim de strings devem ser removidos.
- `entity_field [str = None]`: Nome da propriedade equivalente na classe de entidade.
- `filters [typing.List[DTOFieldFilter] = None]`: Lista de filtros adicionais suportados para esta propriedade.
- `pk [bool = False]`: Indica se o campo é a chave primária da entidade.
- `use_default_validator [bool = True]`: Indica se o validador padrão deve ser aplicado à propriedade.
- `default_value [typing.Union[typing.Callable, typing.Any] = None]`: Valor padrão de preenchimento da propriedade, caso não seja fornecido.
- `partition_data [bool = False]`: Indica se esta propriedade participa dos campos de particionamento da entidade.
- `convert_to_entity [typing.Callable = None]`: Função para converter o valor do DTO para o valor da entidade.
- `convert_from_entity [typing.Callable = None]`: Função para converter o valor da entidade para o valor do DTO.
- `unique [str = None]`: Nome de chave de unicidade, usado para evitar duplicações no banco de dados.
- `candidate_key [bool = False]`: Indica se este campo é uma chave candidata.

**Exemplo:**
```
from nsj_rest_lib.descriptor.dto_field import DTOField, DTOFieldFilter
from nsj_rest_lib.descriptor.dto_field_validators import DTOFieldValidators

cliente: str = DTOField(resume=True, not_null=True, strip=True, min=11, max=60, 
    validator=DTOFieldValidators().validate_cpf_or_cnpj)
criado_em: datetime.datetime = DTOField(
        resume=True,
        filters=[
            DTOFieldFilter('criado_apos', FilterOperator.GREATER_THAN),
            DTOFieldFilter('criado_antes', FilterOperator.LESS_THAN),
        ],
        default_value=datetime.datetime.now
    )
```

### Controllers

#### [get_route](src/nsj_rest_lib/controller/get_route.py)

**Exemplo:**
```
from nsj_rest_lib.controller.get_route import GetRoute

@GetRoute(
    url=GET_ROUTE,
    http_method='GET',
    dto_class=ClienteDTO,
    entity_class=ClienteEntity
)
```

#### [list_route](src/nsj_rest_lib/controller/list_route.py)
***Exemplo:***
```
from nsj_rest_lib.controller.list_route import ListRoute

@ListRoute(
    url=LIST_ROUTE,
    http_method='GET',
    dto_class=ClienteDTO,
    entity_class=ClienteEntity
)
```

#### [post_route](src/nsj_rest_lib/controller/post_route.py)
***Exemplo:***
```
from nsj_rest_lib.controller.post_route import PostRoute

@PostRoute(
    url=LIST_POST_ROUTE,
    http_method='POST',
    dto_class=ClienteDTO,
    entity_class=ClienteEntity,
    dto_response_class=ClientePostReturnDTO
)
```

#### [put_route](src/nsj_rest_lib/controller/put_route.py)
***Exemplo:***
```
from nsj_rest_lib.controller.put_route import PutRoute

@PutRoute(
    url=GET_PUT_ROUTE,
    http_method='PUT',
    dto_class=ClienteDTO,
    entity_class=ClienteEntity
)
```

#### [delete_route](src/nsj_rest_lib/controller/delete_route.py)
***Exemplo:***
```
from nsj_rest_lib.controller.delete_route import DeleteRoute

@DeleteRoute(
    url=GET_DELETE_ROUTE,
    http_method="DELETE",
    dto_class=ClienteDTO,
    entity_class=ClienteEntity,
    injector_factory=InjectorFactoryMultibanco,
    service_name="cliente_service",
)
```
