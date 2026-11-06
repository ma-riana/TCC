import os
import csv
import time
import json
import argparse
from datetime import datetime
from contextlib import contextmanager
from dotenv import load_dotenv

import services.run_polyglot_tasks as polyglot
import services.run_graph_tasks as neo4j
import services.run_multimodel_tasks as arango
from services.validate import validate_results

TASK_PARAMS = {
    "t1": {"edital": "ED-12/2026", "data_inicio": None, "data_fim": None, "limite": 10},
    "t2": {"tamanho": 20, "ultimo_id": None},
    "t3": {"id": 6},
    "t4": {"id": 7},
    "t5": {},
    "t6": {},
    "t7": {},
    "t8": {},
    "t9": {},
    "t10": {},
}

CSV_FIELDS = [
    "timestamp", "run", "architecture", "task", "metric",
    "time_ms", "status", "response_size", "error",
]

class MetricsTracker:
    def __init__(self):
        self.metrics = {}

    @contextmanager
    def etapa(self, name):
        start_time = time.perf_counter()
        try:
            yield
        finally:
            self.metrics[name] = (time.perf_counter() - start_time) * 1000

    def registrar(self, key, value):
        self.metrics[key] = value

def save_logs(architecture_name, data, timestamp, run_number):
    clean_name = architecture_name.replace(" ", "_").replace("+", "e").replace("(", "").replace(")", "").lower()
    target_dir = os.path.join("logs", timestamp)
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, f"{clean_name}_run_{run_number}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4, default=str)

def save_metrics_csv(rows, timestamp):
    target_dir = os.path.join("logs", timestamp)
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, "metrics.csv")

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

def execute_tests(name, module, timestamp, csv_rows, run_number):
    architecture_results = {}

    for task, params in TASK_PARAMS.items():
        tracker = MetricsTracker()
        try:
            response = module.TASKS[task](params, tracker)
        except Exception as e:
            print(f"[{name}] [Run {run_number}] {task.upper()} -> ERRO: {e} | Metrics: {tracker.metrics}")
            architecture_results[task] = {"metrics": tracker.metrics, "error": str(e)}
            status, size, error = "error", "", str(e)
        else:
            size = len(response) if isinstance(response, list) else "N/A"
            print(f"[{name}] [Run {run_number}] {task.upper()} -> Rows: {size} | Metrics: {tracker.metrics}")
            architecture_results[task] = {
                "metrics": tracker.metrics,
                "response_size": size,
                "response": response,
            }
            status, error = "ok", ""

        for metric, value in (tracker.metrics or {"": ""}).items():
            csv_rows.append({
                "timestamp": timestamp,
                "run": run_number,
                "architecture": name,
                "task": task,
                "metric": metric,
                "time_ms": value,
                "status": status,
                "response_size": size,
                "error": error,
            })

    save_logs(name, architecture_results, timestamp, run_number)

def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Executar testes das arquiteturas de banco de dados")
    parser.add_argument("--arch", choices=["polyglot", "graph", "multimodel", "all"], default="all")
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args()

    architectures_map = {
        "polyglot": {"name": "Polyglot", "module": polyglot},
        "graph": {"name": "Graph", "module": neo4j},
        "multimodel": {"name": "Multimodel", "module": arango},
    }

    if args.arch == "all":
        selected_archs = architectures_map.values()
    else:
        selected_archs = [architectures_map[args.arch]]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_rows = []

    try:
        for arch in selected_archs:
            print(f"\n=== Iniciando Setup: {arch['name']} ===")
            try:
                arch["module"].setup()
            except TypeError:
                arch["module"].setup(criar_indices=False)

            for run in range(1, args.runs + 1):
                execute_tests(arch["name"], arch["module"], timestamp, csv_rows, run)

            print(f"=== Iniciando Teardown: {arch['name']} ===")
            try:
                arch["module"].teardown()
            except Exception as e:
                print(f"Erro no teardown de {arch['name']}: {e}")

    finally:
        if csv_rows:
            save_metrics_csv(csv_rows, timestamp)

    if args.arch == "all":
        print("\n=== Todas as arquiteturas executadas. Validando resultados... ===")
        validate_results()

if __name__ == "__main__":
    main()