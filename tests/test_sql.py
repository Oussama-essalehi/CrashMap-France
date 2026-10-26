"""Static checks on the SQL layer (no database needed)."""

from crashmap.config import ROOT
from crashmap.load_postgres import LOAD_ORDER, split_queries

SQL = ROOT / "sql"


def test_every_analysis_query_is_named_and_covers_all_questions():
    queries = split_queries((SQL / "03_analysis_queries.sql").read_text(encoding="utf-8"))
    names = [name for name, _ in queries]
    assert len(names) == len(set(names))
    assert {n.split(".")[0] for n in names} == {f"Q{i}" for i in range(1, 8)}
    assert all(statement.rstrip().endswith(";") for _, statement in queries)


def test_rates_go_through_safe_rate():
    sql = (SQL / "03_analysis_queries.sql").read_text(encoding="utf-8")
    assert sql.count("safe_rate(") >= 20


def test_schema_declares_every_loaded_table():
    schema = (SQL / "01_schema.sql").read_text(encoding="utf-8")
    for table in LOAD_ORDER:
        assert f"CREATE TABLE {table} (" in schema
