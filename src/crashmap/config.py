"""Project configuration and paths, read from ``config.yaml`` at the repository root."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = ROOT / "config.yaml"


@dataclass(frozen=True)
class Paths:
    """Absolute paths used by the pipeline."""

    raw: Path
    processed: Path
    gold: Path
    figures: Path
    maps: Path

    @property
    def raw_onisr(self) -> Path:
        return self.raw / "onisr"

    @property
    def raw_insee(self) -> Path:
        return self.raw / "insee"

    @property
    def raw_geo(self) -> Path:
        return self.raw / "geo"


@lru_cache(maxsize=1)
def load_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    """Load ``config.yaml`` as a dictionary."""
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get_paths() -> Paths:
    """Return the project paths, creating the folders if needed."""
    cfg = load_config()["paths"]
    paths = Paths(**{key: ROOT / value for key, value in cfg.items()})
    for folder in (paths.raw, paths.processed, paths.gold, paths.figures, paths.maps):
        folder.mkdir(parents=True, exist_ok=True)
    return paths


def min_accidents() -> int:
    """Minimum number of accidents in a group before a rate is shown."""
    return int(load_config()["analysis"]["min_accidents_for_rate"])


def postgres_url() -> str:
    """SQLAlchemy URL built from the POSTGRES_* environment variables (or a local .env file)."""
    _load_dotenv(ROOT / ".env")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "crashmap")
    user = os.getenv("POSTGRES_USER", "crashmap")
    password = os.getenv("POSTGRES_PASSWORD", "change_me")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader: KEY=VALUE lines, existing variables are not overridden."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def setup_logging(level: int = logging.INFO) -> None:
    """Configure a simple console logger for the pipeline."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
