CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE EXTENSION IF NOT EXISTS unaccent;

create schema teste;

create table teste.cliente (
	id uuid not null default uuid_generate_v4(),
	estabelecimento varchar(60) not null,
	cliente varchar(60) not null,
	criado_em timestamp without time zone not null default now(),
	criado_por varchar(150) not null,
	atualizado_em timestamp without time zone not null default now(),
	atualizado_por varchar(150) not null,
	apagado_em timestamp without time zone,
	apagado_por varchar(150),
	grupo_empresarial varchar(36) not null,
	tenant bigint not null,
	PRIMARY KEY (tenant, grupo_empresarial, id)
);

CREATE TABLE teste.email (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	cliente_id uuid NULL,
	email varchar(150) NULL,
	criado_em timestamp without time zone not null default now(),
	criado_por varchar(150) not null,
	atualizado_em timestamp without time zone not null default now(),
	atualizado_por varchar(150) not null,
	apagado_em timestamp without time zone,
	apagado_por varchar(150),
	grupo_empresarial varchar(36) not null,
	tenant bigint not null,
	PRIMARY KEY (tenant, grupo_empresarial, id),
	FOREIGN KEY (tenant, grupo_empresarial, cliente_id) REFERENCES teste.cliente (tenant, grupo_empresarial, id)
);

CREATE TABLE teste.classificacoesfinanceiras (
	codigo varchar(30) NOT NULL,
	descricao varchar(150) NULL,
	codigocontabil varchar(20) NULL,
	resumo varchar(30) NULL,
	situacao int2 DEFAULT 0 NOT NULL,
	versao int8 DEFAULT 1 NULL,
	natureza int2 DEFAULT 0 NULL,
	classificacaofinanceira uuid DEFAULT uuid_generate_v4() NOT NULL,
	paiid uuid NULL,
	grupoempresarial uuid NULL,
	lastupdate timestamp DEFAULT now() NULL,
	resumoexplicativo text NULL,
	importacao_hash varchar NULL,
	iniciogrupo bool DEFAULT false NOT NULL,
	apenasagrupador bool DEFAULT false NOT NULL,
	id_erp int8 NULL,
	padrao bool DEFAULT false NULL,
	transferencia bool DEFAULT false NOT NULL,
	repasse_deducao bool DEFAULT false NOT NULL,
	tenant int8 NULL,
	rendimentos bool DEFAULT false NOT NULL,
	categoriafinanceira uuid NULL,
	grupobalancete varchar(150) NULL,
	atributo1 varchar(50) NULL,
	atributo2 varchar(50) NULL,
	atributo3 varchar(50) NULL,
	CONSTRAINT "PK_classificacoesfinanceiras_classificacaofinanceira" PRIMARY KEY (classificacaofinanceira)
);

CREATE TYPE teste.tclassificacaofinanceiranovo AS (
	idclassificacao uuid,
	classificacaopai text,
	grupoempresarial text,
	codigo varchar(16),
	descricao varchar(150),
	codigocontabil varchar(20),
	resumo varchar(30),
	natureza int4,
	transferencia bool,
	repasse_deducao bool,
	rendimentos bool
);

CREATE TYPE teste.trecibo AS (
	mensagem json);

CREATE OR REPLACE FUNCTION teste.api_montamensagem(a_codigo text, a_mensagem text, a_tipo text DEFAULT ''::text)
 RETURNS json
 LANGUAGE plpgsql
 IMMUTABLE
AS $function$
BEGIN          
    RETURN ('{"codigo" : "' || COALESCE(a_codigo, '') || '", "mensagem" : "' || REPLACE(COALESCE(a_mensagem, ''), '"', '\"')  || '", "tipo": "' || a_tipo || '"}' )::JSON; 
END;
$function$
;

CREATE OR REPLACE FUNCTION teste.api_classificacaofinanceiranovo(a_objeto teste.tclassificacaofinanceiranovo)
 RETURNS teste.trecibo
 LANGUAGE plpgsql
AS $function$
	DECLARE VAR_GRUPOEMPRESARIAL UUID;
	DECLARE VAR_ID UUID;
	DECLARE VAR_CLASSIFICACAO_PAI_ID UUID;
	DECLARE VAR_NATUREZA INTEGER;
	DECLARE VAR_RECIBO teste.TRECIBO;
BEGIN      
	--VERIFICA CAMPOS OBRIGATORIOS
	IF ( a_objeto.codigo IS NULL ) OR ( a_objeto.codigo = '' ) THEN
		VAR_RECIBO.MENSAGEM := teste.API_MONTAMENSAGEM('FALHA', 'Código não informado.' );
		RETURN VAR_RECIBO;
        END IF;

	IF EXISTS ( SELECT CODIGO 
                    FROM teste.CLASSIFICACOESFINANCEIRAS 
                    WHERE UPPER(CODIGO) = UPPER(a_objeto.codigo)
		      AND GRUPOEMPRESARIAL = VAR_GRUPOEMPRESARIAL ) THEN
		VAR_RECIBO.MENSAGEM := teste.API_MONTAMENSAGEM('FALHA', 'Código: ' || a_objeto.codigo || ' já cadastrado no sistema.' );
		RETURN VAR_RECIBO;
	END IF;

	IF NOT ( a_objeto.natureza IS NULL ) AND ( a_objeto.natureza NOT IN (0,1,2) ) THEN
		VAR_RECIBO.MENSAGEM := teste.API_MONTAMENSAGEM('FALHA', 'Natureza da classificação deve ser informada com um dos seguintes valores[0,1,2].' );
		RETURN VAR_RECIBO;
        END IF;

        VAR_NATUREZA := COALESCE( a_objeto.natureza, 0 ); --indefinido
	
	VAR_CLASSIFICACAO_PAI_ID := NULL;
	
	--INSERE A CLASSIFICACAO FINANCEIRA
	INSERT INTO teste.CLASSIFICACOESFINANCEIRAS( CODIGO, 
							DESCRICAO, 
							CODIGOCONTABIL, 
							RESUMO, 
							SITUACAO, 
							NATUREZA, 
							CLASSIFICACAOFINANCEIRA, 
							PAIID, 
							GRUPOEMPRESARIAL,
							TRANSFERENCIA,
							REPASSE_DEDUCAO,
							RENDIMENTOS)
		VALUES ( a_objeto.codigo,
			 COALESCE( a_objeto.descricao, NULL ),	
			 COALESCE( a_objeto.codigocontabil, NULL ),	
			 COALESCE( a_objeto.resumo, NULL ),	
			 0, --ativo
			 VAR_NATUREZA,
			 a_objeto.idclassificacao,
			 COALESCE( VAR_CLASSIFICACAO_PAI_ID, NULL ),
                         VAR_GRUPOEMPRESARIAL,
			 COALESCE( a_objeto.transferencia, FALSE),
			 COALESCE( a_objeto.repasse_deducao, FALSE),
			 COALESCE( a_objeto.rendimentos, FALSE));

	VAR_RECIBO.MENSAGEM := teste.API_MONTAMENSAGEM('OK', 'Classificação financeira inserida com sucesso.' );
	RETURN VAR_RECIBO;
END;
$function$
;
