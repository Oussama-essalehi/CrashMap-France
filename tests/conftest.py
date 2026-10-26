"""Shared fixtures: the hand-made CSVs in tests/fixtures cover 2019 and 2022 format variants."""

from pathlib import Path

import pandas as pd
import pytest

from crashmap.clean import run_cleaning
from crashmap.standardize import load_all

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def raw_tables() -> dict[str, pd.DataFrame]:
    return load_all(FIXTURES)


@pytest.fixture(scope="session")
def departments() -> pd.DataFrame:
    return pd.DataFrame({
        "dep_code": ["01", "31", "971", "2A"],
        "dep_name": ["Ain", "Haute-Garonne", "Guadeloupe", "Corse-du-Sud"],
        "region_name": ["Auvergne-Rhône-Alpes", "Occitanie", "Guadeloupe", "Corse"],
        "population": [694945, 1460000, 388493, 162000],
    })


@pytest.fixture(scope="session")
def grains(raw_tables, departments) -> dict[str, pd.DataFrame]:
    return run_cleaning(raw_tables, departments)
