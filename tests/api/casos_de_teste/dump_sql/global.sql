DELETE FROM teste.email WHERE tenant=:tenant;
DELETE FROM teste.cliente WHERE tenant=:tenant;
DELETE FROM teste.classificacoesfinanceiras WHERE true;

INSERT INTO teste.cliente
(id, estabelecimento, cliente, criado_em, criado_por, atualizado_em, atualizado_por, apagado_em, apagado_por, grupo_empresarial, tenant)
VALUES
('359ce9d9-ce5f-47bb-bbad-f162c2eaa3f3', '27915735000100', '27915735000100', '2023-08-12 00:00:00', 'teste@teste.com', '2023-08-12 00:00:00', 'teste@teste.com', NULL, NULL, '8e92ae13-992b-437d-b006-90da41999b04', 99999),
('360ce9d9-ce5f-47bb-bbad-f162c2eaa3f3', '27915735000100', '27915735000101', '2023-08-12 00:00:00', 'teste@teste.com', '2023-08-12 00:00:00', 'teste@teste.com', NULL, NULL, '8e92ae13-992b-437d-b006-90da41999b04', 99999),
('361ce9d9-ce5f-47bb-bbad-f162c2eaa3f3', '27915735000100', '27915735000102', '2023-08-12 00:00:00', 'teste@teste.com', '2023-08-12 00:00:00', 'teste@teste.com', NULL, NULL, '8e92ae13-992b-437d-b006-90da41999b04', 99999);


INSERT INTO teste.email (id, cliente_id, email, criado_em, criado_por, atualizado_em, atualizado_por, apagado_em, apagado_por, grupo_empresarial, tenant)
VALUES
(uuid_generate_v4(), '359ce9d9-ce5f-47bb-bbad-f162c2eaa3f3', 'teste@teste.com', now(), 'teste@teste.com', now(), 'teste@teste.com', null, null, '8e92ae13-992b-437d-b006-90da41999b04', 99999),
(uuid_generate_v4(), '359ce9d9-ce5f-47bb-bbad-f162c2eaa3f3', 'testemunha@teste.com', now(), 'teste@teste.com', now(), 'teste@teste.com', null, null, '8e92ae13-992b-437d-b006-90da41999b04', 99999),
(uuid_generate_v4(), '360ce9d9-ce5f-47bb-bbad-f162c2eaa3f3', 'teste2@teste.com', now(), 'teste@teste.com', now(), 'teste@teste.com', null, null, '8e92ae13-992b-437d-b006-90da41999b04', 99999);

INSERT INTO teste.classificacoesfinanceiras (codigo, descricao, codigocontabil, resumo, situacao, versao, natureza, classificacaofinanceira, paiid, grupoempresarial, lastupdate, resumoexplicativo, importacao_hash, iniciogrupo, apenasagrupador, id_erp, padrao, transferencia, repasse_deducao, tenant, rendimentos, categoriafinanceira, grupobalancete, atributo1, atributo2, atributo3)
VALUES
('teste-04', 'Classificação para teste do insert por funcao', NULL, NULL, 0, 1, 2, 'ffe29dad-e33d-4e9c-9803-5eb926e5bc21', NULL, '3964bfdc-e09e-4386-9655-5296062e632d'::uuid, '2025-11-06 14:28:16.429', NULL, NULL, false, false, NULL, false, false, false, NULL, false, NULL, NULL, NULL, NULL, NULL);