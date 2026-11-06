import os
from dotenv import load_dotenv
from arango import ArangoClient

load_dotenv()

db = ArangoClient(hosts=os.getenv("ARANGO_URL", "http://localhost:8529")).db(
    os.getenv("ARANGO_DB", "_system"),
    username=os.getenv("ARANGO_USER", "root"),
    password=os.getenv("ARANGO_PASSWORD", ""),
)

for c in db.collections():
    if not c["system"]:
        db.collection(c["name"]).truncate()
        print("esvaziada:", c["name"])