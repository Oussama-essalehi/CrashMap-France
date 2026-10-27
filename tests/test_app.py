"""Smoke tests: every page of the Streamlit app renders without exception on the committed app data."""

from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
PAGES = ["overview", "territory", "when", "conditions", "who", "hotspots", "about"]

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

pytestmark = pytest.mark.skipif(not (APP_DIR / "data" / "accidents.parquet").exists(),
                                reason="app data missing: run `python run.py web`")


def _page(app_dir: str, page: str, years: tuple[int, int]) -> None:
    import importlib
    import sys

    import streamlit as st

    sys.path.insert(0, app_dir)
    import helpers as h

    filters = h.sidebar_filters()
    filters.years = years
    st.session_state["filters"] = filters
    importlib.import_module(f"views.{page}").render()


@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("years", [(2019, 2024), (2024, 2024)])
def test_page_renders(page, years):
    at = AppTest.from_function(_page, args=(str(APP_DIR), page, years), default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.title, "page has no title"


def test_overview_kpis_match_published_totals():
    at = AppTest.from_function(_page, args=(str(APP_DIR), "overview", (2024, 2024)), default_timeout=120)
    at.run()
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Accidents"] == "54 402"
    assert metrics["Tués"] == "3 432"  # ONISR 2024 report, France entière


def _page_with_widgets(app_dir: str, page: str, widget_values: dict) -> None:
    import importlib
    import sys

    import streamlit as st

    sys.path.insert(0, app_dir)
    import helpers as h

    for key, value in widget_values.items():
        st.session_state[key] = value
    st.session_state["filters"] = h.sidebar_filters()
    importlib.import_module(f"views.{page}").render()


@pytest.mark.parametrize("page, values", [
    ("territory", {"map_metric": "Accidents pour 100 000 habitants par an"}),
    ("territory", {"map_metric": "Tués pour 100 accidents", "f_regions": ["Occitanie"]}),
    ("when", {"when_metric": "Nombre d'accidents", "f_loc": "Hors agglomération"}),
    ("hotspots", {"hotspot_layer": "Points noirs (DBSCAN)"}),
    ("who", {"f_deps": ["Haute-Garonne"], "f_threshold": 0}),
    ("overview", {"f_deps": ["Paris"], "f_years": (2023, 2023)}),
    *[("conditions", {"cond_factor": factor}) for factor in
      ["Luminosité", "Conditions météo", "État de la surface", "Catégorie de route", "Vitesse maximale autorisée",
       "Type d'intersection", "Tracé de la route", "Type de collision"]],
])
def test_page_widgets(page, values):
    at = AppTest.from_function(_page_with_widgets, args=(str(APP_DIR), page, values), default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
