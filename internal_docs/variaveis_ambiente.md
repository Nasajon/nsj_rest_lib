# Variáveis de ambiente necessárias no seu projeto

## Variáveis gerais

| Variável                 | Obrigatória        | Descrição                                                  |
| ------------------------ | ------------------ | ---------------------------------------------------------- |
| APP_NAME                 | Sim                | Nome da aplicação.                                         |
| DEFAULT_PAGE_SIZE        | Não (padrão: 20)   | Quantidade máxima de items retonardos numa página de dados |
| USE_SQL_RETURNING_CLAUSE | Não (padrão: true) | Montagem das cláusulas returning                           |
| TESTS_TENANT             | Sim                | Código do tenant obrigatório para rodar os testes          |

## Variáveis de banco

| Variável        | Obrigatória            | Descrição                                  |
| --------------- | ---------------------- | ------------------------------------------ |
| DATABASE_HOST   | Sim                    | IP ou nome do host, para conexão com o BD. |
| DATABASE_PASS   | Sim                    | Senha para conexão com o BD.               |
| DATABASE_PORT   | Sim                    | Porta para conexão com o BD.               |
| DATABASE_NAME   | Sim                    | Nome do BD.                                |
| DATABASE_USER   | Sim                    | Usuário para conexão com o BD.             |
| DATABASE_DRIVER | Não (padrão: POSTGRES) | Driver para conexão com o BD.              |

## Variáveis do RabbitMQ

| Variável           | Obrigatória           | Descrição           |
| ------------------ | --------------------- | ------------------- |
| RABBITMQ_HOST      | Não                   | IP ou nome do host. |
| RABBITMQ_HTTP_PORT | Não (padrão: 15672)   | Porta para conexão. |
| RABBITMQ_USER      | Não   (padrão: guest) | Senha para conexão. |
| RABBITMQ_PASS      | Não (padrão: guest)   | Senha para conexão. |
