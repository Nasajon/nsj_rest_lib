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