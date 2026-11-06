import json

import utils.polyglot_queries as Q
from utils.polyglot import Polyglot

poli = Polyglot()

def setup(criar_indices=False):
    poli.open_connections()

def teardown():
    poli.close_connections()

def t1(params, steps):
    with steps.etapa("postgres"):
        return poli.sql(Q.T1_POSTGRES, {
            "edital": params.get("edital"),
            "start_date": params.get("data_inicio"),
            "end_date": params.get("data_fim"),
            "limit": params.get("limite", 100),
        })

def t2(params, steps):
    with steps.etapa("postgres"):
        return poli.sql(Q.T2_POSTGRES, {
            "size": params.get("tamanho", 20),
            "last_id": params.get("ultimo_id"),
        })

def t3(params, steps):
    lid = params["id"]

    def _pg_fetch():
        result = poli.sql(Q.T3_POSTGRES, {"id": lid})
        if not result:
            raise LookupError(f"Process {lid} not found in Postgres")
        return result[0]

    def _neo_fetch():
        rows, server_time = poli.cypher(Q.T3_NEO4J, id=lid)
        return [(r["entity_type"], r["props"]) for r in rows], server_time

    with steps.etapa("parallel_query"):
        (pg_data, pg_ms), ((neo_data, neo_server_ms), neo_ms) = poli.in_parallel(_pg_fetch, _neo_fetch)

    steps.registrar("postgres", pg_ms)
    steps.registrar("neo4j", neo_ms)
    steps.registrar("neo4j_server", neo_server_ms)

    return {
        "process_id": lid,
        "postgres_data": pg_data,
        "neo4j_data": neo_data
    }

def t4(params, steps):
    lid = params["id"]

    def _neo_timeline():
        return poli.cypher(Q.T4_NEO4J, id=lid)

    with steps.etapa("parallel_query"):
        (pg_events, pg_ms), ((neo_events, neo_server_ms), neo_ms) = poli.in_parallel(
            lambda: poli.sql(Q.T4_POSTGRES, {"id": lid}),
            _neo_timeline
        )

    steps.registrar("postgres", pg_ms)
    steps.registrar("neo4j", neo_ms)
    steps.registrar("neo4j_server", neo_server_ms)

    return {
        "postgres_events": pg_events,
        "neo4j_events": neo_events
    }

# T5, T8, T10: so Postgres (dependem apenas da fonte principal).
# T6, T7, T9 : Neo4j primeiro (versoes secundarias) -> "ponte" repassa -> Postgres consolida.

def t5(params, steps):
    with steps.etapa("postgres"):
        return poli.sql(Q.T5_POSTGRES)

def t6(params, steps):
    with steps.etapa("neo4j"):
        rows, neo_server_ms = poli.cypher(Q.T6_NEO4J)
    steps.registrar("neo4j_server", neo_server_ms)

    with steps.etapa("ponte"):
        pg_params = {
            "ids": [r["id_processo_licitatorio"] for r in rows],
            "fontes": [r["codigo_fonte"] for r in rows],
            "datas": [r["data_abertura"] for r in rows],
        }

    with steps.etapa("postgres"):
        return poli.sql(Q.T6_POSTGRES, pg_params)

def t7(params, steps):
    with steps.etapa("neo4j"):
        rows, neo_server_ms = poli.cypher(Q.T7_NEO4J)
    steps.registrar("neo4j_server", neo_server_ms)

    with steps.etapa("ponte"):
        pg_params = {"versoes": json.dumps(rows, default=str)}

    with steps.etapa("postgres"):
        return poli.sql(Q.T7_POSTGRES, pg_params)

def t8(params, steps):
    with steps.etapa("postgres"):
        return poli.sql(Q.T8_POSTGRES)

def t9(params, steps):
    with steps.etapa("neo4j"):
        rows, neo_server_ms = poli.cypher(Q.T9_NEO4J)
    steps.registrar("neo4j_server", neo_server_ms)

    with steps.etapa("ponte"):
        pg_params = {"sec": json.dumps(rows, default=str)}

    with steps.etapa("postgres"):
        return poli.sql(Q.T9_POSTGRES, pg_params)

def t10(params, steps):
    with steps.etapa("postgres"):
        return poli.sql(Q.T10_POSTGRES)

TASKS = {
    "t1": t1, "t2": t2, "t3": t3, "t4": t4,
    "t5": t5, "t6": t6, "t7": t7, "t8": t8, "t9": t9, "t10": t10,
}