"""CrashMap France - web app (Streamlit).

Run locally from the repository root:  streamlit run app/streamlit_app.py
The data comes from app/data/ (built by `python run.py web`).
"""

import streamlit as st

from helpers import REPO_URL, sidebar_filters
from views import about, conditions, hotspots, overview, territory, when, who

st.set_page_config(page_title="CrashMap France", page_icon="🚦", layout="wide",
                   menu_items={"About": f"CrashMap France - accidents de la route 2019-2024. Code : {REPO_URL}"})

# Filters live in the entry script so they stay rendered (and keep their values) on every page.
st.session_state["filters"] = sidebar_filters()

pages = st.navigation([
    st.Page(overview.render, title="Vue d'ensemble", icon=":material/dashboard:", default=True),
    st.Page(territory.render, title="Carte de France", icon=":material/map:", url_path="carte"),
    st.Page(when.render, title="Quand ?", icon=":material/schedule:", url_path="quand"),
    st.Page(conditions.render, title="Dans quelles conditions ?", icon=":material/rainy:", url_path="conditions"),
    st.Page(who.render, title="Qui ?", icon=":material/group:", url_path="qui"),
    st.Page(hotspots.render, title="Points noirs à Toulouse", icon=":material/location_on:", url_path="points-noirs"),
    st.Page(about.render, title="Méthode et sources", icon=":material/menu_book:", url_path="methode"),
])
pages.run()
