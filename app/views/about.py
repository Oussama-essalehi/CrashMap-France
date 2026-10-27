"""Méthode et sources / Method and sources."""

import streamlit as st

import helpers as h
from i18n import t


def render() -> None:
    st.title(t("nav_about"))
    st.markdown(t("about_md", repo=h.REPO_URL))
