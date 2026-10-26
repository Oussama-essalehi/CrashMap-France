"""Export the star schema to ``data/gold/`` as CSV files for Power BI.

Format: UTF-8, comma separator, ``.`` as decimal separator, ISO dates (YYYY-MM-DD), booleans as
``true`` / ``false``, empty field = null. A ``_manifest.json`` lists every file with its row count,
columns and size. Files above ``MAX_TRACKED_MB`` are git-ignored (see .gitignore) and rebuilt with
``python run.py export``.
"""

from __future__ import annotations

import datetime as dt
import json
import logging

import pandas as pd

from crashmap.config import ROOT, get_paths
from crashmap.star_schema import load_star

log = logging.getLogger(__name__)

MAX_TRACKED_MB = 50


def to_gold_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise types for a locale-independent CSV (booleans as true/false, dates as ISO)."""
    out = df.copy()
    for column in out.columns:
        dtype = str(out[column].dtype)
        if dtype.startswith("bool") or dtype == "boolean":
            out[column] = out[column].map({True: "true", False: "false"}).astype("string")
        elif dtype.startswith("datetime"):
            out[column] = out[column].dt.strftime("%Y-%m-%d")
        elif out[column].dtype == object and out[column].map(lambda v: isinstance(v, dt.date)).all():
            out[column] = pd.to_datetime(out[column]).dt.strftime("%Y-%m-%d")
    return out


def main() -> None:
    paths = get_paths()
    tables = load_star()
    manifest = []
    for name, df in tables.items():
        path = paths.gold / f"{name}.csv"
        to_gold_frame(df).to_csv(path, index=False, encoding="utf-8", na_rep="", lineterminator="\n")
        size_mb = path.stat().st_size / 1e6
        manifest.append({"table": name, "file": path.name, "rows": len(df), "columns": list(df.columns),
                         "size_mb": round(size_mb, 2), "tracked_in_git": size_mb <= MAX_TRACKED_MB})
        log.info("%-17s %9d rows  %7.2f MB", name, len(df), size_mb)
    (paths.gold / "_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    big = [m["file"] for m in manifest if not m["tracked_in_git"]]
    if big:
        log.info("Files above %d MB (git-ignored, regenerate with `python run.py export`): %s", MAX_TRACKED_MB, big)
    log.info("Gold export written to %s", paths.gold.relative_to(ROOT))


if __name__ == "__main__":
    from crashmap.config import setup_logging

    setup_logging()
    main()
