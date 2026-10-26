"""Star schema built from the three clean grains (shared by the PostgreSQL loader and the gold export).

Facts
    fact_accident  (accident grain)  -> dim_date, dim_time_band, dim_location, dim_population,
                                        dim_conditions, dim_road
    fact_vehicle   (vehicle grain)   -> fact_accident, dim_vehicle_type
    fact_victim    (person grain)    -> fact_accident, dim_user_type, dim_vehicle_type

Vehicle and victim facts reach the calendar and location dimensions through fact_accident, so
every filter on an accident attribute propagates without a second (ambiguous) path.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from crashmap import codebook
from crashmap.config import get_paths, load_config

log = logging.getLogger(__name__)

SEVERITY_ORDER = {codebook.GRAV_KILLED: 1, codebook.GRAV_HOSPITALIZED: 2, codebook.GRAV_LIGHT: 3,
                  codebook.GRAV_UNHURT: 4}
SPEED_BAND_ORDER = {label: i for i, (_, _, label) in enumerate(codebook.SPEED_BANDS, start=1)}
AGE_BAND_ORDER = {label: i for i, (_, _, label) in enumerate(codebook.AGE_BANDS, start=1)}
TIME_BAND_ORDER = {label: i for i, label in enumerate(codebook.TIME_BAND_ORDER, start=1)}


def _junk_dimension(df: pd.DataFrame, columns: list[str], key: str) -> tuple[pd.DataFrame, pd.Series]:
    """Distinct combinations of ``columns`` with a surrogate integer key (nulls included)."""
    combos = df[columns].drop_duplicates().sort_values(columns, na_position="last").reset_index(drop=True)
    combos.insert(0, key, np.arange(1, len(combos) + 1, dtype="int32"))
    keys = df[columns].merge(combos, on=columns, how="left")[key]
    keys.index = df.index
    return combos, keys


def dim_date(first_year: int, last_year: int) -> pd.DataFrame:
    """Contiguous calendar (required by Power BI to mark it as a date table)."""
    dates = pd.date_range(f"{first_year}-01-01", f"{last_year}-12-31", freq="D")
    covid_year = int(load_config()["analysis"]["covid_year"])
    return pd.DataFrame({
        "date_key": dates.strftime("%Y%m%d").astype(int),
        "date": dates.date,
        "year": dates.year,
        "quarter": dates.quarter,
        "month": dates.month,
        "month_name": [codebook.MONTHS[m - 1] for m in dates.month],
        "year_month": dates.strftime("%Y-%m"),
        "day": dates.day,
        "day_of_week": dates.dayofweek + 1,  # 1 = Monday
        "weekday_name": [codebook.WEEKDAYS[d] for d in dates.dayofweek],
        "is_weekend": dates.dayofweek >= 5,
        "is_covid_year": dates.year == covid_year,
    })


def dim_time_band() -> pd.DataFrame:
    hours = np.arange(24)
    bands = [codebook.HOUR_TO_TIME_BAND[h] for h in hours]
    return pd.DataFrame({
        "hour": hours,
        "hour_label": [f"{h:02d}h" for h in hours],
        "time_band": bands,
        "time_band_order": [TIME_BAND_ORDER[b] for b in bands],
    })


def dim_population(departments: pd.DataFrame) -> pd.DataFrame:
    cols = ["dep_code", "dep_name", "region_code", "region_name", "zone", "population", "population_year"]
    return departments[cols].copy()


def dim_location(accidents: pd.DataFrame, departments: pd.DataFrame, communes: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """One row per (commune, in-town) pair seen in the accidents."""
    a = accidents[["com_code", "dep_code", "in_town"]].copy()
    a["in_town"] = a["in_town"].astype("boolean")
    a["location_key"] = a["com_code"].astype(str) + "-" + a["in_town"].map({True: "A", False: "H"}).fillna("X").astype(str)
    dim = a.drop_duplicates("location_key").copy()
    com = communes.set_index("com_code")
    dep = departments.set_index("dep_code")
    dim["com_name"] = dim["com_code"].map(com["com_name"])
    dim["com_population"] = dim["com_code"].map(com["population"]).astype("Int64")
    dim["dep_name"] = dim["dep_code"].map(dep["dep_name"])
    dim["region_name"] = dim["dep_code"].map(dep["region_name"])
    dim["zone"] = dim["dep_code"].map(dep["zone"])
    dim["in_town_label"] = dim["in_town"].map({True: "En agglomération", False: "Hors agglomération"})
    dim = dim[["location_key", "com_code", "com_name", "com_population", "dep_code", "dep_name",
               "region_name", "zone", "in_town", "in_town_label"]].sort_values("location_key")
    return dim.reset_index(drop=True), a["location_key"]


def dim_vehicle_type() -> pd.DataFrame:
    rows = []
    for catv, label in codebook.CATV.items():
        rows.append({
            "catv": catv, "catv_label": label, "vehicle_group": codebook.VEHICLE_GROUP.get(catv),
            "is_two_wheeler": catv in codebook.TWO_WHEELERS,
            "is_motorised_two_wheeler": catv in codebook.MOTORISED_TWO_WHEELERS,
            "is_bicycle": catv in codebook.BICYCLES,
            "is_personal_mobility": catv in codebook.PERSONAL_MOBILITY,
            "is_heavy_vehicle": catv in codebook.HEAVY_VEHICLES,
        })
    return pd.DataFrame(rows)


def build_star(grains: dict[str, pd.DataFrame], departments: pd.DataFrame,
               communes: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return every dimension and fact table as a DataFrame, keyed by table name."""
    a, v, u = grains["accidents"], grains["vehicles"], grains["victims"]

    location, location_keys = dim_location(a, departments, communes)
    conditions, conditions_keys = _junk_dimension(
        a, ["lum", "lum_label", "atm", "atm_label", "surf", "surf_label"], "conditions_key")
    conditions["night"] = conditions["lum"].isin([3, 4, 5]).astype("boolean").where(conditions["lum"].notna())
    road, road_keys = _junk_dimension(
        a, ["catr", "catr_label", "vma_band", "plan", "plan_label", "int", "int_label"], "road_key")
    road.insert(4, "vma_band_order", road["vma_band"].map(SPEED_BAND_ORDER).astype("Int64"))
    road = road.rename(columns={"int": "intersection", "int_label": "intersection_label"})

    fact_accident = pd.DataFrame({
        "accident_id": a["accident_id"],
        "date_key": a["date"].dt.strftime("%Y%m%d").astype(int),
        "hour": a["hour"],
        "location_key": location_keys,
        "dep_code": a["dep_code"],
        "conditions_key": conditions_keys,
        "road_key": road_keys,
        "year": a["year"],
        "in_town": a["in_town"],
        "vma": a["vma"],
        "collision_type": a["col_label"],
        "n_vehicles": a["n_vehicles"],
        "n_users": a["n_users"],
        "n_victims": a["n_victims"],
        "n_killed": a["n_killed"],
        "n_hospitalized": a["n_hospitalized"],
        "n_lightly_injured": a["n_lightly_injured"],
        "n_unhurt": a["n_unhurt"],
        "fatal": a["fatal"],
        "serious": a["serious"],
        "pedestrian_involved": a["pedestrian_involved"],
        "two_wheeler_involved": a["two_wheeler_involved"],
        "motorised_two_wheeler_involved": a["motorised_two_wheeler_involved"],
        "bicycle_involved": a["bicycle_involved"],
        "personal_mobility_involved": a["personal_mobility_involved"],
        "heavy_vehicle_involved": a["heavy_vehicle_involved"],
        "lat": a["lat"].round(6),
        "lon": a["lon"].round(6),
        "coord_precise": a["coord_precise"],
    })

    fact_vehicle = pd.DataFrame({
        "vehicle_key": v["vehicle_key"],
        "accident_id": v["accident_id"],
        "catv": v["catv"],
        "fixed_obstacle": v["obs_label"],
        "mobile_obstacle": v["obsm_label"],
        "impact_point": v["choc_label"],
        "maneuver": v["manv_label"],
        "engine": v["motor_label"],
        "n_users": v["n_users"],
        "n_killed": v["n_killed"],
        "n_hospitalized": v["n_hospitalized"],
        "n_lightly_injured": v["n_lightly_injured"],
    })

    user_types, user_type_keys = _junk_dimension(u, ["catu", "catu_label", "user_mode"], "user_type_key")
    fact_victim = pd.DataFrame({
        "victim_id": u["victim_id"],
        "accident_id": u["accident_id"],
        "vehicle_key": u["vehicle_key"],
        "user_type_key": user_type_keys,
        "catv": u["vehicle_catv"],
        "grav": u["grav"],
        "severity": u["grav_label"],
        "severity_order": u["grav"].map(SEVERITY_ORDER).astype("Int64"),
        "killed": u["killed"].astype("int8"),
        "hospitalized": u["hospitalized"].astype("int8"),
        "lightly_injured": u["lightly_injured"].astype("int8"),
        "unhurt": u["unhurt"].astype("int8"),
        "sex": u["sexe_label"],
        "age": u["age"],
        "age_band": u["age_band"],
        "age_band_order": u["age_band"].map(AGE_BAND_ORDER).astype("Int64"),
        "trip_purpose": u["trajet_label"],
        "equipment_known": u["equipment_known"],
        "seatbelt_worn": u["seatbelt_worn"],
        "helmet_worn": u["helmet_worn"],
    })

    years = sorted(a["year"].unique())
    tables = {
        "dim_date": dim_date(int(years[0]), int(years[-1])),
        "dim_time_band": dim_time_band(),
        "dim_location": location,
        "dim_population": dim_population(departments),
        "dim_conditions": conditions,
        "dim_road": road,
        "dim_user_type": user_types,
        "dim_vehicle_type": dim_vehicle_type(),
        "fact_accident": fact_accident,
        "fact_vehicle": fact_vehicle,
        "fact_victim": fact_victim,
    }
    for name, df in tables.items():
        log.info("%s: %d rows", name, len(df))
    return tables


def load_star() -> dict[str, pd.DataFrame]:
    """Build the star schema from the parquet files in ``data/processed/``."""
    paths = get_paths()
    grains = {name: pd.read_parquet(paths.processed / f"{name}.parquet")
              for name in ("accidents", "vehicles", "victims")}
    departments = pd.read_parquet(paths.processed / "departments.parquet")
    communes = pd.read_parquet(paths.processed / "communes.parquet")
    return build_star(grains, departments, communes)
