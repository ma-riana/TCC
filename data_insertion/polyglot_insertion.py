import csv
import logging
import os
from datetime import date, datetime
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

PG_CONFIG = {
    'host': os.getenv('PG_HOST', 'localhost'),
    'port': os.getenv('PG_PORT', '5433'),
    'dbname': os.getenv('PG_DATABASE', 'benchmark_db'),
    'user': os.getenv('PG_USER', 'admin'),
    'password': os.getenv('PG_PASSWORD', 'password123'),
}

NEO4J_URI = os.getenv('NEO4J_POLYGLOT_URI', 'bolt://localhost:7688')
NEO4J_USER = os.getenv('NEO4J_POLYGLOT_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_POLYGLOT_PASSWORD', 'password123')

BASE_DIR = Path(r'C:\Users\maria\OneDrive\Documents\TCC\fake_data\csvs')
MAIN_DIR = BASE_DIR / 'main'
OTHER_DIR = BASE_DIR / 'other_sources'
LOG_DIR = Path(__file__).resolve().parent / 'logs'

NODE_BATCH_SIZE = 5000
RELATIONSHIP_BATCH_SIZE = 10000


def setup_logger(name):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger(name)
    log.setLevel(logging.INFO)
    handler = logging.FileHandler(LOG_DIR / f'{name}_{datetime.now():%Y%m%d_%H%M%S}.log', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    log.addHandler(handler)
    return log


logger = setup_logger('polyglot_insertion')

TABLE_ORDER = [
    'modalidade_licitacao',
    'municipio',
    'situacao_cadastral',
    'pessoa',
    'ente',
    'unidade_gestora',
    'processo_licitatorio',
    'documento',
    'item_licitacao',
    'contrato',
    'cotacao',
    'pessoa_fisica',
    'pessoa_juridica',
    'estabelecimento',
    'processo_licitatorio_pessoa',
    'item_cotacao',
    'contrato_cotacao',
]

GRAPH_ENTITIES = {
    'pessoa': ('Pessoa', 'id_pessoa'),
    'processo_licitatorio': ('ProcessoLicitatorio', 'id_processo_licitatorio'),
    'contrato': ('Contrato', 'id_contrato'),
    'item_licitacao': ('ItemLicitacao', 'id_item'),
}

GRAPH_RELATIONSHIPS = [
    ('CONTRATO_PROCESSO_LICITATORIO', 'Contrato', 'ProcessoLicitatorio', 'id_processo_licitatorio'),
    ('ITEM_LICITACAO_PROCESSO_LICITATORIO', 'ItemLicitacao', 'ProcessoLicitatorio', 'id_processo_licitatorio'),
]

# Índices além da PK (id, codigo_fonte): usados por T3 e T4, que buscam por propriedade em vez de aresta
GRAPH_EXTRA_INDEXES = [
    ('Contrato', 'id_processo_licitatorio'),
]

INTEGER_COLUMNS = {
    'id_pessoa', 'tipo_pessoa', 'id_processo_licitatorio', 'id_modalidade_licitacao', 'id_unidade_gestora',
    'id_contrato', 'id_contrato_superior', 'id_item', 'numero_item', 'quantidade', 'reported_bidders',
    'amendment_count', 'catalog_code', 'homologated_quantity',
}
FLOAT_COLUMNS = {
    'valor_previsto', 'valor_garantia', 'valor_contrato', 'valor_unitario_estimado', 'risk_score',
    'execution_percent', 'price_bank_reference',
}
BOOLEAN_COLUMNS = {'estrangeiro', 'internacional', 'sanction_flag'}
DATE_COLUMNS = {
    'data_limite_propostas', 'data_aprovacao_acessoria_juridica', 'data_abertura', 'data_planilha_custos',
    'data_homologacao', 'competencia', 'data_assinatura', 'data_vencimento', 'data_autorizacao_estadual',
    'registry_updated_at', 'publication_date',
}


def load_relational():
    connection = psycopg2.connect(**PG_CONFIG)
    try:
        with connection.cursor() as cursor:
            for table in TABLE_ORDER:
                path = MAIN_DIR / f'{table}.csv'
                if not path.exists():
                    logger.warning('Arquivo não encontrado, pulando: %s', path)
                    continue
                with open(path, newline='', encoding='utf-8') as handle:
                    columns = next(csv.reader(handle))
                    handle.seek(0)
                    cursor.copy_expert(
                        f"COPY {table} ({', '.join(columns)}) FROM STDIN WITH (FORMAT csv, HEADER true)", handle)
                logger.info('%s linha(s) inserida(s) em %s', cursor.rowcount, table)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def convert(column, value):
    if column in INTEGER_COLUMNS:
        return int(value)
    if column in FLOAT_COLUMNS:
        return float(value)
    if column in BOOLEAN_COLUMNS:
        return value == 'True'
    if column in DATE_COLUMNS:
        return date.fromisoformat(value[:10])
    return value


def build_properties(row):
    prefix = f"{row['fonte'].lower()}_"
    properties = {}
    for column, value in row.items():
        if value == '':
            continue
        base_column = column[len(prefix):] if column.startswith(prefix) else column
        properties[column] = convert(base_column, value)
    properties['codigo_fonte'] = row['fonte']
    return properties


def read_batches(path):
    with open(path, newline='', encoding='utf-8') as handle:
        batch = []
        for row in csv.DictReader(handle):
            batch.append(build_properties(row))
            if len(batch) == NODE_BATCH_SIZE:
                yield batch
                batch = []
        if batch:
            yield batch


def resolve_entity(stem):
    for entity in GRAPH_ENTITIES:
        if stem.startswith(f'{entity}_'):
            return entity
    return None


def prepare_graph_schema(session):
    # Mesmo esquema do banco em grafo (graph_insertion.py), restrito às entidades que têm versões secundárias.
    for label, key in GRAPH_ENTITIES.values():
        # Remove o índice composto não único das versões anteriores deste script;
        # ele colidiria com a constraint de mesmas propriedades.
        session.run(f'DROP INDEX idx_{label.lower()}_key_source IF EXISTS').consume()
        session.run(
            f'CREATE CONSTRAINT uniq_{label.lower()} IF NOT EXISTS '
            f'FOR (n:{label}) REQUIRE (n.{key}, n.codigo_fonte) IS UNIQUE').consume()
        session.run(f'CREATE INDEX idx_{label.lower()}_key IF NOT EXISTS FOR (n:{label}) ON (n.{key})').consume()
    for label, prop in GRAPH_EXTRA_INDEXES:
        session.run(
            f'CREATE INDEX idx_{label.lower()}_{prop} IF NOT EXISTS FOR (n:{label}) ON (n.{prop})').consume()
    session.run('CALL db.awaitIndexes()').consume()
    logger.info('Constraints e índices do grafo criados')


def write_batch(tx, label, rows):
    tx.run(f'UNWIND $rows AS row CREATE (n:{label}) SET n = row', rows=rows).consume()


def load_graph():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            prepare_graph_schema(session)

            for path in sorted(OTHER_DIR.glob('*.csv')):
                entity = resolve_entity(path.stem)
                if entity is None:
                    logger.warning('Arquivo sem entidade conhecida, pulando: %s', path.name)
                    continue
                label = GRAPH_ENTITIES[entity][0]
                total = 0
                for batch in read_batches(path):
                    session.execute_write(write_batch, label, batch)
                    total += len(batch)
                logger.info('%s nó(s) %s criados a partir de %s', total, label, path.name)

            for relationship, origin, target, foreign_key in GRAPH_RELATIONSHIPS:
                session.run(f"""
                    MATCH (a:{origin})
                    WHERE a.{foreign_key} IS NOT NULL
                    CALL {{
                        WITH a
                        MATCH (b:{target} {{{foreign_key}: a.{foreign_key}, codigo_fonte: a.codigo_fonte}})
                        CREATE (a)-[:{relationship}]->(b)
                    }} IN TRANSACTIONS OF {RELATIONSHIP_BATCH_SIZE} ROWS
                """).consume()
                logger.info('Relacionamentos %s criados', relationship)
    finally:
        driver.close()


def main():
    logger.info('Início da inserção poliglota')
    try:
        load_relational()
        load_graph()
    except Exception:
        logger.exception('Falha durante a inserção poliglota')
        raise
    logger.info('Inserção poliglota concluída com sucesso')


if __name__ == '__main__':
    main()