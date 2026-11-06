import os
from arango import ArangoClient
import utils.arango_queries as Q

client = None
db = None

def setup(criar_indices=False):
    global client, db
    hosts = os.getenv("ARANGO_URL", "http://localhost:8529")
    db_name = os.getenv("ARANGO_DB", "_system")
    user = os.getenv("ARANGO_USER", "root")
    password = os.getenv("ARANGO_PASSWORD", "")
    
    # request_timeout=None: T5/T7/T9 varrem colecoes inteiras e passam do timeout padrao (60s)
    client = ArangoClient(hosts=hosts, request_timeout=None)
    db = client.db(db_name, username=user, password=password)

def teardown():
    global client
    if client:
        client.close()

def t1(params, steps):
    with steps.etapa("arango"):
        cursor = db.aql.execute(Q.T1_ARANGO, bind_vars={
            "edital": params.get("edital"),
            "start_date": params.get("data_inicio"),
            "end_date": params.get("data_fim"),
            "limit": params.get("limite", 100)
        })
        return [doc for doc in cursor]

def t2(params, steps):
    with steps.etapa("arango"):
        cursor = db.aql.execute(Q.T2_ARANGO, bind_vars={
            "size": params.get("tamanho", 20),
            "last_id": params.get("ultimo_id")
        })
        return [doc for doc in cursor]

def t3(params, steps):
    lid = params["id"]
    with steps.etapa("arango"):
        cursor = db.aql.execute(Q.T3_ARANGO, bind_vars={"id": lid})
        res = [doc for doc in cursor]
        return res[0] if res else {}

def t4(params, steps):
    lid = params["id"]
    with steps.etapa("arango"):
        cursor = db.aql.execute(Q.T4_ARANGO, bind_vars={"id": lid})
        res = [doc for doc in cursor]
        return res[0] if res else []

def _executar(query, steps):
    with steps.etapa("arango"):
        cursor = db.aql.execute(query, batch_size=10000)
        return [doc for doc in cursor]

def t5(params, steps):
    return _executar(Q.T5_ARANGO, steps)

def t6(params, steps):
    return _executar(Q.T6_ARANGO, steps)

def t7(params, steps):
    return _executar(Q.T7_ARANGO, steps)

def t8(params, steps):
    return _executar(Q.T8_ARANGO, steps)

def t9(params, steps):
    return _executar(Q.T9_ARANGO, steps)

def t10(params, steps):
    return _executar(Q.T10_ARANGO, steps)

TASKS = {
    "t1": t1, "t2": t2, "t3": t3, "t4": t4,
    "t5": t5, "t6": t6, "t7": t7, "t8": t8, "t9": t9, "t10": t10,
}