"""Carte de France / Map of France: rates by department (choropleth) and rankings."""

import pandas as pd
import plotly.express as px
import streamlit as st

import helpers as h
from i18n import t, tv_series

# metric key -> (column, decimals)
METRICS = {"m_killed_100k": ("killed_per_100k", 1), "m_acc_100k": ("accidents_per_100k", 1),
           "m_killed_100": ("killed_per_100", 2)}


def department_rates(acc: pd.DataFrame, f: h.Filters) -> pd.DataFrame:
    deps = h.load_departments()
    g = acc.groupby("dep_code", observed=True).agg(accidents=("accident_id", "size"),
                                                   killed=("n_killed", "sum")).reset_index()
    g = deps.merge(g, on="dep_code", how="left").fillna({"accidents": 0, "killed": 0})
    ok = g["accidents"] >= max(f.threshold, 1)
    pop = g["population"].astype(float)
    g["killed_per_100k"] = (g["killed"] / (pop * f.n_years) * 1e5).where(ok)
    g["accidents_per_100k"] = (g["accidents"] / (pop * f.n_years) * 1e5).where(ok)
    g["killed_per_100"] = (g["killed"] / g["accidents"] * 100).where(ok)
    return g


def render() -> None:
    f: h.Filters = st.session_state["filters"]
    acc = h.apply_filters(h.load_accidents(), f)
    st.title(t("map_title"))
    st.caption(t("selection", desc=f.describe()))
    metric = st.radio(t("indicator"), list(METRICS), format_func=t, horizontal=True, key="map_metric")
    column, digits = METRICS[metric]
    label = t(metric)
    rates = department_rates(acc, f)
    metro = rates[rates["zone"] == "Métropole"]

    left, right = st.columns([3, 2])
    with left:
        fig = px.choropleth(
            metro, geojson=h.load_geojson(), locations="dep_code", featureidkey="properties.code",
            color=column, color_continuous_scale=h.color("seq_red"), hover_name="dep_name",
            hover_data={"dep_code": True, column: f":.{digits}f", "accidents": ":,", "killed": ":,"},
            labels={column: label, "accidents": t("col_accidents"), "killed": t("col_killed"), "dep_code": t("col_code")},
        )
        fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator", bgcolor="rgba(0,0,0,0)")
        fig.update_traces(marker_line_color=h.color("grid"))
        fig.update_layout(height=640, margin=dict(l=0, r=0, t=0, b=0),
                          coloraxis_colorbar=dict(title="", thickness=12, len=0.6))
        h.show(fig, "map_choropleth")
        st.caption(t("map_grey"))
    with right:
        ranked = rates.dropna(subset=[column]).sort_values(column, ascending=False)
        table = ranked[["dep_name", column, "accidents", "killed"]].rename(columns={
            "dep_name": t("col_department"), column: t("col_rate"), "accidents": t("col_accidents"),
            "killed": t("col_killed")})
        config = {t("col_rate"): st.column_config.NumberColumn(format=f"%.{digits}f", help=label),
                  t("col_accidents"): st.column_config.NumberColumn(format="localized"),
                  t("col_killed"): st.column_config.NumberColumn(format="localized")}
        st.markdown(f"**{t('top10')}** · {label.lower()}")
        st.dataframe(table.head(10), hide_index=True, column_config=config)
        st.markdown(f"**{t('bottom10')}** · {label.lower()}")
        st.dataframe(table.tail(10).iloc[::-1], hide_index=True, column_config=config)

    st.subheader(t("overseas"))
    overseas = rates[rates["zone"] != "Métropole"].sort_values(column, ascending=False).copy()
    overseas["zone"] = tv_series(overseas["zone"])
    st.dataframe(overseas[["dep_name", "zone", column, "accidents", "killed", "population"]].rename(columns={
        "dep_name": t("col_territory"), "zone": t("col_zone"), column: label, "accidents": t("col_accidents"),
        "killed": t("col_killed"), "population": t("col_population")}), hide_index=True,
        column_config={label: st.column_config.NumberColumn(format=f"%.{digits}f"),
                       t("col_population"): st.column_config.NumberColumn(format="localized")})
    st.caption(t("overseas_note"))
    h.small_sample_note(f.threshold)
