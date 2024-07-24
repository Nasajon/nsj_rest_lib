# Histórico de Versões

## 2.11.0

Novas features:

* Declarar uso de um `service_name` customizado para propriedades do tipo `DTOListField`.
  * Assim, o service customizado pode executar também código customizado para manipular os registros de uma listagem (não ficando mais preso ao comportamento padrão do rest_lib).
  * O único requisito é que o service customizado siga a mesma interface pública do ServiceBase (delcarando-se os métodos: get, list, insert, update, partial_update e delete).
  * Útil para uso conjunto com a biblioteca `erp3-py-commons`, por exemplo, para a manipualação de listas de Anexos (no padrão do ERP3).

## 2.10.0

Novas features:

* Possibildiade de instanciar um DTO a partir de um dict, cujas entradas obedeçam a nomenclatura dos campos da entity (mesmo sem passar uma entity, de fato, no construtor)
  * Ver flag `kwargs_as_entity` no construtor da classe DTOBase

## 2.9.0

Novas features:

* APIs Desktop
  * Implementação de um Command Line Interface genérico.
  * A ideia é permitir a execução de qualquer uma das rotas, declaradas no padrão RestLib, como um commando invocável por meio de uma linha de comando (CLI).
  * Ver a [documentação completa](internal_docs/apis_desktop.md) da feature.

## 2.8.0

Novas features:

* Flag "read_only" no descritor DTOField.
  * Permite declarar propriedades que estão disponíveis no GET (list ou unitário), mas que não poderão ser usadas para gravação (POST, PUT ou PATCH).
  * A ideia é evitar a necessidade de criar outro DTO só por conta de algumas propriedades que servem apenas para leitura, mas que não podem ser alteradas pelo usuário (normalmente geridas pelo próprio sistema).