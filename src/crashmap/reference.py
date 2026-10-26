"""Reference data: INSEE legal populations, department / region / commune names.

Source: INSEE, "Populations de référence 2023" (en vigueur au 1er janvier 2026), fichier
d'ensemble ``ensemble.zip`` (https://www.insee.fr/fr/statistiques/8680726?sommaire=8681011).
The population used is the "population totale" (PTOT).

Coverage: the 96 metropolitan departments and 4 DROM (971-974). Mayotte (976) is not part of the
2023 legal populations; Saint-Pierre-et-Miquelon (975), Saint-Barthélemy (977) and Saint-Martin
(978) come from ``donnees_collectivites.csv``. Wallis-et-Futuna, French Polynesia and New
Caledonia (986-988) have no INSEE legal population in this file: their per-inhabitant rates are
left empty.
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import pandas as pd

from crashmap import codebook

log = logging.getLogger(__name__)


def _read(zf: zipfile.ZipFile, name: str) -> pd.DataFrame:
    with zf.open(name) as fh:
        return pd.read_csv(fh, sep=";", dtype=str, encoding="utf-8")


def territory_zone(dep: str | None) -> str | None:
    """Territory type for a department code."""
    if dep is None or pd.isna(dep):
        return None
    if dep in codebook.DROM:
        return "Outre-mer (DROM)"
    if dep in codebook.COM:
        return "Outre-mer (COM)"
    return "Métropole"


def load_departments(zip_path: Path) -> pd.DataFrame:
    """One row per department / territory: code, name, region, zone, population."""
    with zipfile.ZipFile(zip_path) as zf:
        deps = _read(zf, "donnees_departements.csv")
        collectivites = _read(zf, "donnees_collectivites.csv")
    deps = deps.rename(columns={"DEP": "dep_code", "Département": "dep_name", "Région": "region_name",
                                "REG": "region_code", "PTOT": "population"})
    deps = deps[["dep_code", "dep_name", "region_code", "region_name", "population"]]
    deps["population"] = deps["population"].astype("Int64")

    col = (
        collectivites.assign(PTOT=collectivites["PTOT"].astype(int))
        .groupby(["COL", "Collectivité"], as_index=False)["PTOT"].sum()
        .rename(columns={"COL": "dep_code", "Collectivité": "dep_name", "PTOT": "population"})
    )
    col["region_code"] = None
    col["region_name"] = "Collectivités d'outre-mer"
    col["population"] = col["population"].astype("Int64")

    extra = [
        {"dep_code": code, "dep_name": name, "region_code": None, "region_name": region, "population": pd.NA}
        for code, (name, region) in codebook.EXTRA_DEPARTMENT_NAMES.items()
        if code not in set(deps["dep_code"]) | set(col["dep_code"])
    ]
    out = pd.concat([deps, col, pd.DataFrame(extra)], ignore_index=True)
    out["population"] = out["population"].astype("Int64")
    out["zone"] = out["dep_code"].map(territory_zone)
    out["population_year"] = 2023
    log.info("Departments: %d (%d with a population)", len(out), out["population"].notna().sum())
    return out.sort_values("dep_code").reset_index(drop=True)


def load_communes(zip_path: Path) -> pd.DataFrame:
    """One row per commune (municipal arrondissements for Paris, Lyon, Marseille): code, name, population."""
    with zipfile.ZipFile(zip_path) as zf:
        communes = _read(zf, "donnees_communes.csv")
        collectivites = _read(zf, "donnees_collectivites.csv")
    communes = communes.rename(columns={"COM": "com_code", "Commune": "com_name", "DEP": "dep_code",
                                        "PTOT": "population"})[["com_code", "com_name", "dep_code", "population"]]
    col = collectivites.rename(columns={"COM": "com_code", "Commune": "com_name", "COL": "dep_code",
                                        "PTOT": "population"})[["com_code", "com_name", "dep_code", "population"]]
    out = pd.concat([communes, col], ignore_index=True).drop_duplicates("com_code")
    out["population"] = out["population"].astype("Int64")
    return out.reset_index(drop=True)
