DELETE FROM teste.cliente WHERE tenant=:tenant;

INSERT INTO teste.cliente
(id, estabelecimento, cliente, criado_em, criado_por, atualizado_em, atualizado_por, apagado_em, apagado_por, grupo_empresarial, tenant)
VALUES('359ce9d9-ce5f-47bb-bbad-f162c2eaa3f3', '27915735000100', '27915735000100', '2023-08-12 00:00:00', 'teste@teste.com', '2023-08-12 00:00:00', 'teste@teste.com', NULL, NULL, '8e92ae13-992b-437d-b006-90da41999b04', 99999);