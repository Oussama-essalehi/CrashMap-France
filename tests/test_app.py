"""Smoke tests: every page of the Streamlit app renders without exception, in French and English."""

from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
PAGES = ["overview", "territory", "when", "conditions", "who", "hotspots", "about"]

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

pytestmark = pytest.mark.skipif(not (APP_DIR / "data" / "accidents.parquet").exists(),
                                reason="app data missing: run `python run.py web`")


def _page(app_dir: str, page: str, values: dict) -> None:
    """Render one page with the given session-state values (language, widget keys)."""
    import importlib
    import sys

    import streamlit as st

    sys.path.insert(0, app_dir)
    import helpers as h

    for key, value in values.items():
        st.session_state[key] = value
    st.session_state["filters"] = h.sidebar_filters()
    importlib.import_module(f"views.{page}").render()


def _run(page: str, **values) -> AppTest:
    at = AppTest.from_function(_page, args=(str(APP_DIR), page, values), default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("lang", ["fr", "en"])
@pytest.mark.parametrize("years", [(2019, 2024), (2024, 2024)])
def test_page_renders(page, lang, years):
    at = _run(page, lang=lang, f_years=years)
    assert at.title, "page has no title"


def test_overview_kpis_match_published_totals():
    metrics = {m.label: m.value for m in _run("overview", lang="fr", f_years=(2024, 2024)).metric}
    assert metrics["Accidents"] == "54 402"
    assert metrics["Tués"] == "3 432"  # ONISR 2024 report, France entière
    metrics = {m.label: m.value for m in _run("overview", lang="en", f_years=(2024, 2024)).metric}
    assert metrics["Accidents"] == "54,402"
    assert metrics["Killed"] == "3,432"


def test_english_page_has_no_french_title():
    assert _run("when", lang="en").title[0].value == "When?"
    assert _run("territory", lang="en").title[0].value == "Map of France"


@pytest.mark.parametrize("page, values", [
    ("territory", {"map_metric": "m_acc_100k"}),
    ("territory", {"map_metric": "m_killed_100", "f_regions": ["Occitanie"], "lang": "en"}),
    ("when", {"when_metric": "w_count", "f_loc": "out"}),
    ("hotspots", {"hotspot_layer": "hs_dbscan", "lang": "en"}),
    ("who", {"f_deps": ["Haute-Garonne"], "f_threshold": 0}),
    ("overview", {"f_deps": ["Paris"], "f_years": (2023, 2023), "f_loc": "in"}),
    *[("conditions", {"cond_factor": factor, "lang": lang})
      for factor in ["f_lum", "f_atm", "f_surf", "f_catr", "f_vma", "f_int", "f_plan", "f_col"]
      for lang in ("fr", "en")],
])
def test_page_widgets(page, values):
    _run(page, **values)


def test_i18n_keys_are_complete():
    import sys

    sys.path.insert(0, str(APP_DIR))
    import i18n

    for key, texts in i18n.UI.items():
        assert len(texts) == 2 and all(texts), key


def test_welcome_dialog_on_first_visit():
    at = AppTest.from_file(str(APP_DIR / "streamlit_app.py"), default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    text = " ".join(m.value for m in at.markdown)
    assert "327 628" in text  # welcome dialog content (French by default)
    explore = [b for b in at.button if b.label == "Explorer les données"]
    assert explore, "explore button missing"
    explore[0].click().run()
    assert at.session_state["welcomed"] is True
    assert not any(b.label == "Explorer les données" for b in at.button)
