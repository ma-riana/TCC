import argparse
import csv
import json
import os
import random
from contextlib import ExitStack
from datetime import date, datetime, timedelta

from faker import Faker

VOLUMES = {'small': 10_000, 'medium': 50_000, 'large': 100_000}
MAIN_SOURCE = 'PT'
SOURCE_NAMES = ['TCE', 'PNCP', 'CGU', 'TCU', 'CGE', 'SIAFI', 'COMPRASNET', 'SIASG', 'OPENDATA', 'BEC']
PEOPLE_PER_PROCESS = 0.5
NON_LOWEST_WINNER_RATE = 0.15
LATE_ACTIVITY_RATE = 0.10

COLUMNS = {
    'modalidade_licitacao': ['id_modalidade_licitacao', 'descricao', 'fonte'],
    'municipio': ['id_municipio', 'nome_municipio', 'sigla_uf', 'nome_uf', 'fonte'],
    'situacao_cadastral': ['id_situacao_cadastral', 'descricao', 'fonte'],
    'ente': ['id_ente', 'id_municipio', 'nome_ente', 'id_tipo_esfera', 'fonte'],
    'unidade_gestora': ['id_unidade_gestora', 'id_ente', 'nome_unidade', 'sigla_unidade', 'cep', 'previdencia', 'fonte'],
    'pessoa': ['id_pessoa', 'nome', 'tipo_pessoa', 'estrangeiro', 'fonte'],
    'pessoa_fisica': ['id_pessoa', 'id_situacao_cadastral', 'cpf', 'pais_residencia', 'faixa_etaria', 'data_nascimento', 'fonte'],
    'pessoa_juridica': ['id_pessoa', 'cnpj', 'razao_social', 'data_abertura', 'capital_social', 'pais_residencia', 'porte_empresa', 'fonte'],
    'estabelecimento': ['id_estabelecimento', 'id_pessoa_juridica', 'id_situacao_cadastral', 'id_municipio', 'matriz', 'nome_fantasia',
                        'data_inicio_atividade', 'cnae_principal', 'endereco', 'cep', 'telefones', 'email', 'situacao_especial',
                        'data_situacao_especial', 'fonte'],
    'processo_licitatorio': ['id_processo_licitatorio', 'id_modalidade_licitacao', 'id_unidade_gestora', 'numero_processo_licitatorio',
                             'numero_edital', 'data_limite_propostas', 'data_aprovacao_acessoria_juridica', 'descricao_objeto',
                             'valor_previsto', 'data_abertura', 'data_planilha_custos', 'data_homologacao', 'valor_garantia',
                             'competencia', 'internacional', 'fonte'],
    'documento': ['id_documento', 'id_processo_licitatorio', 'codigo_documento', 'tipo_documento', 'descricao', 'nome',
                  'data_emissao', 'tamanho', 'acesso_arquivo', 'fonte'],
    'item_licitacao': ['id_item', 'id_processo_licitatorio', 'numero_item', 'descricao', 'quantidade', 'valor_unitario_estimado',
                       'unidade_medida', 'fonte'],
    'contrato': ['id_contrato', 'id_processo_licitatorio', 'id_contrato_superior', 'descricao_objetivo', 'numero_contrato',
                 'data_assinatura', 'data_vencimento', 'valor_contrato', 'valor_garantia', 'competencia',
                 'num_autorizacao_estadual', 'data_autorizacao_estadual', 'fonte'],
    'cotacao': ['id_cotacao', 'id_pessoa', 'numero_item', 'qt_item_cotado', 'valor_cotado', 'vencedor', 'classificacao', 'fonte'],
    'processo_licitatorio_pessoa': ['id_processo_licitatorio', 'id_pessoa'],
    'item_cotacao': ['id_item', 'id_cotacao'],
    'contrato_cotacao': ['id_contrato', 'id_cotacao'],
}

ENTITY_KEYS = {
    'pessoa': 'id_pessoa',
    'processo_licitatorio': 'id_processo_licitatorio',
    'contrato': 'id_contrato',
    'item_licitacao': 'id_item',
}


class CsvTable:
    def __init__(self, stack, folder, name, columns):
        os.makedirs(folder, exist_ok=True)
        handle = stack.enter_context(open(os.path.join(folder, f'{name}.csv'), 'w', newline='', encoding='utf-8'))
        self.writer = csv.writer(handle, lineterminator='\n')
        self.columns = columns
        self.name = name
        self.count = 0
        self.writer.writerow(columns)

    def write(self, row):
        self.writer.writerow([row[column] for column in self.columns])
        self.count += 1


def build_cpf(sequence):
    digits = [int(c) for c in f'{(sequence * 7919 + 123456789) % 10**9:09d}']
    for size in (9, 10):
        total = sum(value * (size + 1 - index) for index, value in enumerate(digits))
        digits.append((total * 10) % 11 % 10)
    text = ''.join(map(str, digits))
    return f'{text[:3]}.{text[3:6]}.{text[6:9]}-{text[9:]}'


CNPJ_WEIGHTS = ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])


def build_cnpj(sequence):
    digits = [int(c) for c in f'{(sequence * 7919 + 12345678) % 10**8:08d}'] + [0, 0, 0, 1]
    for weights in CNPJ_WEIGHTS:
        remainder = sum(value * weight for value, weight in zip(digits, weights)) % 11
        digits.append(0 if remainder < 2 else 11 - remainder)
    text = ''.join(map(str, digits))
    return f'{text[:2]}.{text[2:5]}.{text[5:8]}/{text[8:12]}-{text[12:]}'


def build_pools(fake):
    return {
        'sentences': [fake.sentence(nb_words=6) for _ in range(2000)],
        'phrases': [fake.catch_phrase() for _ in range(1000)],
        'words': [fake.word() for _ in range(500)],
        'urls': [fake.url() for _ in range(500)],
        'addresses': [fake.address().replace('\n', ', ') for _ in range(1000)],
        'phones': [fake.phone_number() for _ in range(1000)],
        'emails': [fake.company_email() for _ in range(1000)],
        'companies': [fake.company() for _ in range(2000)],
    }


def generate_main(folder, num_processes, fake, pools):
    num_people = max(10, int(num_processes * PEOPLE_PER_PROCESS))
    person_docs = []
    today = date.today()
    year_start = date(today.year, 1, 1)

    def random_date():
        return year_start + timedelta(days=random.randint(0, 364))

    def random_code():
        return f'{random.randint(0, 10**8 - 1):08d}'

    with ExitStack() as stack:
        tables = {name: CsvTable(stack, folder, name, columns) for name, columns in COLUMNS.items()}

        for index, description in enumerate(['Pregão Eletrônico', 'Concorrência', 'Tomada de Preços', 'Convite', 'Dispensa'], 1):
            tables['modalidade_licitacao'].write(
                {'id_modalidade_licitacao': index, 'descricao': description, 'fonte': MAIN_SOURCE})

        for index, name in enumerate(['Florianópolis', 'São José', 'Palhoça', 'Joinville', 'Blumenau'], 1):
            tables['municipio'].write({'id_municipio': index, 'nome_municipio': name, 'sigla_uf': 'SC',
                                       'nome_uf': 'Santa Catarina', 'fonte': MAIN_SOURCE})

        for index, description in enumerate(['Ativa', 'Baixada', 'Suspensa'], 1):
            tables['situacao_cadastral'].write(
                {'id_situacao_cadastral': index, 'descricao': description, 'fonte': MAIN_SOURCE})

        for ente_id, municipality_id, name in [(1, 1, 'Prefeitura de Florianópolis'), (2, 4, 'Prefeitura de Joinville')]:
            tables['ente'].write({'id_ente': ente_id, 'id_municipio': municipality_id, 'nome_ente': name,
                                  'id_tipo_esfera': 3, 'fonte': MAIN_SOURCE})

        units = [
            (1, 1, 'Secretaria de Saúde - PMF', 'SMS', False),
            (2, 1, 'Secretaria de Obras - PMF', 'SMO', False),
            (3, 2, 'Fundo de Saúde - PMJ', 'FMS', True),
            (4, 2, 'Secretaria de Educação - PMJ', 'SME', False),
        ]
        for unit_id, ente_id, name, acronym, pension in units:
            tables['unidade_gestora'].write({
                'id_unidade_gestora': unit_id, 'id_ente': ente_id, 'nome_unidade': name, 'sigla_unidade': acronym,
                'cep': fake.postcode(), 'previdencia': pension, 'fonte': MAIN_SOURCE})

        establishment_id = 0
        for person_id in range(1, num_people + 1):
            kind = random.choice([1, 2])
            name = fake.name() if kind == 1 else fake.company()
            tables['pessoa'].write({'id_pessoa': person_id, 'nome': name, 'tipo_pessoa': kind,
                                    'estrangeiro': False, 'fonte': MAIN_SOURCE})
            if kind == 1:
                document = build_cpf(person_id)
                age_days = random.randint(20 * 365, 65 * 365)
                age = age_days // 365
                age_band = '20-30' if age < 30 else '30-40' if age < 40 else '40-50' if age < 50 else '50-65'
                tables['pessoa_fisica'].write({
                    'id_pessoa': person_id, 'id_situacao_cadastral': random.randint(1, 3), 'cpf': document,
                    'pais_residencia': 1058, 'faixa_etaria': age_band,
                    'data_nascimento': today - timedelta(days=age_days), 'fonte': MAIN_SOURCE})
            else:
                document = build_cnpj(person_id)
                tables['pessoa_juridica'].write({
                    'id_pessoa': person_id, 'cnpj': document, 'razao_social': name,
                    'data_abertura': today - timedelta(days=random.randint(365, 3650)),
                    'capital_social': round(random.uniform(10000, 500000), 2), 'pais_residencia': 1058,
                    'porte_empresa': random.choice(['ME', 'EPP', 'DEMAIS']), 'fonte': MAIN_SOURCE})
                establishment_id += 1
                if random.random() < LATE_ACTIVITY_RATE:
                    start_date = year_start + timedelta(days=random.randint(0, 364))
                else:
                    start_date = year_start - timedelta(days=random.randint(1, 3650))
                tables['estabelecimento'].write({
                    'id_estabelecimento': establishment_id, 'id_pessoa_juridica': person_id,
                    'id_situacao_cadastral': random.randint(1, 3), 'id_municipio': random.randint(1, 5),
                    'matriz': True, 'nome_fantasia': random.choice(pools['companies']),
                    'data_inicio_atividade': start_date,
                    'cnae_principal': random.randint(1000000, 9999999), 'endereco': random.choice(pools['addresses']),
                    'cep': f'{random.randint(10000, 99999)}-{random.randint(0, 999):03d}',
                    'telefones': json.dumps([random.choice(pools['phones'])]), 'email': random.choice(pools['emails']),
                    'situacao_especial': None, 'data_situacao_especial': None, 'fonte': MAIN_SOURCE})
            person_docs.append(document)

        document_id = item_id = quotation_id = contract_id = 0
        for process_id in range(1, num_processes + 1):
            opening = random_date()
            planned = round(random.uniform(5000, 1000000), 2)
            tables['processo_licitatorio'].write({
                'id_processo_licitatorio': process_id, 'id_modalidade_licitacao': random.randint(1, 5),
                'id_unidade_gestora': random.randint(1, 4),
                'numero_processo_licitatorio': f'{process_id}/{opening.year}', 'numero_edital': f'ED-{process_id}/{opening.year}',
                'data_limite_propostas': opening + timedelta(days=15),
                'data_aprovacao_acessoria_juridica': opening - timedelta(days=5),
                'descricao_objeto': random.choice(pools['sentences']), 'valor_previsto': planned, 'data_abertura': opening,
                'data_planilha_custos': opening - timedelta(days=10), 'data_homologacao': opening + timedelta(days=30),
                'valor_garantia': round(planned * 0.05, 2), 'competencia': opening.replace(day=1),
                'internacional': False, 'fonte': MAIN_SOURCE})

            participants = random.sample(range(1, num_people + 1), k=random.randint(2, 5))
            for person_id in participants:
                tables['processo_licitatorio_pessoa'].write(
                    {'id_processo_licitatorio': process_id, 'id_pessoa': person_id})

            for doc_number in range(1, random.randint(2, 4)):
                document_id += 1
                tables['documento'].write({
                    'id_documento': document_id, 'id_processo_licitatorio': process_id, 'codigo_documento': random_code(),
                    'tipo_documento': random.choice(['Edital', 'Termo de Referência', 'Ata']),
                    'descricao': random.choice(pools['phrases']), 'nome': f'doc_{process_id}_{doc_number}.pdf',
                    'data_emissao': datetime.combine(random_date(), datetime.min.time()) + timedelta(seconds=random.randint(0, 86399)),
                    'tamanho': f'{random.randint(100, 5000)}KB', 'acesso_arquivo': random.choice(pools['urls']),
                    'fonte': MAIN_SOURCE})

            winners = []
            for item_number in range(1, random.randint(2, 5)):
                item_id += 1
                tables['item_licitacao'].write({
                    'id_item': item_id, 'id_processo_licitatorio': process_id, 'numero_item': item_number,
                    'descricao': random.choice(pools['words']), 'quantidade': random.randint(1, 100),
                    'valor_unitario_estimado': round(random.uniform(10, 5000), 2),
                    'unidade_medida': random.choice(['UN', 'KG', 'L', 'SERVIÇO']), 'fonte': MAIN_SOURCE})

                ranking = random.sample(participants, len(participants))
                prices = sorted(round(random.uniform(10, 4800), 2) for _ in ranking)
                if random.random() < NON_LOWEST_WINNER_RATE:
                    swap_index = random.randint(1, len(prices) - 1)
                    if prices[swap_index] > prices[0]:
                        prices[0], prices[swap_index] = prices[swap_index], prices[0]

                for rank, (person_id, price) in enumerate(zip(ranking, prices), 1):
                    quotation_id += 1
                    tables['cotacao'].write({
                        'id_cotacao': quotation_id, 'id_pessoa': person_id, 'numero_item': item_number,
                        'qt_item_cotado': random.randint(1, 100), 'valor_cotado': price, 'vencedor': rank == 1,
                        'classificacao': rank, 'fonte': MAIN_SOURCE})
                    tables['item_cotacao'].write({'id_item': item_id, 'id_cotacao': quotation_id})
                    if rank == 1:
                        winners.append(quotation_id)

            if random.random() > 0.2:
                contract_id += 1
                tables['contrato'].write({
                    'id_contrato': contract_id, 'id_processo_licitatorio': process_id, 'id_contrato_superior': None,
                    'descricao_objetivo': random.choice(pools['sentences']), 'numero_contrato': f'CT-{process_id}/{opening.year}',
                    'data_assinatura': opening + timedelta(days=35), 'data_vencimento': opening + timedelta(days=400),
                    'valor_contrato': round(planned * random.uniform(0.8, 1.0), 2),
                    'valor_garantia': round(planned * 0.05, 2), 'competencia': opening.replace(day=1),
                    'num_autorizacao_estadual': random_code(), 'data_autorizacao_estadual': opening + timedelta(days=32),
                    'fonte': MAIN_SOURCE})
                for quotation in winners:
                    tables['contrato_cotacao'].write({'id_contrato': contract_id, 'id_cotacao': quotation})

        counts = {
            'pessoa': num_people,
            'processo_licitatorio': num_processes,
            'contrato': contract_id,
            'item_licitacao': item_id,
        }
        row_counts = {name: table.count for name, table in tables.items()}
    return counts, person_docs, row_counts


def mutate_date(max_shift):
    def apply(value):
        if not value:
            return value
        shifted = date.fromisoformat(value[:10]) + timedelta(days=random.choice([-1, 1]) * random.randint(1, max_shift))
        return shifted.isoformat()
    return apply


def mutate_amount(low, high):
    def apply(value):
        if not value:
            return value
        return f'{float(value) * random.uniform(low, high):.2f}'
    return apply


def mutate_integer(spread):
    def apply(value):
        if not value:
            return value
        return str(max(1, int(float(value)) + random.choice([-1, 1]) * random.randint(1, spread)))
    return apply


def mutate_choice(options):
    def apply(value):
        return str(random.choice([option for option in options if str(option) != value]))
    return apply


def mutate_text(value):
    if len(value) < 2:
        return value.upper()
    variant = random.choice(['upper', 'truncate', 'suffix', 'typo'])
    if variant == 'upper':
        return value.upper()
    if variant == 'truncate':
        return value[:max(3, len(value) * 2 // 3)]
    if variant == 'suffix':
        return f"{value} - {random.choice(['REV', 'RETIFICADO', 'ATUALIZADO'])}"
    position = random.randrange(len(value) - 1)
    chars = list(value)
    chars[position], chars[position + 1] = chars[position + 1], chars[position]
    return ''.join(chars)


def mutate_identifier(value):
    if not value:
        return value
    return random.choice([value.replace('-', ''), value.replace('/', '-'), value.split('-', 1)[-1]])


def mutate_document(value):
    digits = ''.join(c for c in value if c.isdigit())
    if random.random() < 0.5:
        return digits
    return digits[:-1] + str((int(digits[-1]) + random.randint(1, 9)) % 10)


def mutate_boolean(value):
    return 'False' if value == 'True' else 'True'


MUTATORS = {
    'pessoa': {
        'nome': mutate_text,
        'documento': mutate_document,
        'estrangeiro': mutate_boolean,
    },
    'processo_licitatorio': {
        'valor_previsto': mutate_amount(0.85, 1.25),
        'data_abertura': mutate_date(10),
        'data_limite_propostas': mutate_date(10),
        'data_homologacao': mutate_date(20),
        'valor_garantia': mutate_amount(0.5, 2.0),
        'descricao_objeto': mutate_text,
        'numero_edital': mutate_identifier,
        'id_modalidade_licitacao': mutate_choice([1, 2, 3, 4, 5]),
    },
    'contrato': {
        'valor_contrato': mutate_amount(0.9, 1.3),
        'valor_garantia': mutate_amount(0.5, 2.0),
        'data_assinatura': mutate_date(15),
        'data_vencimento': mutate_date(60),
        'data_autorizacao_estadual': mutate_date(10),
        'descricao_objetivo': mutate_text,
        'numero_contrato': mutate_identifier,
    },
    'item_licitacao': {
        'descricao': mutate_text,
        'quantidade': mutate_integer(20),
        'valor_unitario_estimado': mutate_amount(0.7, 1.4),
        'unidade_medida': mutate_choice(['UN', 'KG', 'L', 'SERVIÇO', 'CX', 'M']),
    },
}


def recent_date():
    return (date.today() - timedelta(days=random.randint(0, 1000))).isoformat()


def build_extras(pools):
    return {
        'pessoa': {
            'risk_score': lambda: round(random.uniform(0, 100), 2),
            'sanction_flag': lambda: random.choice([True, False]),
            'registry_updated_at': recent_date,
            'compliance_status': lambda: random.choice(['Regular', 'Em análise', 'Inidônea', 'Suspensa']),
        },
        'processo_licitatorio': {
            'audit_status': lambda: random.choice(['Regular', 'Ressalvas', 'Irregular']),
            'portal_url': lambda: random.choice(pools['urls']),
            'publication_date': recent_date,
            'external_protocol': lambda: f'{random.randint(0, 10**8 - 1):08d}',
            'reported_bidders': lambda: random.randint(1, 12),
        },
        'contrato': {
            'audit_note': lambda: random.choice(['Sem apontamentos', 'Aditivo irregular', 'Sobrepreço', 'Prazo excedido']),
            'amendment_count': lambda: random.randint(0, 6),
            'execution_percent': lambda: round(random.uniform(0, 100), 1),
            'portal_url': lambda: random.choice(pools['urls']),
        },
        'item_licitacao': {
            'catalog_code': lambda: random.randint(100000, 999999),
            'brand_reference': lambda: random.choice(pools['words']),
            'price_bank_reference': lambda: round(random.uniform(10, 5000), 2),
            'homologated_quantity': lambda: random.randint(1, 120),
        },
    }


def build_profile(entity, extras):
    fields = list(MUTATORS[entity])
    extra_names = list(extras[entity])
    return {
        'fields': random.sample(fields, random.randint(1, len(fields))),
        'extras': random.sample(extra_names, random.randint(1, len(extra_names))),
        'diverge_probability': random.uniform(0.4, 0.95),
        'extra_probability': random.uniform(0.5, 1.0),
        'null_probability': random.uniform(0.0, 0.08),
    }


def build_secondary_row(entity, row, source, profile, extras):
    result = dict(row)
    result['fonte'] = source
    changed = [field for field in profile['fields'] if random.random() < profile['diverge_probability']]
    if not changed:
        changed = [random.choice(profile['fields'])]
    for field in changed:
        if random.random() < profile['null_probability']:
            result[field] = ''
        else:
            result[field] = MUTATORS[entity][field](row[field])
    prefix = source.lower()
    for name in profile['extras']:
        result[f'{prefix}_{name}'] = extras[entity][name]() if random.random() < profile['extra_probability'] else ''
    return result


def split_volume(total, capacities):
    keys = list(capacities)
    weights = {key: random.uniform(0.2, 1.0) for key in keys}
    allocation = {key: 0 for key in keys}
    remaining = min(total, sum(capacities.values()))
    while remaining > 0:
        active = [key for key in keys if allocation[key] < capacities[key]]
        weight_sum = sum(weights[key] for key in active)
        given = 0
        for key in active:
            share = min(max(1, int(remaining * weights[key] / weight_sum)), capacities[key] - allocation[key], remaining - given)
            allocation[key] += share
            given += share
            if given >= remaining:
                break
        remaining -= given
    return allocation


def generate_secondary(main_dir, other_dir, sources, ratios, counts, person_docs, extras):
    total_objects = sum(counts.values())
    plans = {}
    targets = {}
    with ExitStack() as stack:
        for source, ratio in zip(sources, ratios):
            allocation = split_volume(round(total_objects * ratio), counts)
            targets[source] = allocation
            for entity, amount in allocation.items():
                if not amount:
                    continue
                profile = build_profile(entity, extras)
                base_columns = list(COLUMNS[entity])
                if entity == 'pessoa':
                    base_columns.insert(-1, 'documento')
                columns = base_columns + [f"{source.lower()}_{name}" for name in profile['extras']]
                plans.setdefault(entity, []).append({
                    'source': source,
                    'profile': profile,
                    'selected': set(random.sample(range(1, counts[entity] + 1), amount)),
                    'table': CsvTable(stack, other_dir, f'{entity}_{source.lower()}', columns),
                })

        for entity, entity_plans in plans.items():
            key = ENTITY_KEYS[entity]
            with open(os.path.join(main_dir, f'{entity}.csv'), newline='', encoding='utf-8') as handle:
                for row in csv.DictReader(handle):
                    row_id = int(row[key])
                    if entity == 'pessoa':
                        row['documento'] = person_docs[row_id - 1]
                    for plan in entity_plans:
                        if row_id in plan['selected']:
                            plan['table'].write(build_secondary_row(entity, row, plan['source'], plan['profile'], extras))

        secondary_rows = {plan['table'].name: plan['table'].count for entity_plans in plans.values() for plan in entity_plans}
    return secondary_rows, targets


def resolve_sources(count):
    return [SOURCE_NAMES[index] if index < len(SOURCE_NAMES) else f'SRC{index + 1}' for index in range(count)]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--volume', choices=list(VOLUMES), default='small')
    parser.add_argument('--processes', type=int)
    parser.add_argument('--secondary-sources', type=int, default=3)
    parser.add_argument('--secondary-volume', type=float, nargs='+', default=[0.3])
    parser.add_argument('--output-dir', default='csvs')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    if args.secondary_sources < 0:
        parser.error('--secondary-sources must be >= 0')
    if any(ratio <= 0 or ratio > 1 for ratio in args.secondary_volume):
        parser.error('--secondary-volume values must be in (0, 1]')
    return args


def main():
    args = parse_args()
    random.seed(args.seed)
    Faker.seed(args.seed)
    fake = Faker('pt_BR')
    pools = build_pools(fake)

    num_processes = args.processes or VOLUMES[args.volume]
    main_dir = os.path.join(args.output_dir, 'main')
    other_dir = os.path.join(args.output_dir, 'other_sources')

    counts, person_docs, main_rows = generate_main(main_dir, num_processes, fake, pools)

    sources = resolve_sources(args.secondary_sources)
    ratios = [args.secondary_volume[index % len(args.secondary_volume)] for index in range(len(sources))]
    secondary_rows, targets = generate_secondary(main_dir, other_dir, sources, ratios, counts, person_docs, build_extras(pools))

    log_lines = []
    log_lines.append('=' * 52)
    log_lines.append(' DATA GENERATION SUMMARY '.center(52, '='))
    log_lines.append('=' * 52)
    log_lines.append(f'Processes: {num_processes} | People: {counts["pessoa"]} | Contracts: {counts["contrato"]} | Items: {counts["item_licitacao"]}')
    log_lines.append(f'Main source ({MAIN_SOURCE}):')
    for name, count in main_rows.items():
        log_lines.append(f'  {name.ljust(32)}: {count}')
    log_lines.append(f'  {"TOTAL".ljust(32)}: {sum(main_rows.values())}')
    for source, ratio in zip(sources, ratios):
        log_lines.append(f'Secondary source {source} (ratio {ratio}):')
        for name, count in secondary_rows.items():
            if name.endswith(f'_{source.lower()}'):
                log_lines.append(f'  {name.ljust(32)}: {count}')
        log_lines.append(f'  {"TOTAL".ljust(32)}: {sum(targets[source].values())}')
    log_lines.append('=' * 52)
    log_lines.append(f'Main files: ./{main_dir}')
    log_lines.append(f'Secondary files: ./{other_dir}')

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs('logs', exist_ok=True)
    log_path = os.path.join('logs', f'generation_summary_{timestamp}.txt')
    
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines) + '\n')


if __name__ == '__main__':
    main()