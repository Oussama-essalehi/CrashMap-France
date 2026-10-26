"""Bring every yearly ONISR file to one schema.

Differences handled (observed on the 2019-2024 files, see docs/methodology.md):

* the accident key is ``Accident_Id`` in caracteristiques-2022 and ``Num_Acc`` elsewhere;
* ``id_usager`` does not exist in usagers-2019 and usagers-2020;
* 2020 files use CRLF line endings, other years LF;
* codes may carry a leading space (``" -1"``);
* ``id_vehicule`` / ``id_usager`` use a non-breaking space (U+00A0) as thousands separator
  (``"138 306 524"``);
* department codes are not zero-padded in 2019 (``"1"`` instead of ``"01"``);
* latitude / longitude use a comma as decimal separator with 7 to 10 decimals depending on the year;
* free-text artefacts in numeric columns (``"#VALEURMULTI"``, ``"#ERREUR"``, ``"(1)"``, ``"N/A"``).

This module only standardizes names, types and formats; business rules live in ``clean.py``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Column renames applied to every file (raw name -> standard name), after lower-casing.
COLUMN_RENAMES = {"accident_id": "num_acc"}

# Target schema per table: column -> kind ("id", "code", "int", "float", "text", "coord")
SCHEMA: dict[str, dict[str, str]] = {
    "caracteristiques": {
        "num_acc": "id", "jour": "int", "mois": "int", "an": "int", "hrmn": "text",
        "lum": "code", "dep": "text", "com": "text", "agg": "code", "int": "code",
        "atm": "code", "col": "code", "adr": "text", "lat": "coord", "long": "coord",
    },
    "lieux": {
        "num_acc": "id", "catr": "code", "voie": "text", "v1": "code", "v2": "text",
        "circ": "code", "nbv": "code", "vosp": "code", "prof": "code", "pr": "code",
        "pr1": "code", "plan": "code", "lartpc": "float", "larrout": "float", "surf": "code",
        "infra": "code", "situ": "code", "vma": "code",
    },
    "vehicules": {
        "num_acc": "id", "id_vehicule": "id", "num_veh": "text", "senc": "code", "catv": "code",
        "obs": "code", "obsm": "code", "choc": "code", "manv": "code", "motor": "code",
        "occutc": "code",
    },
    "usagers": {
        "num_acc": "id", "id_usager": "id", "id_vehicule": "id", "num_veh": "text",
        "place": "code", "catu": "code", "grav": "code", "sexe": "code", "an_nais": "int",
        "trajet": "code", "secu1": "code", "secu2": "code", "secu3": "code", "locp": "code",
        "actp": "text", "etatp": "code",
    },
}
TABLES = tuple(SCHEMA)

NULL_STRINGS = {"", "N/A", "NA", "null", "NULL", ".", "#VALEURMULTI", "#ERREUR", "(1)"}


def read_raw_csv(path: Path) -> pd.DataFrame:
    """Read one raw ONISR CSV as strings (``;`` separator, UTF-8 with a Latin-1 fallback)."""
    for encoding in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(path, sep=";", dtype=str, keep_default_na=False, encoding=encoding)
        except UnicodeDecodeError:
            log.warning("%s is not %s, retrying", path.name, encoding)
    raise ValueError(f"Cannot decode {path}")


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lower-case column names and apply the known renames."""
    df = df.rename(columns=lambda c: c.strip().lower())
    return df.rename(columns=COLUMN_RENAMES)


def clean_text(series: pd.Series) -> pd.Series:
    """Strip whitespace and turn empty / placeholder strings into nulls."""
    s = series.astype("string").str.strip()
    return s.mask(s.isin(NULL_STRINGS))


def parse_id(series: pd.Series) -> pd.Series:
    """Identifiers: keep letters and digits only, which drops the thousands separators (regular or
    non-breaking spaces): ``'138\u00a0306\u00a0524'`` -> ``'138306524'``."""
    return clean_text(series).str.replace(r"[^0-9A-Za-z]", "", regex=True)


def parse_int(series: pd.Series) -> pd.Series:
    """Integer codes as nullable Int64. Non-numeric values (e.g. ``'#ERREUR'``) become null."""
    s = clean_text(series)
    return pd.to_numeric(s, errors="coerce").astype("Int64")


def parse_float(series: pd.Series) -> pd.Series:
    """Decimal numbers written with a comma or a dot."""
    s = clean_text(series).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce").astype("Float64")


def parse_coordinate(series: pd.Series) -> pd.Series:
    """GPS coordinate with a comma decimal separator (``'48,8962100'`` -> ``48.89621``)."""
    return parse_float(series).astype(float)


def normalize_department(series: pd.Series) -> pd.Series:
    """Department code: zero-padded to 2 characters ('1' -> '01'); '2A', '2B', '971'... unchanged."""
    s = clean_text(series).str.upper()
    return s.where(~s.str.fullmatch(r"\d"), s.str.zfill(2))


def normalize_commune(series: pd.Series) -> pd.Series:
    """Commune INSEE code: 5 characters, zero-padded on the left when purely numeric."""
    s = clean_text(series).str.upper()
    return s.where(~s.str.fullmatch(r"\d{4}"), s.str.zfill(5))


def standardize_table(df: pd.DataFrame, table: str, year: int) -> pd.DataFrame:
    """Return ``df`` conforming to ``SCHEMA[table]`` with a ``year`` column."""
    df = standardize_columns(df)
    schema = SCHEMA[table]
    unexpected = sorted(set(df.columns) - set(schema))
    if unexpected:
        log.warning("%s %d: unexpected columns ignored: %s", table, year, unexpected)
    out = pd.DataFrame(index=df.index)
    for column, kind in schema.items():
        if column not in df.columns:
            log.info("%s %d: column '%s' absent, filled with nulls", table, year, column)
            out[column] = pd.Series(pd.NA, index=df.index, dtype="Int64" if kind in ("code", "int") else "string")
            continue
        raw = df[column]
        if kind == "id":
            out[column] = parse_id(raw)
        elif kind in ("code", "int"):
            out[column] = parse_int(raw)
        elif kind == "float":
            out[column] = parse_float(raw)
        elif kind == "coord":
            out[column] = parse_coordinate(raw)
        else:
            out[column] = clean_text(raw)
    if table == "caracteristiques":
        out["dep"] = normalize_department(out["dep"])
        out["com"] = normalize_commune(out["com"])
    if "num_acc" in out:
        out["num_acc"] = pd.to_numeric(out["num_acc"], errors="raise").astype("int64")
    out.insert(0, "year", np.int16(year))
    return out


def load_year(raw_dir: Path, table: str, year: int) -> pd.DataFrame:
    """Read and standardize ``<table>-<year>.csv`` from ``raw_dir``."""
    path = raw_dir / f"{table}-{year}.csv"
    df = standardize_table(read_raw_csv(path), table, year)
    log.info("%s %d: %d rows", table, year, len(df))
    return df


def available_years(raw_dir: Path) -> list[int]:
    """Years for which the 4 files are present in ``raw_dir``."""
    years = set()
    for path in raw_dir.glob("caracteristiques-*.csv"):
        year = int(path.stem.split("-")[1])
        if all((raw_dir / f"{t}-{year}.csv").exists() for t in TABLES):
            years.add(year)
    return sorted(years)


def load_all(raw_dir: Path, years: list[int] | None = None) -> dict[str, pd.DataFrame]:
    """Standardize every table for every year and concatenate them."""
    years = years or available_years(raw_dir)
    if not years:
        raise FileNotFoundError(f"No ONISR files in {raw_dir}; run `python run.py download` first")
    return {
        table: pd.concat([load_year(raw_dir, table, y) for y in years], ignore_index=True)
        for table in TABLES
    }
