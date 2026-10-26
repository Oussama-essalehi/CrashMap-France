"""Download the raw data into ``data/raw/``.

* ONISR annual files (caracteristiques, lieux, vehicules, usagers) for every year from
  ``data.first_year`` to the latest year available, plus the official description PDF.
  Resource URLs are never hardcoded: they are resolved through the data.gouv.fr API, because
  file titles change from year to year (``caract-2023.csv``, ``carcteristiques-2022.csv``,
  ``Caract_2024.csv``...).
* INSEE legal populations (fichier d'ensemble, communes / departments / regions).
* GeoJSON of French departments for the choropleth map.

A ``manifest.json`` records the URL, size, SHA-256 and resource id of every file.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from crashmap.config import get_paths, load_config

log = logging.getLogger(__name__)

TABLES = ("caracteristiques", "lieux", "vehicules", "usagers")
# Title prefixes seen on data.gouv.fr for each table (lower case, accents removed by the API).
TITLE_PATTERNS = {
    "caracteristiques": re.compile(r"^(caract|carct|carac)"),
    "lieux": re.compile(r"^lieux"),
    "vehicules": re.compile(r"^vehicules"),
    "usagers": re.compile(r"^usagers"),
}
DESCRIPTION_PDF = re.compile(r"^description-des-bases-de-donnees-annuelles")
YEAR = re.compile(r"(?<!\d)(20\d{2})(?!\d)")

MAX_ATTEMPTS = 6
TIMEOUT = 120


@dataclass
class Resource:
    """One file to download."""

    kind: str
    year: int | None
    title: str
    url: str
    filename: str
    expected_size: int | None = None
    resource_id: str | None = None
    last_modified: str | None = None


def _session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = "crashmap-france/1.0 (open data portfolio project)"
    return session


def _get_with_retry(session: requests.Session, url: str, **kwargs) -> requests.Response:
    """GET with exponential backoff on network errors and 5xx responses."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = session.get(url, timeout=TIMEOUT, **kwargs)
            if response.status_code < 500:
                response.raise_for_status()
                return response
            log.warning("HTTP %s on %s (attempt %d)", response.status_code, url, attempt)
        except (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError) as exc:
            log.warning("Network error on %s (attempt %d): %s", url, attempt, exc)
        time.sleep(min(2**attempt, 30))
    raise RuntimeError(f"Could not download {url} after {MAX_ATTEMPTS} attempts")


def resolve_onisr_resources(session: requests.Session) -> list[Resource]:
    """List the ONISR files to download, from the data.gouv.fr dataset API."""
    cfg = load_config()["data"]
    api_url = cfg["api_url"].format(dataset_id=cfg["dataset_id"])
    dataset = _get_with_retry(session, api_url).json()
    log.info("Dataset: %s (last modified %s)", dataset["title"], dataset["last_modified"])

    found: dict[tuple[str, int], dict] = {}
    pdf: dict | None = None
    for res in dataset["resources"]:
        title = res["title"].strip().lower()
        if DESCRIPTION_PDF.match(title):
            pdf = res
            continue
        if "immatricul" in title:  # separate dataset of registered vehicles, out of scope
            continue
        match = YEAR.search(title)
        if not match:
            continue
        year = int(match.group(1))
        for table, pattern in TITLE_PATTERNS.items():
            if pattern.match(title):
                key = (table, year)
                # Keep the most recently modified resource if a year/table appears twice.
                if key not in found or res["last_modified"] > found[key]["last_modified"]:
                    found[key] = res

    first_year = int(cfg["first_year"])
    complete_years = sorted(
        {year for (_, year) in found if all((t, year) in found for t in TABLES) and year >= first_year}
    )
    if not complete_years:
        raise RuntimeError("No complete year found on data.gouv.fr")
    last_year = complete_years[-1] if cfg["last_year"] == "latest" else int(cfg["last_year"])
    years = [y for y in complete_years if y <= last_year]
    missing = sorted(set(range(first_year, last_year + 1)) - set(years))
    if missing:
        raise RuntimeError(f"Years with incomplete files on data.gouv.fr: {missing}")
    log.info("Years to download: %s", years)

    resources = [
        Resource(
            kind=table,
            year=year,
            title=found[(table, year)]["title"],
            url=found[(table, year)]["url"],
            filename=f"{table}-{year}.csv",
            expected_size=found[(table, year)].get("filesize"),
            resource_id=found[(table, year)]["id"],
            last_modified=found[(table, year)]["last_modified"],
        )
        for year in years
        for table in TABLES
    ]
    if pdf is None:
        raise RuntimeError("Description PDF not found in the dataset resources")
    resources.append(
        Resource(
            kind="description_pdf",
            year=None,
            title=pdf["title"],
            url=pdf["url"],
            filename="description-des-bases-de-donnees-annuelles.pdf",
            expected_size=pdf.get("filesize"),
            resource_id=pdf["id"],
            last_modified=pdf["last_modified"],
        )
    )
    return resources


def download_file(session: requests.Session, url: str, dest: Path, expected_size: int | None = None) -> Path:
    """Download ``url`` to ``dest`` (atomic write). Skip if the file already exists with the right size."""
    if dest.exists() and (expected_size is None or dest.stat().st_size == expected_size):
        log.info("Already downloaded: %s", dest.name)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with session.get(url, stream=True, timeout=TIMEOUT) as response:
                response.raise_for_status()
                with open(tmp, "wb") as fh:
                    for chunk in response.iter_content(chunk_size=1 << 20):
                        fh.write(chunk)
            size = tmp.stat().st_size
            if expected_size and size != expected_size:
                raise OSError(f"size mismatch: got {size}, expected {expected_size}")
            tmp.replace(dest)
            log.info("Downloaded %s (%.1f MB)", dest.name, size / 1e6)
            return dest
        except (requests.RequestException, OSError) as exc:
            log.warning("Download failed for %s (attempt %d): %s", dest.name, attempt, exc)
            time.sleep(min(2**attempt, 30))
    raise RuntimeError(f"Could not download {url}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    """Download every raw file and write ``data/raw/manifest.json``."""
    paths = get_paths()
    cfg = load_config()["data"]
    session = _session()

    resources = resolve_onisr_resources(session)
    for res in resources:
        res_dest = paths.raw_onisr / res.filename
        download_file(session, res.url, res_dest, res.expected_size)

    others = [
        Resource("insee_population", cfg["insee_population_year"], "INSEE populations de référence",
                 cfg["insee_population_url"], "ensemble.zip"),
        Resource("departments_geojson", None, "Départements (version simplifiée)",
                 cfg["departments_geojson_url"], "departements.geojson"),
    ]
    folders = {"insee_population": paths.raw_insee, "departments_geojson": paths.raw_geo}
    for res in others:
        download_file(session, res.url, folders[res.kind] / res.filename)

    manifest = []
    for res in resources + others:
        folder = folders.get(res.kind, paths.raw_onisr)
        path = folder / res.filename
        manifest.append({**asdict(res), "path": str(path.relative_to(paths.raw)),
                         "size": path.stat().st_size, "sha256": _sha256(path)})
    out = paths.raw / "manifest.json"
    out.write_text(json.dumps({"downloaded_at": datetime.now(timezone.utc).isoformat(),
                               "files": manifest}, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Manifest written: %s (%d files)", out, len(manifest))


if __name__ == "__main__":
    from crashmap.config import setup_logging

    setup_logging()
    main()
