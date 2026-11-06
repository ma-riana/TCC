import os
from collections import defaultdict
from neo4j import GraphDatabase
import utils.neo4j_queries as Q

driver = None

def setup(criar_indices=False):
    global driver
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    driver = GraphDatabase.driver(uri, auth=(user, password))

def teardown():
    global driver
    if driver:
        driver.close()

def t1(params, steps):
    with steps.etapa("neo4j"):
        with driver.session() as session:
            res = session.run(Q.T1_NEO4J, 
                edital=params.get("edital"),
                start_date=params.get("data_inicio"),
                end_date=params.get("data_fim"),
                limit=params.get("limite", 100)
            )
            return [record.data() for record in res]

def t2(params, steps):
    with steps.etapa("neo4j"):
        with driver.session() as session:
            res = session.run(Q.T2_NEO4J,
                size=params.get("tamanho", 20),
                last_id=params.get("ultimo_id")
            )
            return [record.data() for record in res]

def t3(params, steps):
    lid = params["id"]
    with steps.etapa("neo4j"):
        with driver.session() as session:
            res = session.run(Q.T3_NEO4J, id=lid)
            return [record.data() for record in res]

def t4(params, steps):
    lid = params["id"]
    with steps.etapa("neo4j"):
        with driver.session() as session:
            res = session.run(Q.T4_NEO4J, id=lid)
            return [record.data() for record in res]

def _executar(query, steps):
    with steps.etapa("neo4j"):
        with driver.session() as session:
            return [record.data() for record in session.run(query)]

def t5(params, steps):
    return _executar(Q.T5_NEO4J, steps)

def t6(params, steps):
    return _executar(Q.T6_NEO4J, steps)

def t7(params, steps):
    return _executar(Q.T7_NEO4J, steps)

def t8(params, steps):
    return _executar(Q.T8_NEO4J, steps)

def t9(params, steps):
    return _executar(Q.T9_NEO4J, steps)

def t10(params, steps):
    return _executar(Q.T10_NEO4J, steps)

TASKS = {
    "t1": t1, "t2": t2, "t3": t3, "t4": t4,
    "t5": t5, "t6": t6, "t7": t7, "t8": t8, "t9": t9, "t10": t10,
}