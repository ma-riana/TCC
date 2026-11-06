import csv
import logging
import os
from datetime import datetime
from pathlib import Path

from arango import ArangoClient
from dotenv import load_dotenv

load_dotenv()

ARANGO_URL = os.getenv('ARANGO_URL', 'http://localhost:8529')
ARANGO_DB = os.getenv('ARANGO_DB', '_system')
ARANGO_USER = os.getenv('ARANGO_USER', 'root')
ARANGO_PASSWORD = os.getenv('ARANGO_PASSWORD', 'password123')

BASE_DIR = Path(r'C:\Users\maria\OneDrive\Documents\TCC\fake_data\csvs')
MAIN_DIR = BASE_DIR / 'main'
OTHER_DIR = BASE_DIR / 'other_sources'
LOG_DIR = Path(__file__).resolve().parent / 'logs'

MAIN_SOURCE = 'PT'
BATCH_SIZE = 5000


def setup_logger(name):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger(name)
    log.setLevel(logging.INFO)
    handler = logging.FileHandler(LOG_DIR / f'{name}_{datetime.now():%Y%m%d_%H%M%S}.log', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    log.addHandler(handler)
    return log


logger = setup_logger('multimodel_insertion')

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

SECONDARY_ENTITIES = ['pessoa', 'processo_licitatorio', 'contrato', 'item_licitacao']

DIRECT_RELATIONSHIPS = [
    ('ENTE_MUNICIPIO', 'ente', 'id_municipio', 'municipio'),
    ('ESTABELECIMENTO_MUNICIPIO', 'estabelecimento', 'id_municipio', 'municipio'),
    ('UNIDADE_GESTORA_ENTE', 'unidade_gestora', 'id_ente', 'ente'),
    ('PROCESSO_LICITATORIO_MODALIDADE_LICITACAO', 'processo_licitatorio', 'id_modalidade_licitacao', 'modalidade_licitacao'),
    ('PROCESSO_LICITATORIO_UNIDADE_GESTORA', 'processo_licitatorio', 'id_unidade_gestora', 'unidade_gestora'),
    ('DOCUMENTO_PROCESSO_LICITATORIO', 'documento', 'id_processo_licitatorio', 'processo_licitatorio'),
    ('ITEM_LICITACAO_PROCESSO_LICITATORIO', 'item_licitacao', 'id_processo_licitatorio', 'processo_licitatorio'),
    ('CONTRATO_PROCESSO_LICITATORIO', 'contrato', 'id_processo_licitatorio', 'processo_licitatorio'),
    ('CONTRATO_CONTRATO', 'contrato', 'id_contrato_superior', 'contrato'),
    ('COTACAO_PESSOA', 'cotacao', 'id_pessoa', 'pessoa'),
    ('PESSOA_FISICA_SITUACAO_CADASTRAL', 'pessoa_fisica', 'id_situacao_cadastral', 'situacao_cadastral'),
    ('ESTABELECIMENTO_SITUACAO_CADASTRAL', 'estabelecimento', 'id_situacao_cadastral', 'situacao_cadastral'),
    ('ESTABELECIMENTO_PESSOA_JURIDICA', 'estabelecimento', 'id_pessoa_juridica', 'pessoa_juridica'),
]

SPECIALIZATION_RELATIONSHIPS = [
    ('PESSOA_PESSOA_FISICA', 'pessoa', 'pessoa_fisica'),
    ('PESSOA_PESSOA_JURIDICA', 'pessoa', 'pessoa_juridica'),
]

ASSOCIATIVE_RELATIONSHIPS = [
    ('PESSOA_PROCESSO_LICITATORIO', 'processo_licitatorio_pessoa', 'pessoa', 'processo_licitatorio'),
    ('ITEM_LICITACAO_COTACAO', 'item_cotacao', 'item_licitacao', 'cotacao'),
    ('CONTRATO_COTACAO', 'contrato_cotacao', 'contrato', 'cotacao'),
]

RELATIONSHIP_TYPES = (
    [r[0] for r in DIRECT_RELATIONSHIPS]
    + [r[0] for r in SPECIALIZATION_RELATIONSHIPS]
    + [r[0] for r in ASSOCIATIVE_RELATIONSHIPS]
)

INTEGER_COLUMNS = {
    'tipo_pessoa', 'pais_residencia', 'cnae_principal', 'numero_item', 'quantidade', 'qt_item_cotado',
    'classificacao', 'reported_bidders', 'amendment_count', 'catalog_code', 'homologated_quantity',
}
FLOAT_COLUMNS = {
    'valor_previsto', 'valor_garantia', 'valor_contrato', 'valor_unitario_estimado', 'valor_cotado',
    'capital_social', 'risk_score', 'execution_percent', 'price_bank_reference',
}
BOOLEAN_COLUMNS = {'estrangeiro', 'internacional', 'previdencia', 'matriz', 'vencedor', 'sanction_flag'}


class BatchWriter:
    def __init__(self, collection):
        self.collection = collection
        self.buffer = []
        self.count = 0

    def add(self, document):
        self.buffer.append(document)
        if len(self.buffer) >= BATCH_SIZE:
            self.flush()

    def flush(self):
        if not self.buffer:
            return
        for result in self.collection.insert_many(self.buffer):
            if isinstance(result, Exception):
                raise result
        self.count += len(self.buffer)
        self.buffer = []


def convert(column, value):
    if column.startswith('id_') or column in INTEGER_COLUMNS:
        return int(value)
    if column in FLOAT_COLUMNS:
        return float(value)
    if column in BOOLEAN_COLUMNS:
        return value == 'True'
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


def document_key(source, value):
    return str(value) if source == MAIN_SOURCE else f'{source}_{value}'


def table_files(table):
    files = []
    main_path = MAIN_DIR / f'{table}.csv'
    if main_path.exists():
        files.append(main_path)
    if table in SECONDARY_ENTITIES and OTHER_DIR.exists():
        files.extend(sorted(OTHER_DIR.glob(f'{table}_*.csv')))
    return files


def read_rows(path):
    with open(path, newline='', encoding='utf-8') as handle:
        yield from csv.DictReader(handle)


def prepare_collections(db):
    for table, key in NODE_TABLES.items():
        if not db.has_collection(table):
            db.create_collection(table)
        db.collection(table).add_persistent_index(fields=[key, 'codigo_fonte'], unique=True, sparse=False)
    for relationship in RELATIONSHIP_TYPES:
        if not db.has_collection(relationship):
            db.create_collection(relationship, edge=True)
    logger.info('Collections e índices criados')


def load_documents(db):
    for table, key in NODE_TABLES.items():
        for path in table_files(table):
            writer = BatchWriter(db.collection(table))
            for row in read_rows(path):
                properties = build_properties(row)
                properties['_key'] = document_key(row['fonte'], row[key])
                writer.add(properties)
            writer.flush()
            logger.info('%s documento(s) em %s a partir de %s', writer.count, table, path.name)


DIRECT_EDGE_QUERY = """
FOR d IN @@origin
    FILTER d.@fk != null
    FOR t IN @@target
        FILTER t.@pk == d.@fk
        INSERT { _from: d._id, _to: t._id } INTO @@relationship
"""


def load_direct_edges(db):
    # Cada documento de origem (de qualquer fonte) é ligado a todos os documentos
    # de destino com o mesmo identificador, independentemente da fonte.
    for relationship, origin, foreign_key, target in DIRECT_RELATIONSHIPS:
        db.aql.execute(DIRECT_EDGE_QUERY, bind_vars={
            '@origin': origin,
            '@target': target,
            '@relationship': relationship,
            'fk': foreign_key,
            'pk': NODE_TABLES[target],
        })
        logger.info('%s aresta(s) em %s', db.collection(relationship).count(), relationship)


def load_specialization_edges(db):
    for relationship, origin, target in SPECIALIZATION_RELATIONSHIPS:
        key = NODE_TABLES[target]
        writer = BatchWriter(db.collection(relationship))
        for path in table_files(target):
            for row in read_rows(path):
                writer.add({
                    '_from': f"{origin}/{document_key(row['fonte'], row[key])}",
                    '_to': f"{target}/{document_key(row['fonte'], row[key])}",
                })
        writer.flush()
        logger.info('%s aresta(s) em %s', writer.count, relationship)


def load_associative_edges(db):
    for relationship, file_name, origin, target in ASSOCIATIVE_RELATIONSHIPS:
        path = MAIN_DIR / f'{file_name}.csv'
        if not path.exists():
            logger.warning('Arquivo não encontrado, pulando: %s', path)
            continue
        origin_key = NODE_TABLES[origin]
        target_key = NODE_TABLES[target]
        writer = BatchWriter(db.collection(relationship))
        for row in read_rows(path):
            writer.add({'_from': f'{origin}/{row[origin_key]}', '_to': f'{target}/{row[target_key]}'})
        writer.flush()
        logger.info('%s aresta(s) em %s (via %s)', writer.count, relationship, file_name)


def main():
    logger.info('Início da inserção multimodelo')
    try:
        client = ArangoClient(hosts=ARANGO_URL, request_timeout=None)
        db = client.db(ARANGO_DB, username=ARANGO_USER, password=ARANGO_PASSWORD)
        prepare_collections(db)
        load_documents(db)
        load_direct_edges(db)
        load_specialization_edges(db)
        load_associative_edges(db)
    except Exception:
        logger.exception('Falha durante a inserção multimodelo')
        raise
    logger.info('Inserção multimodelo concluída com sucesso')


if __name__ == '__main__':
    main()