"""Load the star schema into PostgreSQL and run the analysis queries.

Steps: create the schema (sql/01_schema.sql), bulk-load every table with COPY, add indexes
(sql/04_indexes.sql) and views (sql/02_views.sql), then execute each query of
sql/03_analysis_queries.sql, save its result to ``reports/sql_results/`` and cross-check a few
figures against pandas (``docs/sql_python_crosscheck.md``).

Start the database first: ``docker compose up -d`` (credentials in .env, see .env.example).
"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path

import pandas as pd
import psycopg
from sqlalchemy import create_engine, text

from crashmap.config import ROOT, get_paths, min_accidents, postgres_url
from crashmap.star_schema import load_star

log = logging.getLogger(__name__)

SQL_DIR = ROOT / "sql"
RESULTS_DIR = ROOT / "reports" / "sql_results"
LOAD_ORDER = [
    "dim_date", "dim_time_band", "dim_population", "dim_location", "dim_conditions", "dim_road",
    "dim_user_type", "dim_vehicle_type", "fact_accident", "fact_vehicle", "fact_victim",
]
CROSSCHECK = {"departments": ["31", "75"], "years": [2019, 2024]}


def _psycopg_dsn() -> str:
    return postgres_url().replace("postgresql+psycopg://", "postgresql://")


def run_sql_file(conn: psycopg.Connection, path: Path) -> None:
    """Execute a whole SQL file (several statements) in one round trip."""
    log.info("Executing %s", path.name)
    conn.execute(path.read_text(encoding="utf-8"))


def copy_dataframe(conn: psycopg.Connection, table: str, df: pd.DataFrame) -> None:
    """Bulk insert with COPY ... FROM STDIN (CSV, empty string = NULL)."""
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False, na_rep="")
    columns = ", ".join(df.columns)
    with conn.cursor().copy(f"COPY crashmap.{table} ({columns}) FROM STDIN WITH (FORMAT csv, NULL '')") as copy:
        copy.write(buffer.getvalue())
    log.info("Loaded %-17s %9d rows", table, len(df))


def split_queries(sql: str) -> list[tuple[str, str]]:
    """Split sql/03 into (name, statement) pairs; the name is the closest '-- Qx.y' comment."""
    queries = []
    name = None
    current: list[str] = []
    for line in sql.splitlines():
        match = re.match(r"--\s*(Q\d+(?:\.[a-z])?)\b", line)
        if match:
            name = match.group(1)
        current.append(line)
        if line.rstrip().endswith(";"):
            statement = "\n".join(current).strip()
            current = []
            body = "\n".join(l for l in statement.splitlines() if not l.strip().startswith("--")).strip()
            if body.upper().startswith("SET "):
                continue
            queries.append((name or f"query_{len(queries) + 1}", statement))
    return queries


def run_analysis_queries(engine) -> dict[str, pd.DataFrame]:
    """Run every analysis query, save the results as CSV and return them."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    with engine.connect() as conn:
        conn.execute(text("SET search_path TO crashmap"))
        for name, statement in split_queries((SQL_DIR / "03_analysis_queries.sql").read_text(encoding="utf-8")):
            df = pd.read_sql_query(text(statement), conn)
            df.to_csv(RESULTS_DIR / f"{name.replace('.', '_')}.csv", index=False)
            results[name] = df
            log.info("%s: %d rows", name, len(df))
    return results


def crosscheck(engine) -> pd.DataFrame:
    """Compare accidents, deaths and death rate between SQL and pandas for 2 departments x 2 years."""
    paths = get_paths()
    acc = pd.read_parquet(paths.processed / "accidents.parquet",
                          columns=["accident_id", "year", "dep_code", "n_killed"])
    rows = []
    with engine.connect() as conn:
        for dep in CROSSCHECK["departments"]:
            for year in CROSSCHECK["years"]:
                sql = conn.execute(text(
                    "SELECT n_accidents, n_killed, killed_per_100_accidents "
                    "FROM crashmap.v_department_year WHERE dep_code = :dep AND year = :year"),
                    {"dep": dep, "year": year}).one()
                sub = acc[(acc["dep_code"] == dep) & (acc["year"] == year)]
                py_rate = round(sub["n_killed"].sum() * 100 / len(sub), 2) if len(sub) >= min_accidents() else None
                rows.append({
                    "dep_code": dep, "year": year,
                    "accidents_sql": sql.n_accidents, "accidents_python": len(sub),
                    "killed_sql": sql.n_killed, "killed_python": int(sub["n_killed"].sum()),
                    "rate_sql": float(sql.killed_per_100_accidents) if sql.killed_per_100_accidents is not None else None,
                    "rate_python": py_rate,
                })
    df = pd.DataFrame(rows)
    df["match"] = ((df["accidents_sql"] == df["accidents_python"]) & (df["killed_sql"] == df["killed_python"])
                   & (df["rate_sql"] == df["rate_python"]))
    lines = ["# Cross-check SQL vs Python", "",
             "Generated by `python run.py load`: the same indicators computed in PostgreSQL "
             "(`crashmap.v_department_year`) and in pandas (`data/processed/accidents.parquet`).", "",
             "| Department | Year | Accidents SQL | Accidents Python | Killed SQL | Killed Python | "
             "Killed / 100 acc. SQL | Killed / 100 acc. Python | Match |",
             "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in df.itertuples():
        lines.append(f"| {r.dep_code} | {r.year} | {r.accidents_sql:,} | {r.accidents_python:,} | {r.killed_sql} | "
                     f"{r.killed_python} | {r.rate_sql} | {r.rate_python} | {'yes' if r.match else 'NO'} |")
    (ROOT / "docs" / "sql_python_crosscheck.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not df["match"].all():
        raise AssertionError(f"SQL and Python disagree:\n{df}")
    log.info("SQL / Python cross-check OK (%d comparisons)", len(df))
    return df


def main() -> None:
    tables = load_star()
    with psycopg.connect(_psycopg_dsn(), autocommit=False) as conn:
        run_sql_file(conn, SQL_DIR / "01_schema.sql")
        conn.execute("INSERT INTO crashmap.analysis_params VALUES ('min_accidents', %s)", (min_accidents(),))
        for table in LOAD_ORDER:
            copy_dataframe(conn, table, tables[table])
        run_sql_file(conn, SQL_DIR / "02_views.sql")
        conn.commit()
    with psycopg.connect(_psycopg_dsn(), autocommit=True) as conn:
        run_sql_file(conn, SQL_DIR / "04_indexes.sql")

    engine = create_engine(postgres_url())
    run_analysis_queries(engine)
    crosscheck(engine)


if __name__ == "__main__":
    from crashmap.config import setup_logging

    setup_logging()
    main()
