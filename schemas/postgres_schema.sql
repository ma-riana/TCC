-- SQL dump generated using DBML (dbml.dbdiagram.io)
-- Database: PostgreSQL
-- Generated at: 2026-08-26T18:46:11.897Z

CREATE TABLE "modalidade_licitacao" (
  "id_modalidade_licitacao" int4 PRIMARY KEY,
  "descricao" text,
  "fonte" text
);

CREATE TABLE "municipio" (
  "id_municipio" int4 PRIMARY KEY,
  "nome_municipio" text,
  "sigla_uf" char(2),
  "nome_uf" text,
  "fonte" text
);

CREATE TABLE "situacao_cadastral" (
  "id_situacao_cadastral" int4 PRIMARY KEY,
  "descricao" text,
  "fonte" text
);

CREATE TABLE "pessoa" (
  "id_pessoa" int4 PRIMARY KEY,
  "nome" text NOT NULL,
  "tipo_pessoa" int4 NOT NULL,
  "estrangeiro" bool,
  "fonte" text
);

CREATE TABLE "ente" (
  "id_ente" int8 PRIMARY KEY,
  "id_municipio" int4,
  "nome_ente" text,
  "id_tipo_esfera" int8,
  "fonte" text
);

CREATE TABLE "unidade_gestora" (
  "id_unidade_gestora" int4 PRIMARY KEY,
  "id_ente" int8,
  "nome_unidade" text,
  "sigla_unidade" text,
  "cep" text,
  "previdencia" bool,
  "fonte" text
);

CREATE TABLE "processo_licitatorio" (
  "id_processo_licitatorio" int8 PRIMARY KEY,
  "id_modalidade_licitacao" int4,
  "id_unidade_gestora" int4,
  "numero_processo_licitatorio" text,
  "numero_edital" text,
  "data_limite_propostas" date,
  "data_aprovacao_acessoria_juridica" date,
  "descricao_objeto" text,
  "valor_previsto" float8,
  "data_abertura" date,
  "data_planilha_custos" date,
  "data_homologacao" date,
  "valor_garantia" float8,
  "competencia" date,
  "internacional" bool,
  "fonte" text
);

CREATE TABLE "documento" (
  "id_documento" int4 PRIMARY KEY,
  "id_processo_licitatorio" int8,
  "codigo_documento" text,
  "tipo_documento" text,
  "descricao" text,
  "nome" text,
  "data_emissao" timestamp,
  "tamanho" text,
  "acesso_arquivo" text,
  "fonte" text
);

CREATE TABLE "item_licitacao" (
  "id_item" int4 PRIMARY KEY,
  "id_processo_licitatorio" int8,
  "numero_item" int4,
  "descricao" text,
  "quantidade" float8,
  "valor_unitario_estimado" float8,
  "unidade_medida" text,
  "fonte" text
);

CREATE TABLE "contrato" (
  "id_contrato" int4 PRIMARY KEY,
  "id_processo_licitatorio" int8,
  "id_contrato_superior" int4,
  "descricao_objetivo" text,
  "numero_contrato" text,
  "data_assinatura" date,
  "data_vencimento" date,
  "valor_contrato" float8,
  "valor_garantia" float8,
  "competencia" date,
  "num_autorizacao_estadual" text,
  "data_autorizacao_estadual" date,
  "fonte" text
);

CREATE TABLE "cotacao" (
  "id_cotacao" int4 PRIMARY KEY,
  "id_pessoa" int4,
  "numero_item" int4 NOT NULL,
  "qt_item_cotado" float8,
  "valor_cotado" float8,
  "vencedor" bool,
  "classificacao" int2,
  "fonte" text
);

CREATE TABLE "pessoa_fisica" (
  "id_pessoa" int4 PRIMARY KEY,
  "id_situacao_cadastral" int4,
  "cpf" text NOT NULL,
  "pais_residencia" int4,
  "faixa_etaria" char(5),
  "data_nascimento" date,
  "fonte" text
);

CREATE TABLE "pessoa_juridica" (
  "id_pessoa" int4 PRIMARY KEY,
  "cnpj" text NOT NULL,
  "razao_social" text,
  "data_abertura" date,
  "capital_social" float8,
  "pais_residencia" int4,
  "porte_empresa" text,
  "fonte" text
);

CREATE TABLE "estabelecimento" (
  "id_estabelecimento" int4 PRIMARY KEY,
  "id_pessoa_juridica" int4,
  "id_situacao_cadastral" int4,
  "id_municipio" int4,
  "matriz" bool,
  "nome_fantasia" text,
  "data_inicio_atividade" date,
  "cnae_principal" int4,
  "endereco" text,
  "cep" text,
  "telefones" json,
  "email" text,
  "situacao_especial" text,
  "data_situacao_especial" date,
  "fonte" text
);

CREATE TABLE "processo_licitatorio_pessoa" (
  "id_processo_licitatorio" int8,
  "id_pessoa" int4
);

CREATE TABLE "item_cotacao" (
  "id_item" int4,
  "id_cotacao" int4
);

CREATE TABLE "contrato_cotacao" (
  "id_contrato" int4,
  "id_cotacao" int4
);

ALTER TABLE "ente" ADD FOREIGN KEY ("id_municipio") REFERENCES "municipio" ("id_municipio") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "unidade_gestora" ADD FOREIGN KEY ("id_ente") REFERENCES "ente" ("id_ente") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "processo_licitatorio" ADD FOREIGN KEY ("id_modalidade_licitacao") REFERENCES "modalidade_licitacao" ("id_modalidade_licitacao") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "processo_licitatorio" ADD FOREIGN KEY ("id_unidade_gestora") REFERENCES "unidade_gestora" ("id_unidade_gestora") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "documento" ADD FOREIGN KEY ("id_processo_licitatorio") REFERENCES "processo_licitatorio" ("id_processo_licitatorio") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "item_licitacao" ADD FOREIGN KEY ("id_processo_licitatorio") REFERENCES "processo_licitatorio" ("id_processo_licitatorio") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "contrato" ADD FOREIGN KEY ("id_processo_licitatorio") REFERENCES "processo_licitatorio" ("id_processo_licitatorio") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "cotacao" ADD FOREIGN KEY ("id_pessoa") REFERENCES "pessoa" ("id_pessoa") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "pessoa_fisica" ADD FOREIGN KEY ("id_pessoa") REFERENCES "pessoa" ("id_pessoa") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "pessoa_fisica" ADD FOREIGN KEY ("id_situacao_cadastral") REFERENCES "situacao_cadastral" ("id_situacao_cadastral") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "pessoa_juridica" ADD FOREIGN KEY ("id_pessoa") REFERENCES "pessoa" ("id_pessoa") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "estabelecimento" ADD FOREIGN KEY ("id_pessoa_juridica") REFERENCES "pessoa_juridica" ("id_pessoa") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "estabelecimento" ADD FOREIGN KEY ("id_situacao_cadastral") REFERENCES "situacao_cadastral" ("id_situacao_cadastral") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "estabelecimento" ADD FOREIGN KEY ("id_municipio") REFERENCES "municipio" ("id_municipio") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "processo_licitatorio_pessoa" ADD FOREIGN KEY ("id_processo_licitatorio") REFERENCES "processo_licitatorio" ("id_processo_licitatorio") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "processo_licitatorio_pessoa" ADD FOREIGN KEY ("id_pessoa") REFERENCES "pessoa" ("id_pessoa") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "item_cotacao" ADD FOREIGN KEY ("id_item") REFERENCES "item_licitacao" ("id_item") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "item_cotacao" ADD FOREIGN KEY ("id_cotacao") REFERENCES "cotacao" ("id_cotacao") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "contrato_cotacao" ADD FOREIGN KEY ("id_contrato") REFERENCES "contrato" ("id_contrato") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "contrato_cotacao" ADD FOREIGN KEY ("id_cotacao") REFERENCES "cotacao" ("id_cotacao") DEFERRABLE INITIALLY IMMEDIATE;

CREATE INDEX IF NOT EXISTS idx_documento_processo ON documento (id_processo_licitatorio);

CREATE INDEX IF NOT EXISTS idx_item_licitacao_processo ON item_licitacao (id_processo_licitatorio);

CREATE INDEX IF NOT EXISTS idx_contrato_processo ON contrato (id_processo_licitatorio);

CREATE INDEX IF NOT EXISTS idx_plp_processo ON processo_licitatorio_pessoa (id_processo_licitatorio);

CREATE INDEX IF NOT EXISTS idx_item_cotacao_item ON item_cotacao (id_item);

CREATE INDEX IF NOT EXISTS idx_item_cotacao_cotacao ON item_cotacao (id_cotacao);

ANALYZE;