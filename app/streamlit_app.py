"""CrashMap France - web app (Streamlit), in French and English, light and dark themes.

Run locally from the repository root:  streamlit run app/streamlit_app.py
The data comes from app/data/ (built by `python run.py web`).
"""

import streamlit as st

from helpers import REPO_URL, language_selector, sidebar_filters
from i18n import t
from views import about, conditions, hotspots, overview, territory, when, who

st.set_page_config(page_title="CrashMap France", page_icon="🚦", layout="wide",
                   menu_items={"About": f"CrashMap France - 2019-2024. {REPO_URL}"})


def _mark_welcomed() -> None:
    st.session_state["welcomed"] = True


def _switch_language() -> None:
    st.session_state["lang"] = "en" if st.session_state.get("lang", "fr") == "fr" else "fr"


@st.dialog("CrashMap France", width="large", icon=":material/traffic:", on_dismiss=_mark_welcomed)
def welcome() -> None:
    """Shown once per visit: what the project is about and how to use the site."""
    st.subheader(t("welcome_title"))
    st.markdown(t("welcome_body"))
    left, right = st.columns(2)
    if left.button(t("welcome_explore"), type="primary", icon=":material/arrow_forward:", width="stretch"):
        _mark_welcomed()
        st.rerun()
    right.button(t("welcome_other_lang"), icon=":material/translate:", width="stretch", on_click=_switch_language)


with st.sidebar:
    language_selector()
    if st.button(t("about_button"), icon=":material/info:", width="stretch"):
        st.session_state["welcomed"] = False
    st.caption(t("theme_hint"))

# Filters live in the entry script so they stay rendered (and keep their values) on every page.
st.session_state["filters"] = sidebar_filters()

if not st.session_state.get("welcomed", False):
    welcome()

pages = st.navigation([
    st.Page(overview.render, title=t("nav_overview"), icon=":material/dashboard:", default=True),
    st.Page(territory.render, title=t("nav_map"), icon=":material/map:", url_path="carte"),
    st.Page(when.render, title=t("nav_when"), icon=":material/schedule:", url_path="quand"),
    st.Page(conditions.render, title=t("nav_conditions"), icon=":material/rainy:", url_path="conditions"),
    st.Page(who.render, title=t("nav_who"), icon=":material/group:", url_path="qui"),
    st.Page(hotspots.render, title=t("nav_hotspots"), icon=":material/location_on:", url_path="points-noirs"),
    st.Page(about.render, title=t("nav_about"), icon=":material/menu_book:", url_path="methode"),
])
pages.run()
