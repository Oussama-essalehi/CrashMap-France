"""Carte de France: rates by department (choropleth) and rankings."""

import pandas as pd
import plotly.express as px
import streamlit as st

import helpers as h

METRICS = {
    "Tués pour 100 000 habitants par an": ("killed_per_100k", 1),
    "Accidents pour 100 000 habitants par an": ("accidents_per_100k", 1),
    "Tués pour 100 accidents": ("killed_per_100", 2),
}


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
    st.title("Carte de France")
    st.caption(f"Sélection : {f.describe()}")
    label = st.radio("Indicateur", list(METRICS), horizontal=True, key="map_metric")
    column, digits = METRICS[label]
    rates = department_rates(acc, f)
    metro = rates[rates["zone"] == "Métropole"]

    left, right = st.columns([3, 2])
    with left:
        fig = px.choropleth(
            metro, geojson=h.load_geojson(), locations="dep_code", featureidkey="properties.code",
            color=column, color_continuous_scale=h.SEQUENTIAL_RED, hover_name="dep_name",
            hover_data={"dep_code": True, column: f":.{digits}f", "accidents": ":,", "killed": ":,"},
            labels={column: label, "accidents": "Accidents", "killed": "Tués", "dep_code": "Code"},
        )
        fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
        fig.update_layout(height=640, margin=dict(l=0, r=0, t=0, b=0),
                          coloraxis_colorbar=dict(title="", thickness=12, len=0.6))
        h.show(fig, "map_choropleth")
        st.caption("Départements en gris : moins d'accidents que le seuil choisi, ou hors de la sélection.")
    with right:
        ranked = rates.dropna(subset=[column]).sort_values(column, ascending=False)
        table = ranked[["dep_name", column, "accidents", "killed"]].rename(columns={
            "dep_name": "Département", column: "Taux", "accidents": "Accidents", "killed": "Tués"})
        config = {"Taux": st.column_config.NumberColumn(format=f"%.{digits}f", help=label),
                  "Accidents": st.column_config.NumberColumn(format="localized"),
                  "Tués": st.column_config.NumberColumn(format="localized")}
        st.markdown(f"**Les 10 départements les plus touchés** · {label.lower()}")
        st.dataframe(table.head(10), hide_index=True, column_config=config)
        st.markdown(f"**Les 10 départements les moins touchés** · {label.lower()}")
        st.dataframe(table.tail(10).iloc[::-1], hide_index=True, column_config=config)

    st.subheader("Outre-mer")
    overseas = rates[rates["zone"] != "Métropole"].sort_values(column, ascending=False)
    st.dataframe(overseas[["dep_name", "zone", column, "accidents", "killed", "population"]].rename(columns={
        "dep_name": "Territoire", "zone": "Zone", column: label, "accidents": "Accidents", "killed": "Tués",
        "population": "Population 2023"}), hide_index=True,
        column_config={label: st.column_config.NumberColumn(format=f"%.{digits}f"),
                       "Population 2023": st.column_config.NumberColumn(format="localized")})
    st.caption("Mayotte, Wallis-et-Futuna, la Polynésie française et la Nouvelle-Calédonie n'ont pas de "
               "population de référence INSEE 2023 : pas de taux par habitant.")
    h.small_sample_note(f.threshold)
