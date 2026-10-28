"""Validate the Power BI Project without Power BI Desktop.

1. JSON schema validation of every PBIR / PBIP JSON file against the schema declared in its
   ``$schema`` property (published by Microsoft on developer.microsoft.com), and of the report
   theme against the official report theme schema. Schemas are downloaded once into
   ``powerbi/tools/.schema_cache/``.
2. TMDL structural checks (TMDL has no JSON schema): tab indentation, known object keywords and
   properties, every relationship / sortByColumn / DAX reference / report field resolves to an
   existing table, column or measure, Power Query column lists match the gold CSV headers, every
   measure has a description, a format string and a display folder, no DAX variable is named
   after a reserved keyword.

This is not a substitute for opening the project in Power BI Desktop (see BUILD_GUIDE.md), but it
catches schema errors and broken references before that step.

Usage: python powerbi/tools/validate_pbip.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
import urllib.request
from pathlib import Path

from jsonschema import Draft7Validator
from referencing import Registry, Resource

PBI = Path(__file__).resolve().parents[1]
ROOT = PBI.parent
CACHE = Path(__file__).resolve().parent / ".schema_cache"
SM_DEF = PBI / "CrashMapFrance.SemanticModel" / "definition"
REPORT = PBI / "CrashMapFrance.Report"
SCHEMA_HOST = "https://developer.microsoft.com/json-schemas/"

errors: list[str] = []
# DAX keywords that cannot name a variable (CURRENT is refused by Power BI Desktop even if rarely listed)
DAX_RESERVED = {"abs", "asc", "at", "by", "column", "columns", "current", "define", "dense", "desc", "evaluate",
                "false", "in", "measure", "none", "not", "order", "rel", "return", "rows", "skip", "start",
                "table", "true", "var"}


def error(message: str) -> None:
    errors.append(message)


# --------------------------------------------------------------------------------------------
# JSON schemas
# --------------------------------------------------------------------------------------------

def fetch(url: str) -> dict:
    """Download a schema (cached). developer.microsoft.com schemas mirror microsoft/json-schemas."""
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("://", 1)[1])
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as response:
            path.write_bytes(response.read())
    return json.loads(path.read_text(encoding="utf-8"))


def retrieve(uri: str) -> Resource:
    return Resource.from_contents(fetch(uri))


def validate_json_files() -> int:
    registry = Registry(retrieve=retrieve)
    files = sorted(p for p in PBI.rglob("*") if p.is_file() and (p.suffix in {".json", ".pbir", ".pbism", ".pbip"}
                                                                 or p.name == ".platform"))
    files = [p for p in files if ".schema_cache" not in p.parts]
    count = 0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        url = data.get("$schema")
        if not url:
            if path.name != "CrashMapSignalisation.json":
                error(f"{path.relative_to(PBI)}: no $schema")
            continue
        schema = fetch(url)
        validator = Draft7Validator(schema, registry=registry)
        for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
            error(f"{path.relative_to(PBI)}: {'/'.join(map(str, err.path))}: {err.message[:300]}")
        count += 1
    return count


# --------------------------------------------------------------------------------------------
# TMDL
# --------------------------------------------------------------------------------------------

TABLE_PROPS = {"lineageTag", "dataCategory", "isHidden", "description"}
COLUMN_PROPS = {"dataType", "isHidden", "isKey", "formatString", "dataCategory", "lineageTag", "summarizeBy",
                "sourceColumn", "sortByColumn", "isNameInferred", "displayFolder"}
MEASURE_PROPS = {"formatString", "displayFolder", "lineageTag", "isHidden"}
PARTITION_PROPS = {"mode", "source"}
DATA_TYPES = {"string", "int64", "double", "boolean", "dateTime", "decimal"}


def unquote(name: str) -> str:
    name = name.strip()
    return name[1:-1].replace("''", "'") if name.startswith("'") and name.endswith("'") else name


def parse_tables() -> dict[str, dict]:
    """Minimal TMDL reader: tables -> columns (with dataType), measures (with DAX and properties)."""
    tables: dict[str, dict] = {}
    for path in sorted((SM_DEF / "tables").glob("*.tmdl")):
        lines = path.read_text(encoding="utf-8").splitlines()
        table = None
        current = None
        description_pending = False
        in_expression = False
        for number, raw in enumerate(lines, start=1):
            where = f"{path.name}:{number}"
            if not raw.strip():
                continue
            indent = len(raw) - len(raw.lstrip("\t"))
            if raw[indent:indent + 1] == " " and not in_expression:
                error(f"{where}: indentation must use tabs")
            text = raw.strip()
            if text.startswith("///"):
                description_pending = True
                continue
            if indent == 0:
                match = re.fullmatch(r"table (.+)", text)
                if not match:
                    error(f"{where}: expected 'table <name>'")
                    continue
                table = unquote(match.group(1))
                tables[table] = {"columns": {}, "measures": {}, "file": path.name, "partitions": [],
                                 "has_description": description_pending}
                description_pending = False
                continue
            if indent == 1:
                in_expression = False
                head = re.match(r"(column|measure|partition|annotation|lineageTag|dataCategory)\b\s*(.*)", text)
                if not head:
                    error(f"{where}: unknown table-level keyword: {text[:40]}")
                    continue
                kind, rest = head.groups()
                if kind == "column":
                    name = unquote(rest)
                    current = {"kind": "column", "name": name, "props": {}}
                    tables[table]["columns"][name] = current["props"]
                elif kind == "measure":
                    name, _, expr = rest.partition("=")
                    name = unquote(name)
                    current = {"kind": "measure", "name": name, "props": {"description": description_pending},
                               "dax": [expr.strip()] if expr.strip() else []}
                    tables[table]["measures"][name] = current
                    in_expression = not expr.strip()
                elif kind == "partition":
                    current = {"kind": "partition", "name": rest, "props": {}, "source": []}
                    tables[table]["partitions"].append(current)
                else:
                    current = None
                description_pending = False
                continue
            if current is None:
                continue
            if in_expression and current["kind"] == "measure" and indent >= 3:
                current["dax"].append(text)
                continue
            if current["kind"] == "partition" and (indent >= 3 or (in_expression and indent >= 2 and ":" not in text)):
                current["source"].append(raw)
                continue
            if in_expression and indent >= 3:  # body of an extendedProperty JSON value
                continue
            in_expression = False
            if indent == 2:
                key, _, value = text.partition(":")
                key = key.split(" ")[0].strip()
                if key == "annotation":
                    continue
                if key == "extendedProperty":  # followed by a JSON value block
                    in_expression = True
                    continue
                allowed = {"column": COLUMN_PROPS, "measure": MEASURE_PROPS, "partition": PARTITION_PROPS}[current["kind"]]
                if key.startswith("source"):
                    in_expression = True
                    if "=" in text and text.split("=", 1)[1].strip():
                        current["source"].append(text.split("=", 1)[1])
                    continue
                if key not in allowed:
                    error(f"{where}: unknown {current['kind']} property '{key}'")
                current["props"][key] = value.strip()
    return tables


DAX_COLUMN = re.compile(r"('(?:[^']|'')+'|\b[A-Za-z_][A-Za-z0-9_]*)\[([^\]]+)\]")
DAX_MEASURE = re.compile(r"(?<![\]\w'])\[([^\]]+)\]")


def check_model(tables: dict[str, dict]) -> None:
    measures = {name: (table, m) for table, t in tables.items() for name, m in t["measures"].items()}
    for table, t in tables.items():
        if not t["has_description"]:
            error(f"{t['file']}: table '{table}' has no /// description")
        for column, props in t["columns"].items():
            if props.get("dataType") not in DATA_TYPES:
                error(f"{t['file']}: column {table}[{column}] has invalid dataType {props.get('dataType')}")
            sort = props.get("sortByColumn")
            if sort and unquote(sort) not in t["columns"]:
                error(f"{t['file']}: sortByColumn {sort} not found in {table}")
        for name, m in t["measures"].items():
            for prop in ("formatString", "displayFolder"):
                if prop not in m["props"]:
                    error(f"{t['file']}: measure [{name}] has no {prop}")
            if not m["props"].get("description"):
                error(f"{t['file']}: measure [{name}] has no /// description")
            dax = " ".join(m["dax"])
            if not dax:
                error(f"{t['file']}: measure [{name}] has an empty expression")
            for var in re.findall(r"\bVAR\s+(\w+)", dax):
                if var.lower() in DAX_RESERVED:
                    error(f"{t['file']}: measure [{name}] uses the reserved word {var} as a variable name")
            if dax.count("(") != dax.count(")"):
                error(f"{t['file']}: measure [{name}] has unbalanced parentheses")
            for tbl, col in DAX_COLUMN.findall(dax):
                tbl = unquote(tbl)
                if tbl not in tables:
                    error(f"measure [{name}]: unknown table {tbl}")
                elif col not in tables[tbl]["columns"] and col not in tables[tbl]["measures"]:
                    error(f"measure [{name}]: unknown column {tbl}[{col}]")
            stripped = DAX_COLUMN.sub("", dax)
            for ref in DAX_MEASURE.findall(stripped):
                if ref not in measures:
                    error(f"measure [{name}]: unknown measure [{ref}]")
        for partition in t["partitions"]:
            source = "\n".join(partition["source"])
            match = re.search(r'File\.Contents\(Folder & "([^"]+)"\)', source)
            if match:
                csv_path = ROOT / "data" / "gold" / match.group(1)
                if not csv_path.exists():
                    error(f"{t['file']}: {match.group(1)} not found in data/gold (run python run.py export)")
                    continue
                with open(csv_path, encoding="utf-8") as fh:
                    header = next(csv.reader(fh))
                typed = re.findall(r'\{"([^"]+)", (?:type \w+|Int64\.Type)\}', source)
                if typed != header:
                    error(f"{t['file']}: Power Query typed columns differ from {csv_path.name} header")
                expected = set(header) | ({"dep_geo"} if table == "dim_population" else set())
                if set(t["columns"]) != expected:
                    error(f"{t['file']}: TMDL columns differ from CSV columns: "
                          f"{sorted(set(t['columns']) ^ expected)}")

    rel_text = (SM_DEF / "relationships.tmdl").read_text(encoding="utf-8")
    for from_ref, to_ref in re.findall(r"fromColumn: (\S+)\n\ttoColumn: (\S+)", rel_text):
        types = []
        for ref in (from_ref, to_ref):
            table, _, column = ref.partition(".")
            if column not in tables.get(table, {}).get("columns", {}):
                error(f"relationships.tmdl: unknown column {ref}")
            else:
                types.append(tables[table]["columns"][column].get("dataType"))
        if len(types) == 2 and types[0] != types[1]:
            error(f"relationships.tmdl: data types differ for {from_ref} -> {to_ref}: {types}")

    model = (SM_DEF / "model.tmdl").read_text(encoding="utf-8")
    refs = {unquote(r) for r in re.findall(r"^ref table (.+)$", model, flags=re.M)}
    if refs != set(tables):
        error(f"model.tmdl: ref table list differs from table files: {sorted(refs ^ set(tables))}")
    dates = [t for t, v in tables.items() if any("dataCategory: Time" in line for line in
                                                  (SM_DEF / "tables" / v["file"]).read_text(encoding="utf-8").splitlines()[:5])]
    if dates != ["dim_date"]:
        error(f"date table: expected dim_date marked as Time, found {dates}")


def check_report_fields(tables: dict[str, dict]) -> int:
    """Every Column / Measure referenced by a visual must exist in the semantic model."""
    count = 0
    for path in (REPORT / "definition" / "pages").rglob("visual.json"):
        text = path.read_text(encoding="utf-8")
        for kind, entity, prop in re.findall(
                r'"(Column|Measure)": \{\s*"Expression": \{\s*"SourceRef": \{\s*"Entity": "([^"]+)"\s*\}\s*\},\s*"Property": "([^"]+)"',
                text):
            count += 1
            target = tables.get(entity, {}).get("columns" if kind == "Column" else "measures", {})
            if prop not in target:
                error(f"{path.relative_to(PBI)}: unknown {kind.lower()} {entity}[{prop}]")
        for section in re.findall(r'"section": \{\s*"expr": \{\s*"Literal": \{\s*"Value": "\'([^\']+)\'"', text):
            if not (REPORT / "definition" / "pages" / section / "page.json").exists():
                error(f"{path.relative_to(PBI)}: tooltip page {section} not found")
    return count


def main() -> None:
    n_json = validate_json_files()
    theme = json.loads((PBI / "theme.json").read_text(encoding="utf-8"))
    tables = parse_tables()
    check_model(tables)
    n_fields = check_report_fields(tables)
    n_measures = sum(len(t["measures"]) for t in tables.values())
    print(f"JSON files validated against Microsoft schemas: {n_json} (theme: {theme['name']})")
    print(f"TMDL tables: {len(tables)}, columns: {sum(len(t['columns']) for t in tables.values())}, "
          f"measures: {n_measures}; report field references checked: {n_fields}")
    if errors:
        print(f"\n{len(errors)} problem(s):")
        for message in errors:
            print(" -", message)
        sys.exit(1)
    print("No problem found.")


if __name__ == "__main__":
    main()
