"""Vue d'ensemble / Overview: KPIs, trend by year, monthly pattern."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import helpers as h
from i18n import months, num, t


def kpis(acc: pd.DataFrame, f: h.Filters) -> dict:
    n = len(acc)
    killed = int(acc["n_killed"].sum())
    with_pop = h.with_population(acc)
    pop = h.population(f)
    ok = n >= max(f.threshold, 1)
    return {
        "accidents": n,
        "killed": killed,
        "killed_per_100": killed / n * 100 if ok else None,
        "killed_per_100k": with_pop["n_killed"].sum() / (pop * f.n_years) * 1e5 if ok and pop else None,
        "night_share": (acc["time_band"] == "Nuit (21h-6h)").mean() * 100 if ok else None,
        "out_of_town_killed": acc.loc[~acc["in_town"].fillna(True).astype(bool), "n_killed"].sum() / killed * 100
        if ok and killed else None,
    }


def render() -> None:
    f: h.Filters = st.session_state["filters"]
    acc_all = h.load_accidents()
    acc = h.apply_filters(acc_all, f)

    st.title(t("ov_title"))
    st.markdown(t("ov_pitch"))
    st.caption(t("selection_n", desc=f.describe(), n=num(len(acc))))

    k = kpis(acc, f)
    delta = {}
    if f.years[0] == f.years[1] and f.years[0] > int(acc_all["year"].min()):
        prev_f = h.Filters((f.years[0] - 1, f.years[0] - 1), f.regions, f.departments, f.localisation, f.threshold)
        prev = kpis(h.apply_filters(acc_all, prev_f), prev_f)
        if prev["accidents"]:
            delta["accidents"] = num((k["accidents"] / prev["accidents"] - 1) * 100, 1, t("vs_prev"))
        if prev["killed"]:
            delta["killed"] = num((k["killed"] / prev["killed"] - 1) * 100, 1, t("vs_prev"))

    cols = st.columns(6)
    cols[0].metric(t("kpi_accidents"), num(k["accidents"]), delta.get("accidents"), delta_color="inverse")
    cols[1].metric(t("kpi_killed"), num(k["killed"]), delta.get("killed"), delta_color="inverse")
    cols[2].metric(t("kpi_rate"), num(k["killed_per_100"], 2))
    cols[3].metric(t("kpi_100k"), num(k["killed_per_100k"], 1), help=t("kpi_100k_help"))
    cols[4].metric(t("kpi_night"), num(k["night_share"], 1, " %"), help=t("kpi_night_help"))
    cols[5].metric(t("kpi_out"), num(k["out_of_town_killed"], 1, " %"), help=t("kpi_out_help"))

    st.subheader(t("ov_by_year"))
    yearly = acc.groupby("year").agg(accidents=("accident_id", "size"), killed=("n_killed", "sum")).reset_index()
    colors = [h.color("grey") if y == h.COVID_YEAR else h.color("blue") for y in yearly["year"]]
    fig = make_subplots(rows=1, cols=2, subplot_titles=(t("injury_accidents"), t("people_killed")),
                        horizontal_spacing=0.08)
    for i, col in enumerate(("accidents", "killed"), start=1):
        fig.add_bar(x=yearly["year"].astype(str), y=yearly[col], marker_color=colors, showlegend=False,
                    text=[num(v) for v in yearly[col]], textposition="outside", cliponaxis=False, row=1, col=i,
                    hovertemplate="%{x} : %{y:,}<extra></extra>")
    fig.update_yaxes(rangemode="tozero")
    fig.update_layout(height=360, margin=dict(t=50))
    fig.update_annotations(font_color=h.color("text"))
    h.show(fig, "overview_yearly")
    st.caption(t("covid_grey"))

    st.subheader(t("ov_by_month"))
    monthly = acc.groupby(["year", "month"]).size().rename("accidents").reset_index()
    fig = go.Figure()
    palette = h.categorical()
    labels = months()
    for i, (year, grp) in enumerate(monthly.groupby("year")):
        fig.add_scatter(x=[labels[m - 1] for m in grp["month"]], y=grp["accidents"], mode="lines+markers",
                        name=str(year), line=dict(width=2, color=palette[i % len(palette)],
                                                  dash="dot" if year == h.COVID_YEAR else "solid"),
                        hovertemplate=f"{year} %{{x}} : %{{y:,}}<extra></extra>")
    fig.update_yaxes(rangemode="tozero", title_text=t("accidents_axis"))
    fig.update_layout(height=380)
    h.show(fig, "overview_monthly")

    with st.container(border=True):
        st.markdown(t("ov_key_points"))
    h.small_sample_note(f.threshold)
