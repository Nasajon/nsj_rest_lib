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

--------------------------------------------------
-- Classificação Financeira
--------------------------------------------------
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

CREATE OR REPLACE FUNCTION teste.api_montamensagemok(a_mensagem text)
 RETURNS json
 LANGUAGE plpgsql
 IMMUTABLE
AS $function$
BEGIN          
    RETURN ('{"codigo" : "OK", "mensagem" : "' || COALESCE(a_mensagem, '') || '", "tipo": ""}' )::JSON; 
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

--------------------------------------------------
-- Cliente
--------------------------------------------------

CREATE TABLE teste.enderecos (
	tipologradouro varchar(10) NULL,
	logradouro varchar(150) NULL,
	numero varchar(10) NULL,
	complemento varchar(60) NULL,
	cep varchar(15) NULL,
	bairro varchar(60) NULL,
	tipoendereco int2 NULL,
	ufexterior varchar(2) NULL,
	enderecopadrao int2 NULL,
	uf varchar(2) NULL,
	pais varchar(5) NULL,
	ibge varchar(8) NULL,
	cidade varchar(60) NULL,
	referencia varchar NULL,
	versao int8 DEFAULT 1 NULL,
	endereco uuid DEFAULT uuid_generate_v4() NOT NULL,
	id_pessoa uuid NULL,
	lastupdate timestamp DEFAULT now() NULL,
	tenant int8 NULL,
	id_pessoafisica uuid NULL,
	id_proposta uuid NULL,
	id_ordemservico uuid NULL,
	CONSTRAINT "PK_enderecos_endereco" PRIMARY KEY (endereco)
);

CREATE TABLE teste.pessoas (
	pessoa varchar(30) NOT NULL,
	datacadastro date NULL,
	proximocontato date NULL,
	nome varchar(150) NULL,
	nomefantasia varchar(150) NULL,
	tp_identificacao int4 NULL,
	cnpj varchar(18) NULL,
	chavecnpj varchar(18) NULL,
	cpf varchar(18) NULL,
	caepf varchar(18) NULL,
	inscricaoestadual varchar(20) NULL,
	inscestsubstituto varchar(20) NULL,
	inscricaomunicipal varchar(20) NULL,
	rntrc varchar(14) NULL,
	identidade varchar(20) NULL,
	suframa varchar(14) NULL,
	nit varchar(11) NULL,
	nire varchar(11) NULL,
	observacao varchar(255) NULL,
	email varchar(150) NULL,
	site varchar(150) NULL,
	codigopis varchar(6) NULL,
	codigocofins varchar(6) NULL,
	codigocsll varchar(6) NULL,
	codigoirrf varchar(6) NULL,
	conta varchar(15) NULL,
	contrapartida varchar(16) NULL,
	contadesconto varchar(16) NULL,
	contajuros varchar(16) NULL,
	classefinpersona varchar(16) NULL,
	contacorrente varchar(16) NULL,
	ccustopersona varchar(10) NULL,
	contamulta varchar(16) NULL,
	contaestoque varchar(16) NULL,
	bloqueado bool DEFAULT false NOT NULL,
	contribuinteicms bool NULL,
	contribuinteipi bool NULL,
	produtorrural bool NULL,
	substitutomunicipal bool NULL,
	tiposimples int4 NULL,
	qualificacao int4 NULL,
	icmssimp int4 NULL,
	regimereceita int4 NULL,
	percentualtaxaservicoscooperativa float8 NULL,
	percentualinsscooperativa float8 NULL,
	lastupdate timestamp DEFAULT now() NULL,
	orgaoemissor varchar(10) NULL,
	tipoicms int2 NULL,
	codigocontabilcliente varchar(20) NULL,
	anotacao text NULL,
	datacliente date NULL,
	datafornecedor date NULL,
	datavendedor date NULL,
	leadativado int2 DEFAULT 0 NOT NULL,
	clienteativado int2 DEFAULT 0 NOT NULL,
	fornecedorativado int2 DEFAULT 0 NOT NULL,
	vendedorativado int2 DEFAULT 0 NOT NULL,
	transportadoraativado int2 DEFAULT 0 NOT NULL,
	pagamentounificado int2 NULL,
	tipovencimento int2 NULL,
	diavencimento int2 NULL,
	notaantecipadacobranca int2 NULL,
	emailcobranca varchar(200) NULL,
	enviarnfeporemail int2 NULL,
	pontofidelidade float8 NULL,
	retempis int2 NULL,
	retemcofins int2 NULL,
	retemcsll int2 NULL,
	retemirrf int2 NULL,
	retemiss int2 NULL,
	tipolead int2 NULL,
	descricao varchar(150) NULL,
	totalfuncionarios int4 NULL,
	receitaanual float4 NULL,
	datacriacao timestamp NULL,
	codigocontabilfornecedor varchar(20) NULL,
	banco varchar(3) NULL,
	agencianumero varchar(10) NULL,
	agencianome varchar(50) NULL,
	contanumero varchar(20) NULL,
	podeparticiparagendamento int2 DEFAULT 0 NOT NULL,
	codigocontabiltransportadora varchar(20) NULL,
	datatransportadora date NULL,
	cobrancaaposservico int2 NULL,
	prorataantecipada int2 NULL,
	celulavenda uuid NULL,
	classificacaolead uuid NULL,
	midiaorigem uuid NULL,
	parcelamento uuid NULL,
	promocaolead uuid NULL,
	representante uuid NULL,
	segmentoatuacao uuid NULL,
	statuslead uuid NULL,
	agencia uuid NULL,
	centrocusto uuid NULL,
	id_grupo uuid NULL,
	idclasspessoacliente uuid NULL,
	idclasspessoafornecedor uuid NULL,
	idclasspessoatransportadora uuid NULL,
	idclasspessoavendedor uuid NULL,
	classificado uuid NULL,
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	captador uuid NULL,
	vendedor uuid NULL,
	usuariovendedor uuid NULL,
	criador uuid NULL,
	contatoativado int2 DEFAULT 0 NOT NULL,
	id_receitadiferenciada uuid NULL,
	id_despesadiferenciada uuid NULL,
	tecnicoativado int2 DEFAULT 0 NOT NULL,
	tpcontacompra int4 NULL,
	fichaativado int2 DEFAULT 1 NOT NULL,
	categoriatecnico_id uuid NULL,
	percentualfaturamentoservico float8 NULL,
	percentualfaturamentoencargo float8 NULL,
	percentualfaturamentoiss float8 NULL,
	percentualfaturamentoretencao float8 NULL,
	tributoativado int2 DEFAULT 0 NOT NULL,
	valormaxdesconto float8 NULL,
	id_conta uuid NULL,
	id_rateiopadrao uuid NULL,
	enviarboletoporemail int2 DEFAULT 1 NULL,
	concessionariapublica bool DEFAULT false NOT NULL,
	codigoconcessionaria varchar(4) NULL,
	id_conta_receber uuid NULL,
	id_rateiopadrao_receber uuid NULL,
	id_layoutcobranca uuid NULL,
	id_cliente_fatura uuid NULL,
	diafaturamento int4 NULL,
	diasvencimentofatura int4 NULL,
	id_formapagamento uuid NULL,
	aliquotarat float8 NULL,
	aliquotafap float8 NULL,
	aliquotaterceiros float8 NULL,
	templateordemservico uuid NULL,
	nacionalidade int4 DEFAULT 0 NULL,
	chavegold text NULL,
	id_faixadecredito uuid NULL,
	limite_de_credito numeric(20, 4) NULL,
	importacao_hash text NULL,
	id_erp bigserial,
	retem_inss bool DEFAULT false NULL,
	enderecocobrancautilizarenderecoprincipal bool DEFAULT false NOT NULL,
	enderecoentregautilizarenderecoprincipal bool DEFAULT false NOT NULL,
	classificado_old uuid NULL,
	ajuste_cnpj bool DEFAULT false NOT NULL,
	representantecomercialativado int2 DEFAULT 0 NULL,
	representantetecnicoativado int2 DEFAULT 0 NULL,
	representante_old uuid NULL,
	representante_tecnico uuid NULL,
	template_rps uuid NULL,
	percentualtaxacobrancaterceirizacao numeric(20, 6) NULL,
	dataultimacompra date NULL,
	valorultimacompra numeric(20, 2) NULL,
	contratounificadonacobranca bool DEFAULT false NULL,
	vendedor_anterior uuid NULL,
	usarvencimentounificado bool DEFAULT false NULL,
	diavencimentounificado int4 NULL,
	projeto uuid NULL,
	indicadorinscricaoestadual int2 NULL,
	comissao numeric(20, 2) NULL,
	json_elementos_controle json NULL,
	enviarnfseporemail bool DEFAULT false NULL,
	documentoestrangeiro varchar(20) NULL,
	id_formapagamento_fornecedor uuid NULL,
	cnpjsemformato varchar NULL,
	tipocontrolepagamento int2 DEFAULT 2 NULL,
	situacaopagamento int2 DEFAULT 0 NULL,
	tipoclientepagamento int2 DEFAULT 0 NULL,
	justificativasituacaopagamento varchar(255) NULL,
	justificativatipoclientepagamento varchar(255) NULL,
	inscritapaa bool NULL,
	retem_abaixo_minimo bool DEFAULT false NULL,
	id_fornecedorfactoring uuid NULL,
	funcionarioativado int2 DEFAULT 0 NOT NULL,
	contribuinteindividualativado int2 DEFAULT 0 NOT NULL,
	tomadorfolhaativado int2 DEFAULT 0 NOT NULL,
	classificacaofinanceirafrete uuid NULL,
	classificacaofinanceiraseguro uuid NULL,
	classificacaofinanceiraoutdesp uuid NULL,
	notafutura bool DEFAULT false NULL,
	datasituacaopagamento date NULL,
	datatipoclientepagamento date NULL,
	reguacobranca uuid NULL,
	restricaocobranca1 uuid NULL,
	restricaocobranca2 uuid NULL,
	restricaocobranca3 uuid NULL,
	grupodeparticipante uuid NULL,
	tipocliente_codigo varchar(20) NULL,
	tipocliente_descricao varchar(100) NULL,
	tenant int8 NULL,
	desabilitadopersona bool DEFAULT false NOT NULL,
	ajudanteativado int4 NULL,
	formatributacaofunrural int2 NULL,
	cnae varchar(7) NULL,
	valor_comissao int4 NULL,
	recebimento_comissao int4 NULL,
	prospectativado int4 NULL,
	id_transportadora uuid NULL,
	id_historicopadraoestoque uuid NULL,
	nascimento date NULL,
	confirmacao_email varchar(150) NULL,
	mensagem_de_alerta text NULL,
	tiponegocio uuid NULL,
	atividadeicms int4 DEFAULT 0 NULL,
	id_conjunto uuid NULL,
	suframa_perc_reducao_icms numeric(15, 2) DEFAULT 0 NULL,
	suframa_perc_reducao_ipi numeric(15, 2) DEFAULT 0 NULL,
	suframa_perc_descto numeric(15, 2) DEFAULT 0 NULL,
	suframa_perc_descto_pis_confins numeric(15, 2) DEFAULT 0 NULL,
	suframa_dtvalidade date NULL,
	suframa_habilitar_descto bool DEFAULT false NULL,
	suframa_descto_icms_basecalc bool DEFAULT false NULL,
	suframa_descto_pis_confins bool DEFAULT false NULL,
	suframa_descto_icms_antes bool DEFAULT false NULL,
	suframa_incluir_desp_basecalc_icms bool DEFAULT false NULL,
	suframa_isencao_ipi bool DEFAULT false NULL,
	enviarxmlnfseporemail bool DEFAULT false NULL,
	enviarpdfnfseporemail bool DEFAULT false NULL,
	pendenciaaprovacaocliente bool NULL,
	suframa_desoneracao_icms bool DEFAULT true NULL,
	suframa_destaque_ipi bool DEFAULT false NULL,
	aliquotapis float8 NULL,
	aliquotacofins float8 NULL,
	aliquotairrf float8 NULL,
	aliquotacsll float8 NULL,
	incentivopis bool DEFAULT false NULL,
	incentivoipi bool DEFAULT false NULL,
	id_potencialportfolio uuid NULL,
	negativado bool NULL,
	prioridade int4 NULL,
	classificacaoabc varchar(1) NULL,
	reinf_natrend varchar(5) NULL,
	data_atualizacao_nasajonhub date NULL,
	aplica_regra_abaixo_minimo bool DEFAULT false NULL,
	grupovendedor uuid NULL,
	descontofixo numeric(20, 4) NULL,
	tipooperacao int4 DEFAULT '-1'::integer NULL,
	CONSTRAINT "PK_pessoas_id" PRIMARY KEY (id),
	CONSTRAINT "UK_teste.pessoas_pessoa_id_grupo" UNIQUE (id_grupo, pessoa) DEFERRABLE,
	CONSTRAINT ck_tpcontacompra CHECK ((tpcontacompra = ANY (ARRAY[1, 2])))
);

CREATE TYPE teste.tendereco AS (
	id uuid,
	tipologradouro varchar(50),
	logradouro varchar(150),
	numero varchar(50),
	complemento varchar(100),
	cep varchar(30),
	bairro varchar(100),
	municipio varchar(50),
	pais varchar(50),
	uf varchar(2),
	tipo int4,
	enderecopadrao int4,
	referencia varchar(150),
	idpessoa uuid,
	cidade varchar(60),
	idpessoafisica uuid,
	idproposta uuid,
	idordemservico uuid);

CREATE TYPE teste.tclientenovo AS (
	cliente uuid,
	codigo varchar(30),
	nome varchar(150),
	nomefantasia varchar(150),
	identidade varchar(20),
	documento varchar(20),
	retemiss bool,
	retemir bool,
	retempis bool,
	retemcofins bool,
	retemcsll bool,
	reteminss bool,
	endereco teste._tendereco,
	inscricaoestadual varchar(20));

CREATE OR REPLACE FUNCTION teste.public_get_only_number(a_texto character varying)
 RETURNS text
 LANGUAGE plpgsql
AS $function$
	DECLARE VAR_CHAR VARCHAR;
	DECLARE VAR_RETURN VARCHAR;
BEGIN
	VAR_RETURN = '';
	FOR VAR_CHAR IN (SELECT UNNEST(REGEXP_SPLIT_TO_ARRAY(A_TEXTO,'')))
	LOOP
		IF NOT ((SELECT (VAR_CHAR ~'^[0-9]+$')::BOOLEAN)) THEN
			CONTINUE;
		ELSE
			VAR_RETURN = VAR_RETURN || VAR_CHAR;
		END IF;
	END LOOP;

	RETURN VAR_RETURN;
END;
$function$
;

CREATE OR REPLACE FUNCTION teste.api_endereco(a_objeto teste.tendereco)
 RETURNS teste.trecibo
 LANGUAGE plpgsql
AS $function$
	-- BEGIN DECLARE
	DECLARE VAR_RETURN teste.TRECIBO;	
	DECLARE VAR_ID_ENDERECO UUID;  
        DECLARE VAR_MONTACAMPOS text;
	DECLARE VAR_MONTACONDICAO text;
	DECLARE VAR_ENCONTRADO boolean;
	DECLARE VAR_LINHASAFETADAS integer;
	-- END DECLARE	
BEGIN      
	-- BEGIN CODE  
	IF A_OBJETO.IDPESSOA IS NULL THEN
		VAR_RETURN.MENSAGEM := teste.API_MONTAMENSAGEM('ERRO', 'A Pessoa não pode ser vazia.');
		RAISE EXCEPTION '%', VAR_RETURN.MENSAGEM;
	END IF;

	if true then
		VAR_ID_ENDERECO := UUID_GENERATE_V4();

		INSERT INTO teste.ENDERECOS(
			ENDERECO,
			TIPOLOGRADOURO,
			LOGRADOURO,
			NUMERO,
			COMPLEMENTO,
			CEP,
			BAIRRO,
			IBGE,
			PAIS,
			UF,
			TIPOENDERECO,
			ENDERECOPADRAO,
			REFERENCIA,
			ID_PESSOA		
			
		) VALUES (
			VAR_ID_ENDERECO,
			A_OBJETO.TIPOLOGRADOURO,
			A_OBJETO.LOGRADOURO,		
			A_OBJETO.NUMERO,		
			A_OBJETO.COMPLEMENTO,		
			A_OBJETO.CEP,		
			A_OBJETO.BAIRRO,
			null,
			null,
			A_OBJETO.UF,
			A_OBJETO.TIPO,
			A_OBJETO.ENDERECOPADRAO,
			A_OBJETO.REFERENCIA,
			A_OBJETO.IDPESSOA
		);		
	END IF;
	
	VAR_RETURN.MENSAGEM := teste.API_MONTAMENSAGEM('OK', 'Endereço cadastrado com sucesso');
	RETURN VAR_RETURN;
	-- END CODE	
END;
$function$
;

CREATE OR REPLACE FUNCTION teste.public_get_with_mask_cpf_cnpj(a_documento character varying)
 RETURNS text
 LANGUAGE plpgsql
AS $function$
	DECLARE VAR_DOCUMENTO VARCHAR;
BEGIN
	SELECT teste.PUBLIC_GET_ONLY_NUMBER(A_DOCUMENTO) INTO VAR_DOCUMENTO;

	IF (VAR_DOCUMENTO IS NULL) OR (VAR_DOCUMENTO = '') OR (LENGTH(VAR_DOCUMENTO) NOT IN (11, 14)) THEN
		--RAISE EXCEPTION 'O documento possui formato não suportado: %', A_DOCUMENTO;
        RETURN NULL;
	END IF;

	IF LENGTH(VAR_DOCUMENTO) = 11 THEN
		RETURN REPLACE((TO_CHAR(VAR_DOCUMENTO::BIGINT, '000"."000"."000"-"00'::text)), ' ', '');
	ELSEIF LENGTH(VAR_DOCUMENTO) = 14 THEN
		RETURN REPLACE((TO_CHAR(VAR_DOCUMENTO::BIGINT, '00"."000"."000"/"0000"-"00'::TEXT)), ' ', '');	
	END IF;
END;
$function$
;

CREATE OR REPLACE FUNCTION teste.api_montamensagemerro(a_mensagem text)
 RETURNS json
 LANGUAGE plpgsql
 IMMUTABLE
AS $function$

	DECLARE VAR_TIPO VARCHAR;
	DECLARE VAR_MENSGEM VARCHAR;

BEGIN          
	IF STRPOS(A_MENSAGEM, '#') > 0 THEN
		VAR_TIPO = COALESCE(SUBSTRING(a_mensagem from 1 for strpos(a_mensagem, '#')-1), '');
		VAR_MENSGEM = SUBSTRING(a_mensagem from strpos(a_mensagem, '#')+1 for LENGTH(a_mensagem));	
	ELSE
		VAR_TIPO = '';
		VAR_MENSGEM = A_MENSAGEM;
	END IF;
	RETURN ('{"codigo" : "ERRO", "tipo" : "'|| VAR_TIPO ||'", "mensagem" : "' || REPLACE(COALESCE(VAR_MENSGEM, ''), '"', '\"') || '"}' )::JSON; 
END;
$function$
;

CREATE OR REPLACE FUNCTION teste.api_clientenovo(a_objeto teste.tclientenovo, a_usaconfigadmincodigounico boolean DEFAULT true)
 RETURNS teste.trecibo
 LANGUAGE plpgsql
AS $function$
DECLARE
  var_return teste.TRecibo;
  var_guid_cliente uuid;
  var_encontrado boolean;
  var_guid_conjunto uuid;
  var_guids_conjuntos uuid[];
  var_endereco teste.TEndereco;
  var_documento_mascarado text;
  var_tipo_documento integer;
BEGIN
  BEGIN
	var_encontrado := False;

    IF NOT var_encontrado THEN
      var_guid_cliente := uuid_generate_v4();

      var_documento_mascarado := NULL;
      SELECT teste.PUBLIC_GET_WITH_MASK_CPF_CNPJ(a_objeto.documento) INTO var_documento_mascarado;

      var_tipo_documento := 0;
      IF LENGTH(var_documento_mascarado) = 14 THEN -- É CPF MASCARADO
        var_tipo_documento = 90; -- QUALIFICAÇÃO PESSOA FÍSICA EM GERAL
      END IF;

      INSERT INTO teste.pessoas
      (
        /*01*/id,
        /*02*/clienteativado,
        /*03*/pessoa,
        /*04*/nome,
        /*05*/nomefantasia,
        /*06*/identidade,
        /*07*/datacadastro,
        /*08*/bloqueado,
        /*09*/cnpj,
        /*10*/retemiss,
        /*11*/retemirrf,
        /*12*/retempis,
        /*13*/retemcofins,
        /*14*/retemcsll,
        /*15*/retem_inss,
        /*16*/inscricaoestadual,
        /*17*/qualificacao
      )
      VALUES
      (
        /*01*/var_guid_cliente,
        /*02*/1,
        /*03*/a_objeto.codigo,
        /*04*/a_objeto.nome,
        /*05*/a_objeto.nomefantasia,
        /*06*/a_objeto.identidade,
        /*07*/current_date,
        /*08*/FALSE,
        /*09*/var_documento_mascarado,
        /*10*/(case when coalesce(a_objeto.retemiss, false) = false then 0 else 1 end),
        /*11*/(case when coalesce(a_objeto.retemir, false) = false then 0 else 1 end),
        /*12*/(case when coalesce(a_objeto.retempis, false) = false then 0 else 1 end),
        /*13*/(case when coalesce(a_objeto.retemcofins, false) = false then 0 else 1 end),
        /*14*/(case when coalesce(a_objeto.retemcsll, false) = false then 0 else 1 end),
        /*15*/coalesce(a_objeto.retemiss, false),
        /*16*/a_objeto.inscricaoestadual,
        /*17*/var_tipo_documento
      );

      IF a_objeto.endereco IS NOT NULL THEN
        FOREACH var_endereco IN ARRAY a_objeto.endereco
        LOOP
          var_endereco.idpessoa := var_guid_cliente;
          var_return := teste.api_endereco(var_endereco);
        END LOOP;
      END IF;

    ElSE
      RETURN VAR_RETURN;
    END IF;

    VAR_RETURN.MENSAGEM := teste.api_montamensagemok(var_guid_cliente::varchar);

  EXCEPTION
    WHEN OTHERS THEN
      VAR_RETURN.MENSAGEM := teste.api_montamensagemerro(SQLERRM);
  END;

  RETURN VAR_RETURN;
END;
$function$
;

--------------------------------------------------
-- Classificação Financeira UPDATE
--------------------------------------------------

CREATE TYPE teste.tclassificacaofinanceiraalterar AS (
	classificacao text,
	classificacaopai text,
	grupoempresarial text,
	codigo varchar(16),
	descricao varchar(150),
	codigocontabil varchar(20),
	resumo varchar(30),
	situacao int4,
	natureza int4,
	transferencia bool,
	repasse_deducao bool,
	rendimentos bool);

CREATE OR REPLACE FUNCTION teste.api_classificacaofinanceiraalterar(a_objeto teste.tclassificacaofinanceiraalterar)
 RETURNS teste.trecibo
 LANGUAGE plpgsql
AS $function$
	DECLARE VAR_GRUPOEMPRESARIAL UUID;
	DECLARE VAR_ID UUID;
	DECLARE VAR_CLASSIFICACAO_PAI_ID UUID;
	DECLARE VAR_RECIBO teste.TRECIBO;
BEGIN      

	--VERIFICA CAMPOS OBRIGATORIOS
	IF ( a_objeto.codigo IS NULL ) OR ( a_objeto.codigo = '' ) THEN
		VAR_RECIBO.MENSAGEM := teste.API_MONTAMENSAGEM('FALHA', 'Código não informado.' );
		RETURN VAR_RECIBO;
        END IF;

	IF ( a_objeto.classificacao IS NULL ) OR ( a_objeto.classificacao = '' ) THEN
		VAR_RECIBO.MENSAGEM := teste.API_MONTAMENSAGEM('FALHA', 'Identificador da classificação não informado.' );
		RETURN VAR_RECIBO;
	END IF;

	IF a_objeto.grupoempresarial IS NOT NULL THEN
		VAR_GRUPOEMPRESARIAL := a_objeto.grupoempresarial::uuid;
	ELSE
		VAR_GRUPOEMPRESARIAL := NULL;
	END IF;

	VAR_ID := a_objeto.classificacao::uuid;

	IF ( a_objeto.situacao IS NULL ) THEN
		VAR_RECIBO.MENSAGEM := teste.API_MONTAMENSAGEM('FALHA', 'Situação não informada.' );
		RETURN VAR_RECIBO;
	END IF;

	IF NOT ( a_objeto.situacao IS NULL ) AND ( a_objeto.situacao NOT IN (0,1) ) THEN
		VAR_RECIBO.MENSAGEM := teste.API_MONTAMENSAGEM('FALHA', 'Situação da classificação deve ser informada com um dos seguintes valores[0,1].' );
		RETURN VAR_RECIBO;
        END IF;

	IF ( a_objeto.natureza IS NULL ) THEN
		VAR_RECIBO.MENSAGEM := teste.API_MONTAMENSAGEM('FALHA', 'Natureza não informada.' );
		RETURN VAR_RECIBO;
	END IF;

	IF NOT ( a_objeto.natureza IS NULL ) AND ( a_objeto.natureza NOT IN (0,1,2) ) THEN
		VAR_RECIBO.MENSAGEM := teste.API_MONTAMENSAGEM('FALHA', 'Natureza da classificação deve ser informadas com um dos seguintes valores[0,1,2].' );
		RETURN VAR_RECIBO;
        END IF;

        IF a_objeto.classificacaopai IS NOT NULL THEN
		VAR_CLASSIFICACAO_PAI_ID := a_objeto.classificacaopai::uuid;
	ELSE
		VAR_CLASSIFICACAO_PAI_ID := NULL;
	END IF;

	--ALTERA A CLASSIFICACAO FINANCEIRA
	UPDATE teste.CLASSIFICACOESFINANCEIRAS SET 
		CODIGO = a_objeto.codigo, 
		DESCRICAO = COALESCE( a_objeto.descricao, NULL ), 
		CODIGOCONTABIL = COALESCE( a_objeto.codigocontabil, NULL ), 
		RESUMO = COALESCE( a_objeto.resumo, NULL ), 
		SITUACAO = a_objeto.situacao, 
		NATUREZA = a_objeto.natureza, 
		PAIID = VAR_CLASSIFICACAO_PAI_ID,
		TRANSFERENCIA = COALESCE(a_objeto.transferencia, FALSE),
		REPASSE_DEDUCAO = COALESCE(a_objeto.repasse_deducao, FALSE),
		RENDIMENTOS = COALESCE(a_objeto.rendimentos, FALSE)
        WHERE CLASSIFICACAOFINANCEIRA = VAR_ID
          AND GRUPOEMPRESARIAL = VAR_GRUPOEMPRESARIAL; 
		
	VAR_RECIBO.MENSAGEM := teste.API_MONTAMENSAGEM('OK', 'Classificação financeira alterada com sucesso.' );
	RETURN VAR_RECIBO;
END;
$function$
;
