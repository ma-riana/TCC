import re
import sys
import json
from collections import Counter
from pathlib import Path

# Chaves que existem só em algumas engines (metadados do Arango, coluna extra do Neo4j)
DROP_KEYS = {"_id", "_key", "_rev", "codigo_fonte"}

# Strings numéricas sem ponto ("231841") só são convertidas para estas chaves,
# para não transformar códigos como "007" em número.
NUMERIC_KEYS = {"diferenca", "capital_social", "risk_score", "execution_percent", "price_bank_reference"}
NUMERIC_STR = re.compile(r"-?\d+(\.\d+)?")


def load_logs(timestamp_dir):
    paths = {
        "polyglot": timestamp_dir / "polyglot.json",
        "graph": timestamp_dir / "graph.json",
        "multimodel": timestamp_dir / "multimodel.json"
    }
    data = {}
    for arch, path in paths.items():
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data[arch] = json.load(f)
    return data


def freeze_value(v):
    if isinstance(v, list):
        return tuple(freeze_value(i) for i in v)
    elif isinstance(v, dict):
        return freeze_dict(v)
    elif isinstance(v, float):
        return round(v, 4)
    return v


def freeze_dict(d):
    if not isinstance(d, dict):
        return freeze_value(d)

    frozen_items = []
    for k, v in d.items():
        if v is None or k in DROP_KEYS:
            continue

        v_f = freeze_value(v)

        if isinstance(v_f, str):
            if len(v_f) >= 19 and v_f[10] in ("T", " ") and v_f[13] == ":":
                v_f = v_f[:19].replace("T", " ")
            elif NUMERIC_STR.fullmatch(v_f) and (
                "." in v_f or k.startswith("valor") or k in NUMERIC_KEYS
            ):
                v_f = round(float(v_f), 4)

        frozen_items.append((k, v_f))
    return frozenset(frozen_items)


def flatten_t3(data):
    """Reduz qualquer formato de resposta do t3 a um conjunto de (entidade, linha).

    Formatos aceitos:
      - dict entidade -> linha | lista de linhas (multimodel, postgres_data)
      - polyglot: {"postgres_data": {...}, "neo4j_data": [...]}
      - lista de {"entity_type": ..., "props": {...}} (query UNION ALL)
      - lista de [entity_type, props] (tupla serializada em JSON)
      - lista de {"result": {...}} (query única do grafo, via record.data())
    """
    pairs = set()
    if not data:
        return pairs

    if isinstance(data, dict):
        if "postgres_data" in data or "neo4j_data" in data:
            pairs |= flatten_t3(data.get("postgres_data"))
            pairs |= flatten_t3(data.get("neo4j_data"))
            return pairs
        for entity, val in data.items():
            if isinstance(val, dict):
                rows = [val]
            elif isinstance(val, list):
                rows = val
            else:
                continue
            for row in rows:
                if row:
                    pairs.add((entity, freeze_dict(row)))
        return pairs

    for rec in data:
        if isinstance(rec, dict) and "entity_type" in rec:
            pairs.add((rec["entity_type"], freeze_dict(rec.get("props", {}))))
        elif isinstance(rec, dict) and "result" in rec:
            pairs |= flatten_t3(rec["result"])
        elif isinstance(rec, (list, tuple)) and len(rec) == 2:
            pairs.add((rec[0], freeze_dict(rec[1])))
    return pairs


def normalize_t4(data, arch):
    if not data:
        return set()
    if arch == "polyglot":
        events = data.get("postgres_events", []) + data.get("neo4j_events", [])
    else:
        events = data
    return set(freeze_dict(e) for e in events)


def normalize_generic(data):
    if not data:
        return set()
    if isinstance(data, dict):
        data = [data]
    return set(freeze_dict(row) for row in data)


def validate_results():
    logs_folder = Path("logs")
    if not logs_folder.exists() or not [p for p in logs_folder.iterdir() if p.is_dir()]:
        print("Pasta 'logs' não encontrada ou vazia.")
        sys.exit(1)

    target_folder = sorted([p for p in logs_folder.iterdir() if p.is_dir()], reverse=True)[0]
    print(f"A validar resultados na pasta: {target_folder.name}...\n")

    data = load_logs(target_folder)
    if "polyglot" not in data:
        print("Gabarito (Polyglot) ausente. Abortar.")
        sys.exit(1)

    tasks = [f"t{i}" for i in range(1, 11)]
    report = {}

    for task in tasks:
        report[task] = {}
        ref_raw = data.get("polyglot", {}).get(task, {}).get("response")

        for arch in ["graph", "multimodel"]:
            if arch not in data:
                continue
            target_raw = data[arch].get(task, {}).get("response")

            if task == "t3":
                ref_set = flatten_t3(ref_raw)
                target_set = flatten_t3(target_raw)
            elif task == "t4":
                ref_set = normalize_t4(ref_raw, "polyglot")
                target_set = normalize_t4(target_raw, arch)
            else:
                ref_set = normalize_generic(ref_raw)
                target_set = normalize_generic(target_raw)

            is_equal = (ref_set == target_set)
            status = "EQUIVALENT" if is_equal else "DIFFERENT"
            report[task][arch] = status
            print(f"{task.upper()} -> {arch.capitalize()}: {status}")

            if not is_equal:
                missing, extra = ref_set - target_set, target_set - ref_set
                if missing:
                    print(f"  - Faltam {len(missing)} itens no {arch.capitalize()}")
                if extra:
                    print(f"  - Sobram {len(extra)} itens no {arch.capitalize()}")
                if task == "t3":
                    if missing:
                        print(f"    faltam por entidade: {dict(Counter(e for e, _ in missing))}")
                    if extra:
                        print(f"    sobram por entidade: {dict(Counter(e for e, _ in extra))}")

    report_path = target_folder / "validation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4)


if __name__ == "__main__":
    validate_results()