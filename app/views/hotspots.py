"""Points noirs à Toulouse: density map, fatal accidents and DBSCAN hotspots."""

import plotly.graph_objects as go
import streamlit as st

import helpers as h

CITY = {"name": "Toulouse", "insee_code": "31555", "center": {"lat": 43.6045, "lon": 1.4440}}


def render() -> None:
    f: h.Filters = st.session_state["filters"]
    acc = h.load_accidents()
    city = acc[(acc["com_code"] == CITY["insee_code"]) & acc["year"].between(*f.years) & acc["lat"].notna()]
    st.title(f"Points noirs à {CITY['name']}")
    st.caption(f"Années {f.years[0]}-{f.years[1]} · {h.fr(len(city))} accidents géolocalisés précisément "
               "(les filtres de région, département et localisation ne s'appliquent pas à cette page).")

    fatal = city[city["fatal"]]
    cols = st.columns(3)
    cols[0].metric("Accidents géolocalisés", h.fr(len(city)))
    cols[1].metric("Accidents mortels", h.fr(len(fatal)))
    cols[2].metric("Tués", h.fr(int(city["n_killed"].sum())))

    layer = st.radio("Affichage", ["Densité des accidents", "Points noirs (DBSCAN)"], horizontal=True,
                     key="hotspot_layer")
    hotspots = h.load_hotspots()
    fig = go.Figure()
    if layer == "Densité des accidents":
        fig.add_densitymap(lat=city["lat"], lon=city["lon"], radius=9, colorscale="YlOrRd", showscale=False,
                           name="Densité", hoverinfo="skip")
        fig.add_scattermap(
            lat=fatal["lat"], lon=fatal["lon"], mode="markers", name="Accident mortel",
            marker=dict(size=10, color=h.RED),
            customdata=fatal[["date", "time_band", "lum_label", "catr_label", "n_killed"]].astype(str).values,
            hovertemplate="<b>Accident mortel</b><br>%{customdata[0]}<br>%{customdata[1]}<br>"
                          "Luminosité : %{customdata[2]}<br>Route : %{customdata[3]}<br>Tués : %{customdata[4]}<extra></extra>")
    else:
        fig.add_scattermap(lat=city["lat"], lon=city["lon"], mode="markers", name="Accident",
                           marker=dict(size=5, color=h.GREY, opacity=0.5), hoverinfo="skip")
        if not hotspots.empty:
            fig.add_scattermap(
                lat=hotspots["lat"], lon=hotspots["lon"], mode="markers+text", name="Point noir",
                marker=dict(size=hotspots["n_accidents"].clip(lower=8) * 1.2, color=h.RED, opacity=0.6),
                text=hotspots["rank"].astype(str), textfont=dict(color="#ffffff", size=12),
                customdata=hotspots[["rank", "main_address", "n_accidents", "n_killed", "n_hospitalized"]].values,
                hovertemplate="<b>Point noir n°%{customdata[0]}</b><br>%{customdata[1]}<br>%{customdata[2]} accidents"
                              "<br>Tués : %{customdata[3]}, hospitalisés : %{customdata[4]}<extra></extra>")
    fig.update_layout(map=dict(style="open-street-map", center=CITY["center"], zoom=11.5), height=600,
                      margin=dict(l=0, r=0, t=0, b=0), legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,.8)"))
    h.show(fig, "hotspot_map")

    st.subheader("Les 10 points noirs")
    st.markdown("Regroupement **DBSCAN** des accidents précisément géolocalisés de 2019 à 2024 : un point noir "
                "rassemble au moins 8 accidents situés à moins de 100 m les uns des autres.")
    if not hotspots.empty:
        st.dataframe(hotspots[["rank", "main_address", "n_accidents", "n_killed", "n_hospitalized",
                               "n_pedestrians_cyclists_edp", "first_year", "last_year"]].rename(columns={
            "rank": "Rang", "main_address": "Adresse principale", "n_accidents": "Accidents", "n_killed": "Tués",
            "n_hospitalized": "Blessés hospitalisés", "n_pedestrians_cyclists_edp": "Piétons, cyclistes, EDP",
            "first_year": "Depuis", "last_year": "Jusqu'à"}), hide_index=True)
    st.caption("Fond de carte © les contributeurs d'OpenStreetMap. " + h.SOURCE + ".")
