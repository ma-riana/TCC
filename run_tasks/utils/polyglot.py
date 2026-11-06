import os
import time
from concurrent.futures import ThreadPoolExecutor
from neo4j import GraphDatabase
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool


class Polyglot:
    def open_connections(self):
        self.pg = ThreadedConnectionPool(
            1, 5,
            host=os.getenv("PG_HOST", "localhost"),
            port=int(os.getenv("PG_PORT", "5432")),
            user=os.getenv("PG_USER"),
            password=os.getenv("PG_PASSWORD"),
            dbname=os.getenv("PG_DATABASE"),
        )
        self.neo = GraphDatabase.driver(
            os.getenv("NEO4J_POLYGLOT_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_POLYGLOT_USER"), os.getenv("NEO4J_POLYGLOT_PASSWORD")),
        )

    def close_connections(self):
        self.pg.closeall()
        self.neo.close()

    def sql(self, query, params=None):
        conn = self.pg.getconn()
        try:
            with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return [dict(r) for r in cur.fetchall()]
        finally:
            self.pg.putconn(conn)

    def cypher(self, query, **params):
        with self.neo.session() as session:
            result = session.run(query, **params)
            rows = [r.data() for r in result]
            summary = result.consume()
        server_ms = (summary.result_available_after or 0) + (summary.result_consumed_after or 0)
        return rows, server_ms

    def in_parallel(self, fn_pg, fn_neo):
        def time_it(fn):
            start = time.perf_counter()
            result = fn()
            return result, (time.perf_counter() - start) * 1000

        with ThreadPoolExecutor(max_workers=2) as pool:
            task_pg = pool.submit(time_it, fn_pg)
            task_neo = pool.submit(time_it, fn_neo)
            return task_pg.result(), task_neo.result()