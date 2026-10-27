"""Export a compact dataset for the Streamlit web app (``app/data/``).

The web app cannot download and clean 200 MB of raw files at start-up, so this step writes small
Parquet files (categorical columns, zstd compression) that are committed with the app:

* ``accidents.parquet``: one row per accident, the columns the app filters and charts on;
* ``victims.parquet``: one row per person involved, with the accident attributes used as filters
  copied in (year, department, region, in-town), so the app never joins accidents to people;
* ``departments.parquet``: department names, regions and INSEE 2023 population;
* ``departements.geojson``: department outlines (IGN Admin Express via france-geojson, Licence Ouverte);
* ``hotspots_<city>.csv``: DBSCAN hotspots of the focus city (from ``python run.py maps``);
* ``odds_ratios.csv``: logistic regression results (from ``python run.py analyze``).
"""

from __future__ import annotations

import logging
import shutil

import pandas as pd

from crashmap.config import ROOT, get_paths, load_config
from crashmap.maps import slug

log = logging.getLogger(__name__)

WEB_DATA = ROOT / "app" / "data"
MAX_MB = 25

ACCIDENT_COLUMNS = [
    "accident_id", "year", "date", "month", "day_of_week", "hour", "time_band", "dep_code", "dep_name",
    "region_name", "zone", "com_code", "in_town", "lum_label", "night", "atm_label", "surf_label",
    "catr_label", "vma_band", "int_label", "plan_label", "col_label", "n_vehicles", "n_victims",
    "n_killed", "n_hospitalized", "n_lightly_injured", "fatal", "pedestrian_involved",
    "two_wheeler_involved", "motorised_two_wheeler_involved", "bicycle_involved",
    "personal_mobility_involved", "lat", "lon", "coord_precise",
]
VICTIM_COLUMNS = ["accident_id", "user_mode", "catu_label", "grav_label", "killed", "hospitalized",
                  "age_band", "sexe_label", "seatbelt_worn", "helmet_worn", "equipment_known"]
CATEGORICAL_MIN_RATIO = 0.5  # convert text columns with few distinct values to categories


def compact(df: pd.DataFrame) -> pd.DataFrame:
    """Categorical text, small integers, nullable booleans: smaller files and less memory in the app."""
    out = df.copy()
    for column in out.columns:
        series = out[column]
        if pd.api.types.is_string_dtype(series) or series.dtype == object:
            if series.nunique(dropna=True) < len(series) * CATEGORICAL_MIN_RATIO:
                out[column] = series.astype("category")
        elif pd.api.types.is_integer_dtype(series) and column != "accident_id":
            out[column] = pd.to_numeric(series, downcast="integer")
    return out


def main() -> None:
    paths = get_paths()
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    acc = pd.read_parquet(paths.processed / "accidents.parquet", columns=ACCIDENT_COLUMNS)
    # Only precise coordinates are mapped; the others are dropped to keep the file small.
    acc.loc[~acc["coord_precise"], ["lat", "lon"]] = pd.NA
    acc[["lat", "lon"]] = acc[["lat", "lon"]].round(5)
    acc = acc.drop(columns="coord_precise")

    vic = pd.read_parquet(paths.processed / "victims.parquet", columns=VICTIM_COLUMNS)
    context = acc[["accident_id", "year", "dep_code", "region_name", "in_town"]]
    vic = vic.merge(context, on="accident_id", how="left", validate="many_to_one")
    vic = vic[vic["grav_label"].notna()]  # severity unknown: excluded from every victim rate

    deps = pd.read_parquet(paths.processed / "departments.parquet")

    outputs = {
        "accidents.parquet": compact(acc),
        "victims.parquet": compact(vic),
        "departments.parquet": deps,
    }
    for name, df in outputs.items():
        df.to_parquet(WEB_DATA / name, index=False, compression="zstd")
    shutil.copyfile(paths.raw_geo / "departements.geojson", WEB_DATA / "departements.geojson")
    city = slug(load_config()["maps"]["focus_city"]["name"])
    for table in (f"hotspots_{city}.csv", "odds_ratios.csv"):
        source = ROOT / "reports" / "tables" / table
        if source.exists():
            shutil.copyfile(source, WEB_DATA / table)
        else:
            log.warning("%s not found: run `python run.py maps` and `python run.py analyze` first", table)

    total_mb = sum(p.stat().st_size for p in WEB_DATA.iterdir()) / 1e6
    for path in sorted(WEB_DATA.iterdir()):
        log.info("%-28s %6.2f MB", path.name, path.stat().st_size / 1e6)
    if total_mb > MAX_MB:
        raise RuntimeError(f"Web data is {total_mb:.1f} MB (limit {MAX_MB} MB)")
    log.info("Web app data written to %s (%.1f MB)", WEB_DATA.relative_to(ROOT), total_mb)


if __name__ == "__main__":
    from crashmap.config import setup_logging

    setup_logging()
    main()
