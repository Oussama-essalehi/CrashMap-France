"""Cleaning rules and the three analysis grains (accident, vehicle, victim).

Every rule is documented in docs/methodology.md; row counts before/after each rule are written
to ``data/processed/quality_report.json`` and ``docs/cleaning_report.md``.

The double-counting trap: an accident has several vehicles and each vehicle several users, so a
joined accident x vehicle x user table has one row per *user*. Counting accidents or summing
accident attributes on that table inflates the result. This module therefore never exposes the
joined table: it aggregates users and vehicles *up* to the accident grain, and keeps the three
grains in three separate files.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from crashmap import codebook, reference
from crashmap.config import ROOT, get_paths
from crashmap.standardize import load_all

log = logging.getLogger(__name__)

CODE_COLUMNS = {
    "caracteristiques": ["lum", "agg", "int", "atm", "col"],
    "lieux": ["catr", "circ", "vosp", "prof", "plan", "surf", "infra", "situ", "vma", "nbv"],
    "vehicules": ["senc", "catv", "obs", "obsm", "choc", "manv", "motor"],
    "usagers": ["place", "catu", "grav", "sexe", "trajet", "secu1", "secu2", "secu3",
                "locp", "actp", "etatp"],
}
MIN_AGE, MAX_AGE = 0, 110
REPEATED_POINT_THRESHOLD = 5


class QualityReport:
    """Collects row counts and checks; serialised to JSON and Markdown."""

    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []
        self.checks: dict[str, Any] = {}
        self.missing: dict[str, dict[str, float]] = {}

    def step(self, table: str, rule: str, before: int, after: int, affected: int | None = None,
             by_year: dict | None = None) -> None:
        entry = {"table": table, "rule": rule, "rows_before": int(before), "rows_after": int(after),
                 "affected": int(affected if affected is not None else before - after)}
        if by_year:
            entry["by_year"] = {str(k): int(v) for k, v in by_year.items()}
        self.steps.append(entry)
        log.info("[%s] %s: %d -> %d (affected %d)", table, rule, before, after, entry["affected"])

    def to_dict(self) -> dict[str, Any]:
        return {"steps": self.steps, "checks": self.checks, "missing_rates_pct": self.missing}


# --------------------------------------------------------------------------------------------
# Generic rules
# --------------------------------------------------------------------------------------------

def replace_missing_codes(df: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, dict[str, int]]:
    """Rule 4: codes meaning "not filled in" (-1, and 0 where the codebook says so) become null."""
    df = df.copy()
    counts = {}
    for column in columns:
        missing = codebook.MISSING_CODES.get(column, set())
        mask = df[column].isin(list(missing)) if missing else pd.Series(False, index=df.index)
        counts[column] = int(mask.sum())
        df.loc[mask, column] = pd.NA
    return df, counts


def drop_unknown_codes(df: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, dict[str, int]]:
    """Codes absent from the PDF codebook are set to null (they cannot be decoded)."""
    df = df.copy()
    counts = {}
    for column in columns:
        labels = codebook.LABELS.get(column)
        if labels is None:
            continue
        mask = df[column].notna() & ~df[column].isin(list(labels))
        counts[column] = int(mask.sum())
        df.loc[mask, column] = pd.NA
    return df, counts


def decode(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Rule 5: add a ``<column>_label`` column with the French label from the codebook."""
    df = df.copy()
    for column in columns:
        labels = codebook.LABELS.get(column)
        if labels is not None:
            df[f"{column}_label"] = df[column].map(labels).astype("string")
    return df


def parse_hrmn(hrmn: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Rule 6: ``'HH:MM'`` (or ``'HHMM'``) -> hour, minute as nullable integers; invalid -> null."""
    s = hrmn.astype("string").str.strip().str.replace(":", "", regex=False)
    s = s.mask(s == "").str.zfill(4)
    valid = s.str.fullmatch(r"\d{4}").fillna(False)
    hour = pd.to_numeric(s.where(valid).str[:2], errors="coerce").astype("Int64")
    minute = pd.to_numeric(s.where(valid).str[2:], errors="coerce").astype("Int64")
    bad = (hour > 23) | (minute > 59)
    hour = hour.mask(bad.fillna(False))
    minute = minute.mask(bad.fillna(False))
    return hour, minute


def build_date(year: pd.Series, month: pd.Series, day: pd.Series) -> pd.Series:
    """Rule 6: date from the year / month / day columns; impossible dates become NaT."""
    frame = pd.DataFrame({"year": year.astype("Int64"), "month": month.astype("Int64"),
                          "day": day.astype("Int64")})
    return pd.to_datetime(frame, errors="coerce")


def coordinate_box(dep: str | None) -> tuple[float, float, float, float] | None:
    """Bounding box of the territory a department belongs to."""
    if dep is None or pd.isna(dep):
        return None
    return codebook.BOUNDING_BOXES.get(dep, codebook.BOUNDING_BOXES["metropole"])


def validate_coordinates(lat: pd.Series, lon: pd.Series, dep: pd.Series) -> pd.DataFrame:
    """Rule 6: keep coordinates only when inside the bounding box of the accident's territory.

    Returns ``lat``, ``lon`` (null when invalid) and ``coord_status``:
    "valide", "manquante" (no or zero coordinates) or "hors zone" (outside the territory box).
    """
    out = pd.DataFrame({"lat": lat.astype(float), "lon": lon.astype(float)})
    missing = out["lat"].isna() | out["lon"].isna() | ((out["lat"] == 0) & (out["lon"] == 0))
    boxes = dep.map(coordinate_box).dropna()
    bounds = pd.DataFrame(boxes.tolist(), index=boxes.index,
                          columns=["lat_min", "lat_max", "lon_min", "lon_max"]).reindex(out.index)
    inside = (
        out["lat"].between(bounds["lat_min"], bounds["lat_max"])
        & out["lon"].between(bounds["lon_min"], bounds["lon_max"])
    ).fillna(False)
    status = np.where(missing, "manquante", np.where(inside, "valide", "hors zone"))
    out["coord_status"] = pd.Series(status, index=out.index, dtype="string")
    out.loc[out["coord_status"] != "valide", ["lat", "lon"]] = np.nan
    return out


def age_at_accident(year: pd.Series, birth_year: pd.Series) -> pd.Series:
    """Rule 7: age = accident year - birth year; outside [0, 110] -> null."""
    age = year.astype("Int64") - birth_year.astype("Int64")
    return age.where(age.between(MIN_AGE, MAX_AGE)).astype("Int64")


def to_band(values: pd.Series, bands: list[tuple[float, float, str]]) -> pd.Series:
    """Map numeric values to labelled closed intervals ``(low, high, label)``; others -> null."""
    out = pd.Series(pd.NA, index=values.index, dtype="string")
    for low, high, label in bands:
        out[values.between(low, high).fillna(False)] = label
    return out


def age_band(age: pd.Series) -> pd.Series:
    return to_band(age, codebook.AGE_BANDS)


def speed_band(vma: pd.Series) -> pd.Series:
    return to_band(vma, codebook.SPEED_BANDS)


def time_band(hour: pd.Series) -> pd.Series:
    return hour.map(codebook.HOUR_TO_TIME_BAND).astype("string")


# --------------------------------------------------------------------------------------------
# Table-specific rules
# --------------------------------------------------------------------------------------------

def select_main_lieu(lieux: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Rule 2: keep one ``lieux`` row per accident (the main road).

    Since 2023 the file can hold several rows per accident (one per road at an intersection).
    Priority: road category in the hierarchy ``codebook.ROAD_PRIORITY`` (motorway > national >
    departmental > metropolitan > communal > other), then the highest speed limit, then file order.
    Returns the deduplicated table and, per accident, the number of rows it had.
    """
    df = lieux.copy()
    df["_order"] = np.arange(len(df))
    df["_road_rank"] = df["catr"].map(codebook.ROAD_PRIORITY).fillna(99)
    df["_vma"] = df["vma"].fillna(-1)
    n_rows = df.groupby("num_acc").size().rename("lieux_rows")
    df = df.sort_values(["num_acc", "_road_rank", "_vma", "_order"], ascending=[True, True, False, True])
    df = df.drop_duplicates("num_acc", keep="first").drop(columns=["_order", "_road_rank", "_vma"])
    return df.reset_index(drop=True), n_rows


def check_foreign_keys(tables: dict[str, pd.DataFrame], report: QualityReport) -> dict[str, pd.DataFrame]:
    """Rule 2: every lieux / vehicule / usager row must point to a known accident, every usager to
    a known vehicle. Orphans are reported per year and removed."""
    acc = set(tables["caracteristiques"]["num_acc"])
    out = dict(tables)
    for table in ("lieux", "vehicules", "usagers"):
        df = out[table]
        orphan = ~df["num_acc"].isin(acc)
        report.checks[f"orphans_{table}_without_accident"] = int(orphan.sum())
        out[table] = df[~orphan].reset_index(drop=True)
        report.step(table, "remove rows whose accident is unknown", len(df), len(out[table]),
                    by_year=df[orphan].groupby("year").size().to_dict())

    veh_keys = pd.MultiIndex.from_frame(out["vehicules"][["num_acc", "id_vehicule"]])
    users = out["usagers"]
    user_keys = pd.MultiIndex.from_frame(users[["num_acc", "id_vehicule"]])
    no_vehicle = ~user_keys.isin(veh_keys)
    report.checks["users_without_vehicle"] = int(no_vehicle.sum())
    out["usagers"] = users[~no_vehicle].reset_index(drop=True)
    report.step("usagers", "remove users whose vehicle is unknown", len(users), len(out["usagers"]))

    vehicles_without_users = ~veh_keys.isin(user_keys)
    report.checks["vehicles_without_users"] = {
        str(k): int(v) for k, v in out["vehicules"][vehicles_without_users].groupby("year").size().items()
    }
    acc_df = out["caracteristiques"]
    for table in ("lieux", "vehicules", "usagers"):
        missing = ~acc_df["num_acc"].isin(set(out[table]["num_acc"]))
        report.checks[f"accidents_without_{table}"] = int(missing.sum())
    return out


def missing_rates(df: pd.DataFrame, columns: list[str]) -> dict[str, float]:
    """Share of null values (%) for each column."""
    return {c: round(float(df[c].isna().mean() * 100), 2) for c in columns if c in df}


# --------------------------------------------------------------------------------------------
# Grains
# --------------------------------------------------------------------------------------------

def build_vehicles(vehicles: pd.DataFrame) -> pd.DataFrame:
    """Vehicle grain: one row per vehicle with decoded labels and vehicle groups."""
    v = vehicles.copy()
    v["vehicle_key"] = v["num_acc"].astype(str) + "_" + v["id_vehicule"].astype(str)
    v["vehicle_group"] = v["catv"].map(codebook.VEHICLE_GROUP).astype("string")
    v["is_two_wheeler"] = v["catv"].isin(list(codebook.TWO_WHEELERS))
    v["is_motorised_two_wheeler"] = v["catv"].isin(list(codebook.MOTORISED_TWO_WHEELERS))
    v["is_bicycle"] = v["catv"].isin(list(codebook.BICYCLES))
    v["is_personal_mobility"] = v["catv"].isin(list(codebook.PERSONAL_MOBILITY))
    v["is_heavy_vehicle"] = v["catv"].isin(list(codebook.HEAVY_VEHICLES))
    return v.rename(columns={"num_acc": "accident_id"})


def build_victims(users: pd.DataFrame, vehicles: pd.DataFrame) -> pd.DataFrame:
    """Victim grain: one row per person involved (including unhurt users)."""
    u = users.copy()
    u["victim_seq"] = u.groupby("num_acc").cumcount() + 1
    u["victim_id"] = u["num_acc"].astype(str) + "_" + u["victim_seq"].astype(str).str.zfill(3)
    u["vehicle_key"] = u["num_acc"].astype(str) + "_" + u["id_vehicule"].astype(str)
    u["killed"] = u["grav"].eq(codebook.GRAV_KILLED).fillna(False)
    u["hospitalized"] = u["grav"].eq(codebook.GRAV_HOSPITALIZED).fillna(False)
    u["lightly_injured"] = u["grav"].eq(codebook.GRAV_LIGHT).fillna(False)
    u["unhurt"] = u["grav"].eq(codebook.GRAV_UNHURT).fillna(False)
    u["is_victim"] = u["killed"] | u["hospitalized"] | u["lightly_injured"]
    u["killed_or_hospitalized"] = (u["killed"] | u["hospitalized"]).astype("boolean").where(u["grav"].notna())
    u["age"] = age_at_accident(u["year"], u["an_nais"])
    u["age_band"] = age_band(u["age"])

    secu = u[["secu1", "secu2", "secu3"]]
    known = secu.notna() & secu.ne(codebook.SECU_UNDETERMINABLE)
    u["equipment_known"] = known.any(axis=1)
    u["seatbelt_worn"] = secu.eq(codebook.SECU_SEATBELT).any(axis=1).astype("boolean").where(u["equipment_known"])
    u["helmet_worn"] = secu.eq(codebook.SECU_HELMET).any(axis=1).astype("boolean").where(u["equipment_known"])

    veh = vehicles[["vehicle_key", "catv", "vehicle_group"]]
    u = u.merge(veh, on="vehicle_key", how="left", validate="many_to_one")
    pedestrian = u["catu"].eq(3).fillna(False)
    # Travel mode of the person: pedestrians are attached to the vehicle that hit them.
    u["user_mode"] = u["vehicle_group"].where(~pedestrian, "Piéton").astype("string")
    u = u.rename(columns={"num_acc": "accident_id", "catv": "vehicle_catv"})
    return u


def build_accidents(caract: pd.DataFrame, lieux: pd.DataFrame, lieux_rows: pd.Series,
                    vehicles: pd.DataFrame, victims: pd.DataFrame) -> pd.DataFrame:
    """Accident grain: one row per accident, users and vehicles aggregated up (never joined down)."""
    a = caract.merge(lieux.drop(columns=["year"]), on="num_acc", how="left", validate="one_to_one")
    a = a.merge(lieux_rows, left_on="num_acc", right_index=True, how="left")
    a = a.rename(columns={"num_acc": "accident_id", "long": "lon"})

    veh_agg = vehicles.groupby("accident_id").agg(
        n_vehicles=("vehicle_key", "size"),
        two_wheeler_involved=("is_two_wheeler", "any"),
        motorised_two_wheeler_involved=("is_motorised_two_wheeler", "any"),
        bicycle_involved=("is_bicycle", "any"),
        personal_mobility_involved=("is_personal_mobility", "any"),
        heavy_vehicle_involved=("is_heavy_vehicle", "any"),
    )
    vic = victims.assign(
        is_pedestrian=victims["catu"].eq(3).fillna(False),
        grav_unknown=victims["grav"].isna(),
    )
    vic_agg = vic.groupby("accident_id").agg(
        n_users=("victim_id", "size"),
        n_killed=("killed", "sum"),
        n_hospitalized=("hospitalized", "sum"),
        n_lightly_injured=("lightly_injured", "sum"),
        n_unhurt=("unhurt", "sum"),
        n_severity_unknown=("grav_unknown", "sum"),
        n_pedestrians=("is_pedestrian", "sum"),
    )
    a = a.merge(veh_agg, left_on="accident_id", right_index=True, how="left")
    a = a.merge(vic_agg, left_on="accident_id", right_index=True, how="left")
    count_cols = ["n_vehicles", "n_users", "n_killed", "n_hospitalized", "n_lightly_injured",
                  "n_unhurt", "n_severity_unknown", "n_pedestrians"]
    a[count_cols] = a[count_cols].fillna(0).astype("int32")
    flag_cols = ["two_wheeler_involved", "motorised_two_wheeler_involved", "bicycle_involved",
                 "personal_mobility_involved", "heavy_vehicle_involved"]
    a[flag_cols] = a[flag_cols].fillna(False).astype(bool)
    a["pedestrian_involved"] = a["n_pedestrians"] > 0
    a["n_victims"] = a["n_killed"] + a["n_hospitalized"] + a["n_lightly_injured"]
    # Rule 8: severity indicators
    a["fatal"] = a["n_killed"] > 0
    a["serious"] = (a["n_killed"] + a["n_hospitalized"]) > 0
    return a


def add_accident_derived(a: pd.DataFrame, departments: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Rules 6-7: dates, times, coordinates, bands, territory and implausible values."""
    counts: dict[str, int] = {}
    a = a.copy()
    a["date"] = build_date(a["an"], a["mois"], a["jour"])
    counts["invalid_dates"] = int(a["date"].isna().sum())
    counts["year_mismatch"] = int((a["an"] != a["year"]).sum())
    a["month"] = a["date"].dt.month.astype("Int64")
    a["day_of_week"] = a["date"].dt.dayofweek.astype("Int64")  # Monday = 0
    a["weekday"] = a["day_of_week"].map(dict(enumerate(codebook.WEEKDAYS))).astype("string")
    a["is_weekend"] = a["day_of_week"].isin([5, 6])
    a["hour"], a["minute"] = parse_hrmn(a["hrmn"])
    counts["invalid_times"] = int(a["hour"].isna().sum())
    a["time_band"] = time_band(a["hour"])

    coords = validate_coordinates(a["lat"], a["lon"], a["dep"])
    a["lat"], a["lon"], a["coord_status"] = coords["lat"], coords["lon"], coords["coord_status"]
    counts["coord_missing"] = int((a["coord_status"] == "manquante").sum())
    counts["coord_out_of_zone"] = int((a["coord_status"] == "hors zone").sum())
    # Points shared by many accidents are geocoding artefacts (same address / commune centroid).
    point = a["lat"].round(6).astype(str) + "_" + a["lon"].round(6).astype(str)
    point_counts = point.map(point.value_counts())
    a["coord_repeated"] = a["lat"].notna() & (point_counts >= REPEATED_POINT_THRESHOLD)
    counts["coord_repeated"] = int(a["coord_repeated"].sum())
    a["coord_precise"] = (a["coord_status"] == "valide") & ~a["coord_repeated"]

    a["vma_implausible"] = a["vma"].notna() & ~a["vma"].between(10, codebook.MAX_PLAUSIBLE_VMA)
    counts["vma_implausible"] = int(a["vma_implausible"].sum())
    a.loc[a["vma_implausible"], "vma"] = pd.NA
    a["vma_band"] = speed_band(a["vma"])

    a["in_town"] = a["agg"].eq(2).astype("boolean").where(a["agg"].notna())
    a["night"] = a["lum"].isin([3, 4, 5]).astype("boolean").where(a["lum"].notna())
    a["covid_year"] = a["year"].eq(2020)

    deps = departments.set_index("dep_code")
    a = a.rename(columns={"dep": "dep_code", "com": "com_code"})
    a["dep_name"] = a["dep_code"].map(deps["dep_name"]).astype("string")
    a["region_name"] = a["dep_code"].map(deps["region_name"]).astype("string")
    a["zone"] = a["dep_code"].map(reference.territory_zone).astype("string")
    counts["unknown_department"] = int(a["dep_name"].isna().sum())
    return a, counts


ACCIDENT_COLUMNS = [
    "accident_id", "year", "date", "month", "day_of_week", "weekday", "is_weekend", "hrmn", "hour",
    "minute", "time_band", "dep_code", "dep_name", "region_name", "zone", "com_code", "in_town",
    "agg", "agg_label", "lum", "lum_label", "night", "atm", "atm_label", "int", "int_label",
    "col", "col_label", "catr", "catr_label", "vma", "vma_band", "vma_implausible", "plan",
    "plan_label", "surf", "surf_label", "prof", "prof_label", "circ", "circ_label", "vosp",
    "vosp_label", "infra", "infra_label", "situ", "situ_label", "nbv", "lat", "lon",
    "coord_status", "coord_repeated", "coord_precise", "lieux_rows", "n_vehicles", "n_users",
    "n_victims", "n_killed", "n_hospitalized", "n_lightly_injured", "n_unhurt",
    "n_severity_unknown", "n_pedestrians", "pedestrian_involved", "two_wheeler_involved",
    "motorised_two_wheeler_involved", "bicycle_involved", "personal_mobility_involved",
    "heavy_vehicle_involved", "fatal", "serious", "covid_year",
]
VEHICLE_COLUMNS = [
    "vehicle_key", "accident_id", "year", "id_vehicule", "num_veh", "catv", "catv_label",
    "vehicle_group", "is_two_wheeler", "is_motorised_two_wheeler", "is_bicycle",
    "is_personal_mobility", "is_heavy_vehicle", "senc", "senc_label", "obs", "obs_label",
    "obsm", "obsm_label", "choc", "choc_label", "manv", "manv_label", "motor", "motor_label",
    "occutc", "n_users", "n_killed", "n_hospitalized", "n_lightly_injured",
]
VICTIM_COLUMNS = [
    "victim_id", "accident_id", "year", "id_usager", "vehicle_key", "id_vehicule", "num_veh",
    "vehicle_catv", "vehicle_group", "user_mode", "place", "catu", "catu_label", "grav",
    "grav_label", "killed", "hospitalized", "lightly_injured", "unhurt", "is_victim",
    "killed_or_hospitalized", "sexe", "sexe_label", "an_nais", "age", "age_band", "trajet",
    "trajet_label", "secu1", "secu1_label", "secu2", "secu2_label", "secu3", "secu3_label",
    "equipment_known", "seatbelt_worn", "helmet_worn", "locp", "locp_label", "actp",
    "actp_label", "etatp", "etatp_label",
]


def run_cleaning(tables: dict[str, pd.DataFrame], departments: pd.DataFrame,
                 report: QualityReport | None = None) -> dict[str, pd.DataFrame]:
    """Apply every rule to standardized tables and return the three grains."""
    report = report or QualityReport()
    for name, df in tables.items():
        report.step(name, "standardized rows (all years)", len(df), len(df),
                    by_year=df.groupby("year").size().to_dict())

    # Rule 2: keys and grain
    caract = tables["caracteristiques"]
    dup = caract.duplicated("num_acc", keep="first")
    report.checks["caracteristiques_duplicate_num_acc"] = int(dup.sum())
    caract = caract[~dup].reset_index(drop=True)
    report.step("caracteristiques", "drop duplicated Num_Acc", len(dup), len(caract))

    veh = tables["vehicules"]
    dup_v = veh.duplicated(["num_acc", "id_vehicule"], keep="first")
    report.checks["vehicules_duplicate_keys"] = int(dup_v.sum())
    tables = {**tables, "caracteristiques": caract, "vehicules": veh[~dup_v].reset_index(drop=True)}
    tables = check_foreign_keys(tables, report)

    lieux_raw = tables["lieux"]
    multi = lieux_raw.groupby(["year", "num_acc"]).size()
    multi = multi[multi > 1]
    lieux, lieux_rows = select_main_lieu(lieux_raw)
    report.step("lieux", "keep one row per accident (main road)", len(lieux_raw), len(lieux),
                by_year=multi.groupby(level="year").size().to_dict())
    report.checks["accidents_with_several_lieux"] = int(len(multi))

    # Rule 4: missing values; unknown codes
    cleaned = {}
    for name, df in [("caracteristiques", tables["caracteristiques"]), ("lieux", lieux),
                     ("vehicules", tables["vehicules"]), ("usagers", tables["usagers"])]:
        cols = CODE_COLUMNS[name]
        df, missing_counts = replace_missing_codes(df, cols)
        df, unknown_counts = drop_unknown_codes(df, cols)
        report.checks[f"missing_codes_to_null_{name}"] = missing_counts
        report.checks[f"unknown_codes_to_null_{name}"] = {k: v for k, v in unknown_counts.items() if v}
        cleaned[name] = decode(df, cols)  # Rule 5

    vehicles = build_vehicles(cleaned["vehicules"])
    victims = build_victims(cleaned["usagers"], vehicles)
    report.checks["victims_invalid_age"] = int((victims["an_nais"].notna() & victims["age"].isna()).sum())
    per_vehicle = victims.groupby("vehicle_key")[["killed", "hospitalized", "lightly_injured"]].sum()
    per_vehicle["n_users"] = victims.groupby("vehicle_key").size()
    vehicles = vehicles.merge(per_vehicle.rename(columns={"killed": "n_killed", "hospitalized": "n_hospitalized",
                                                          "lightly_injured": "n_lightly_injured"}),
                              left_on="vehicle_key", right_index=True, how="left")
    vehicles[["n_users", "n_killed", "n_hospitalized", "n_lightly_injured"]] = (
        vehicles[["n_users", "n_killed", "n_hospitalized", "n_lightly_injured"]].fillna(0).astype("int32")
    )

    accidents = build_accidents(cleaned["caracteristiques"], cleaned["lieux"], lieux_rows, vehicles, victims)
    accidents, derived_counts = add_accident_derived(accidents, departments)
    report.checks.update(derived_counts)

    accidents = accidents[ACCIDENT_COLUMNS].sort_values("accident_id").reset_index(drop=True)
    vehicles = vehicles[VEHICLE_COLUMNS].sort_values(["accident_id", "vehicle_key"]).reset_index(drop=True)
    victims = victims[VICTIM_COLUMNS].sort_values(["accident_id", "victim_id"]).reset_index(drop=True)

    report.missing["accidents"] = missing_rates(accidents, [
        "date", "hour", "lum", "atm", "int", "col", "catr", "vma", "plan", "surf", "agg", "lat", "dep_name"])
    report.missing["vehicles"] = missing_rates(vehicles, ["catv", "obs", "obsm", "choc", "manv", "motor"])
    report.missing["victims"] = missing_rates(victims, [
        "catu", "grav", "sexe", "age", "trajet", "secu1", "seatbelt_worn", "helmet_worn", "place"])
    for name, df in (("accidents", accidents), ("vehicles", vehicles), ("victims", victims)):
        report.step(name, "final grain", len(df), len(df), by_year=df.groupby("year").size().to_dict())
    return {"accidents": accidents, "vehicles": vehicles, "victims": victims}


def consistency_checks(grains: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Accident counts and death counts must be identical whatever grain they are computed from."""
    a, v, u = grains["accidents"], grains["vehicles"], grains["victims"]
    by_year = {}
    for year in sorted(a["year"].unique()):
        by_year[str(year)] = {
            "accidents_from_accident_grain": int((a["year"] == year).sum()),
            "accidents_from_vehicle_grain": int(v.loc[v["year"] == year, "accident_id"].nunique()),
            "accidents_from_victim_grain": int(u.loc[u["year"] == year, "accident_id"].nunique()),
            "killed_from_accident_grain": int(a.loc[a["year"] == year, "n_killed"].sum()),
            "killed_from_victim_grain": int(u.loc[u["year"] == year, "killed"].sum()),
            "killed_from_vehicle_grain": int(v.loc[v["year"] == year, "n_killed"].sum()),
        }
    joined_rows = len(a.merge(v[["accident_id", "vehicle_key"]], on="accident_id")
                      .merge(u[["vehicle_key"]], on="vehicle_key"))
    return {"by_year": by_year, "naive_join_rows": joined_rows, "accidents": len(a)}


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    """Human-readable version of the quality report (tracked in git)."""
    lines = ["# Cleaning report (generated by `python run.py clean`)", "",
             "Row counts before / after each rule. See docs/methodology.md for the rules.", "",
             "| Table | Rule | Rows before | Rows after | Affected | By year |",
             "|---|---|---:|---:|---:|---|"]
    for s in report["steps"]:
        by_year = ", ".join(f"{k}: {v:,}" for k, v in s.get("by_year", {}).items())
        lines.append(f"| {s['table']} | {s['rule']} | {s['rows_before']:,} | {s['rows_after']:,} | "
                     f"{s['affected']:,} | {by_year} |")
    lines += ["", "## Checks", "", "```json", json.dumps(report["checks"], indent=2, ensure_ascii=False),
              "```", "", "## Missing rates after cleaning (%)", ""]
    for grain, rates in report["missing_rates_pct"].items():
        lines.append(f"**{grain}**: " + ", ".join(f"`{k}` {v}%" for k, v in rates.items()))
        lines.append("")
    lines += ["## Consistency across grains", "",
              "| Year | Accidents (accident grain) | (vehicle grain) | (victim grain) | Killed (accident) "
              "| Killed (victim) | Killed (vehicle) |", "|---|---:|---:|---:|---:|---:|---:|"]
    for year, c in report["consistency"]["by_year"].items():
        lines.append(f"| {year} | {c['accidents_from_accident_grain']:,} | {c['accidents_from_vehicle_grain']:,} | "
                     f"{c['accidents_from_victim_grain']:,} | {c['killed_from_accident_grain']:,} | "
                     f"{c['killed_from_victim_grain']:,} | {c['killed_from_vehicle_grain']:,} |")
    cons = report["consistency"]
    lines += ["", f"A naive accident x vehicle x user join has **{cons['naive_join_rows']:,} rows** for "
              f"**{cons['accidents']:,} accidents**: counting rows there would overstate accidents "
              f"{cons['naive_join_rows'] / cons['accidents']:.2f} times.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Standardize, clean and write the three grains to ``data/processed/``."""
    paths = get_paths()
    tables = load_all(paths.raw_onisr)
    departments = reference.load_departments(paths.raw_insee / "ensemble.zip")
    report = QualityReport()
    grains = run_cleaning(tables, departments, report)

    for name, df in grains.items():
        out = paths.processed / f"{name}.parquet"
        df.to_parquet(out, index=False)
        log.info("Wrote %s (%d rows, %d columns)", out.relative_to(ROOT), len(df), df.shape[1])
    departments.to_parquet(paths.processed / "departments.parquet", index=False)
    reference.load_communes(paths.raw_insee / "ensemble.zip").to_parquet(
        paths.processed / "communes.parquet", index=False)

    full = report.to_dict()
    full["consistency"] = consistency_checks(grains)
    (paths.processed / "quality_report.json").write_text(json.dumps(full, indent=2, ensure_ascii=False),
                                                         encoding="utf-8")
    write_markdown_report(full, ROOT / "docs" / "cleaning_report.md")
    log.info("Quality report written to docs/cleaning_report.md")


if __name__ == "__main__":
    from crashmap.config import setup_logging

    setup_logging()
    main()
