# Histórico de Versões

## 2.8.0

Novas features:

* Flag "read_only" no descritor DTOField.
  * Permite declarar propriedades que estão disponíveis no GET (list ou unitário), mas que não poderão ser usadas para gravação (POST, PUT ou PATCH).
  * A ideia é evitar a necessidade de criar outro DTO só por conta de algumas propriedades que servem apenas para leitura, mas que não podem ser alteradas pelo usuário (normalmente geridas pelo próprio sistema).