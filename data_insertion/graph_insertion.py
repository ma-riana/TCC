import csv
import logging
import os
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'password123')

BASE_DIR = Path(r'C:\Users\maria\OneDrive\Documents\TCC\fake_data\csvs')
MAIN_DIR = BASE_DIR / 'main'
OTHER_DIR = BASE_DIR / 'other_sources'
LOG_DIR = Path(__file__).resolve().parent / 'logs'

MAIN_SOURCE = 'PT'
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


logger = setup_logger('graph_insertion')

NODE_TABLES = {
    'modalidade_licitacao': 'id_modalidade_licitacao',
    'municipio': 'id_municipio',
    'situacao_cadastral': 'id_situacao_cadastral',
    'pessoa': 'id_pessoa',
    'ente': 'id_ente',
    'unidade_gestora': 'id_unidade_gestora',
    'processo_licitatorio': 'id_processo_licitatorio',
    'documento': 'id_documento',
    'item_licitacao': 'id_item',
    'contrato': 'id_contrato',
    'cotacao': 'id_cotacao',
    'pessoa_fisica': 'id_pessoa',
    'pessoa_juridica': 'id_pessoa',
    'estabelecimento': 'id_estabelecimento',
}

LABELS = {
    'modalidade_licitacao': 'ModalidadeLicitacao',
    'municipio': 'Municipio',
    'situacao_cadastral': 'SituacaoCadastral',
    'pessoa': 'Pessoa',
    'ente': 'Ente',
    'unidade_gestora': 'UnidadeGestora',
    'processo_licitatorio': 'ProcessoLicitatorio',
    'documento': 'Documento',
    'item_licitacao': 'ItemLicitacao',
    'contrato': 'Contrato',
    'cotacao': 'Cotacao',
    'pessoa_fisica': 'PessoaFisica',
    'pessoa_juridica': 'PessoaJuridica',
    'estabelecimento': 'Estabelecimento',
}

SECONDARY_ENTITIES = ['pessoa', 'processo_licitatorio', 'contrato', 'item_licitacao']

DIRECT_RELATIONSHIPS = [
    ('ENTE_MUNICIPIO', 'ente', 'id_municipio', 'municipio', 'id_municipio'),
    ('ESTABELECIMENTO_MUNICIPIO', 'estabelecimento', 'id_municipio', 'municipio', 'id_municipio'),
    ('UNIDADE_GESTORA_ENTE', 'unidade_gestora', 'id_ente', 'ente', 'id_ente'),
    ('PROCESSO_LICITATORIO_MODALIDADE_LICITACAO', 'processo_licitatorio', 'id_modalidade_licitacao', 'modalidade_licitacao', 'id_modalidade_licitacao'),
    ('PROCESSO_LICITATORIO_UNIDADE_GESTORA', 'processo_licitatorio', 'id_unidade_gestora', 'unidade_gestora', 'id_unidade_gestora'),
    ('DOCUMENTO_PROCESSO_LICITATORIO', 'documento', 'id_processo_licitatorio', 'processo_licitatorio', 'id_processo_licitatorio'),
    ('ITEM_LICITACAO_PROCESSO_LICITATORIO', 'item_licitacao', 'id_processo_licitatorio', 'processo_licitatorio', 'id_processo_licitatorio'),
    ('CONTRATO_PROCESSO_LICITATORIO', 'contrato', 'id_processo_licitatorio', 'processo_licitatorio', 'id_processo_licitatorio'),
    ('CONTRATO_CONTRATO', 'contrato', 'id_contrato_superior', 'contrato', 'id_contrato'),
    ('COTACAO_PESSOA', 'cotacao', 'id_pessoa', 'pessoa', 'id_pessoa'),
    ('PESSOA_FISICA_SITUACAO_CADASTRAL', 'pessoa_fisica', 'id_situacao_cadastral', 'situacao_cadastral', 'id_situacao_cadastral'),
    ('ESTABELECIMENTO_SITUACAO_CADASTRAL', 'estabelecimento', 'id_situacao_cadastral', 'situacao_cadastral', 'id_situacao_cadastral'),
    ('ESTABELECIMENTO_PESSOA_JURIDICA', 'estabelecimento', 'id_pessoa_juridica', 'pessoa_juridica', 'id_pessoa'),
]

SAME_ID_RELATIONSHIPS = [
    ('PESSOA_PESSOA_FISICA', 'pessoa', 'id_pessoa', 'pessoa_fisica', 'id_pessoa'),
    ('PESSOA_PESSOA_JURIDICA', 'pessoa', 'id_pessoa', 'pessoa_juridica', 'id_pessoa'),
]

ASSOCIATIVE_RELATIONSHIPS = [
    ('PESSOA_PROCESSO_LICITATORIO', 'processo_licitatorio_pessoa', 'pessoa', 'id_pessoa', 'processo_licitatorio', 'id_processo_licitatorio'),
    ('ITEM_LICITACAO_COTACAO', 'item_cotacao', 'item_licitacao', 'id_item', 'cotacao', 'id_cotacao'),
    ('CONTRATO_COTACAO', 'contrato_cotacao', 'contrato', 'id_contrato', 'cotacao', 'id_cotacao'),
]

INTEGER_COLUMNS = {
    'tipo_pessoa', 'pais_residencia', 'cnae_principal', 'numero_item', 'quantidade', 'qt_item_cotado',
    'classificacao', 'reported_bidders', 'amendment_count', 'catalog_code', 'homologated_quantity',
}
FLOAT_COLUMNS = {
    'valor_previsto', 'valor_garantia', 'valor_contrato', 'valor_unitario_estimado', 'valor_cotado',
    'capital_social', 'risk_score', 'execution_percent', 'price_bank_reference',
}
BOOLEAN_COLUMNS = {'estrangeiro', 'internacional', 'previdencia', 'matriz', 'vencedor', 'sanction_flag'}
DATE_COLUMNS = {
    'data_nascimento', 'data_abertura', 'data_inicio_atividade', 'data_situacao_especial',
    'data_limite_propostas', 'data_aprovacao_acessoria_juridica', 'data_planilha_custos', 'data_homologacao',
    'competencia', 'data_assinatura', 'data_vencimento', 'data_autorizacao_estadual', 'registry_updated_at',
    'publication_date',
}
DATETIME_COLUMNS = {'data_emissao'}


def convert(column, value):
    if column.startswith('id_') or column in INTEGER_COLUMNS:
        return int(value)
    if column in FLOAT_COLUMNS:
        return float(value)
    if column in BOOLEAN_COLUMNS:
        return value == 'True'
    if column in DATE_COLUMNS:
        return date.fromisoformat(value[:10])
    if column in DATETIME_COLUMNS:
        return datetime.fromisoformat(value)
    return value


def build_properties(row):
    source = row['fonte']
    prefix = f'{source.lower()}_'
    properties = {}
    for column, value in row.items():
        if value == '':
            continue
        base_column = column[len(prefix):] if source != MAIN_SOURCE and column.startswith(prefix) else column
        properties[column] = convert(base_column, value)
    properties['codigo_fonte'] = source
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


def read_pair_batches(path, origin_column, target_column):
    with open(path, newline='', encoding='utf-8') as handle:
        batch = []
        for row in csv.DictReader(handle):
            if not row[origin_column] or not row[target_column]:
                continue
            batch.append({'origin': int(row[origin_column]), 'target': int(row[target_column])})
            if len(batch) == RELATIONSHIP_BATCH_SIZE:
                yield batch
                batch = []
        if batch:
            yield batch


def resolve_secondary_entity(stem):
    for entity in SECONDARY_ENTITIES:
        if stem.startswith(f'{entity}_'):
            return entity
    return None


def prepare_schema(session):
    for table, key in NODE_TABLES.items():
        label = LABELS[table]
        session.run(
            f'CREATE CONSTRAINT uniq_{label.lower()} IF NOT EXISTS '
            f'FOR (n:{label}) REQUIRE (n.{key}, n.codigo_fonte) IS UNIQUE').consume()
        session.run(f'CREATE INDEX idx_{label.lower()}_key IF NOT EXISTS FOR (n:{label}) ON (n.{key})').consume()
    session.run('CALL db.awaitIndexes()').consume()
    logger.info('Constraints e índices criados')


def write_nodes(tx, label, rows):
    tx.run(f'UNWIND $rows AS row CREATE (n:{label}) SET n = row', rows=rows).consume()


def load_nodes(session, path, label):
    total = 0
    for batch in read_batches(path):
        session.execute_write(write_nodes, label, batch)
        total += len(batch)
    return total


def write_pairs(tx, query, pairs):
    tx.run(query, pairs=pairs, main=MAIN_SOURCE).consume()


def count_relationships(session, rel_type):
    return session.run(f'MATCH ()-[r:{rel_type}]->() RETURN count(r) AS total').single()['total']


def create_direct_relationships(session, rel_type, from_label, fk_column, to_label, to_pk):
    session.run(f"""
        MATCH (a:{LABELS[from_label]})
        WHERE a.{fk_column} IS NOT NULL
        CALL {{
            WITH a
            MATCH (b:{LABELS[to_label]} {{{to_pk}: a.{fk_column}}})
            CREATE (a)-[:{rel_type}]->(b)
        }} IN TRANSACTIONS OF {RELATIONSHIP_BATCH_SIZE} ROWS
    """).consume()
    logger.info('%s: %s relacionamento(s)', rel_type, count_relationships(session, rel_type))


def create_same_id_relationships(session, rel_type, from_label, from_pk, to_label, to_pk):
    session.run(f"""
        MATCH (a:{LABELS[from_label]} {{codigo_fonte: $main}})
        CALL {{
            WITH a
            MATCH (b:{LABELS[to_label]} {{{to_pk}: a.{from_pk}, codigo_fonte: $main}})
            CREATE (a)-[:{rel_type}]->(b)
        }} IN TRANSACTIONS OF {RELATIONSHIP_BATCH_SIZE} ROWS
    """, main=MAIN_SOURCE).consume()
    logger.info('%s: %s relacionamento(s)', rel_type, count_relationships(session, rel_type))


def create_associative_relationships(session, rel_type, table, from_label, from_pk, to_label, to_pk):
    path = MAIN_DIR / f'{table}.csv'
    if not path.exists():
        logger.warning('Arquivo não encontrado, pulando: %s', path)
        return
    query = f"""
        UNWIND $pairs AS pair
        MATCH (a:{LABELS[from_label]} {{{from_pk}: pair.origin, codigo_fonte: $main}})
        MATCH (b:{LABELS[to_label]} {{{to_pk}: pair.target, codigo_fonte: $main}})
        CREATE (a)-[:{rel_type}]->(b)
    """
    for batch in read_pair_batches(path, from_pk, to_pk):
        session.execute_write(write_pairs, query, batch)
    logger.info('%s: %s relacionamento(s) (via %s)', rel_type, count_relationships(session, rel_type), table)


def main():
    logger.info('Início da inserção no grafo')
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            prepare_schema(session)

            for table in NODE_TABLES:
                path = MAIN_DIR / f'{table}.csv'
                if not path.exists():
                    logger.warning('Arquivo não encontrado, pulando: %s', path)
                    continue
                total = load_nodes(session, path, LABELS[table])
                logger.info('%s nó(s) %s (fonte principal)', total, LABELS[table])

            for path in sorted(OTHER_DIR.glob('*.csv')):
                entity = resolve_secondary_entity(path.stem)
                if entity is None:
                    logger.warning('Arquivo sem entidade conhecida, pulando: %s', path.name)
                    continue
                total = load_nodes(session, path, LABELS[entity])
                logger.info('%s nó(s) %s a partir de %s', total, LABELS[entity], path.name)

            for rel_type, from_label, fk_column, to_label, to_pk in DIRECT_RELATIONSHIPS:
                create_direct_relationships(session, rel_type, from_label, fk_column, to_label, to_pk)

            for rel_type, from_label, from_pk, to_label, to_pk in SAME_ID_RELATIONSHIPS:
                create_same_id_relationships(session, rel_type, from_label, from_pk, to_label, to_pk)

            for rel_type, table, from_label, from_pk, to_label, to_pk in ASSOCIATIVE_RELATIONSHIPS:
                create_associative_relationships(session, rel_type, table, from_label, from_pk, to_label, to_pk)
    except Exception:
        logger.exception('Falha durante a inserção no grafo')
        raise
    finally:
        driver.close()
    logger.info('Inserção no grafo concluída com sucesso')


if __name__ == '__main__':
    main()