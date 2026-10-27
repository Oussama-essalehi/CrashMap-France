"""Points noirs à Toulouse / Toulouse black spots: density map, fatal accidents and DBSCAN hotspots."""

import plotly.graph_objects as go
import streamlit as st

import helpers as h
from i18n import num, t, tv

CITY = {"insee_code": "31555", "center": {"lat": 43.6045, "lon": 1.4440}}


def render() -> None:
    f: h.Filters = st.session_state["filters"]
    acc = h.load_accidents()
    city = acc[(acc["com_code"] == CITY["insee_code"]) & acc["year"].between(*f.years) & acc["lat"].notna()]
    st.title(t("hs_title"))
    st.caption(t("hs_caption", y0=f.years[0], y1=f.years[1], n=num(len(city))))

    fatal = city[city["fatal"]]
    cols = st.columns(3)
    cols[0].metric(t("hs_located"), num(len(city)))
    cols[1].metric(t("hs_fatal"), num(len(fatal)))
    cols[2].metric(t("kpi_killed"), num(int(city["n_killed"].sum())))

    layer = st.radio(t("hs_display"), ["hs_density", "hs_dbscan"], format_func=t, horizontal=True, key="hotspot_layer")
    hotspots = h.load_hotspots()
    fig = go.Figure()
    if layer == "hs_density":
        fig.add_densitymap(lat=city["lat"], lon=city["lon"], radius=9, colorscale="YlOrRd", showscale=False,
                           name="density", hoverinfo="skip", showlegend=False)
        details = fatal.assign(band=[tv(b) for b in fatal["time_band"]], light=[tv(v) for v in fatal["lum_label"]],
                               road=[tv(v) for v in fatal["catr_label"]], day=fatal["date"].dt.strftime("%d/%m/%Y"))
        fig.add_scattermap(
            lat=details["lat"], lon=details["lon"], mode="markers", name=t("hs_fatal_marker"),
            marker=dict(size=10, color=h.color("red")),
            customdata=details[["day", "band", "light", "road", "n_killed"]].astype(str).values,
            hovertemplate="<b>" + t("hs_fatal_marker") + "</b><br>%{customdata[0]}<br>%{customdata[1]}<br>"
                          + t("hs_light") + " : %{customdata[2]}<br>" + t("hs_road") + " : %{customdata[3]}<br>"
                          + t("kpi_killed") + " : %{customdata[4]}<extra></extra>")
    else:
        fig.add_scattermap(lat=city["lat"], lon=city["lon"], mode="markers", name=t("hs_accident"),
                           marker=dict(size=5, color=h.color("grey"), opacity=0.5), hoverinfo="skip")
        if not hotspots.empty:
            fig.add_scattermap(
                lat=hotspots["lat"], lon=hotspots["lon"], mode="markers+text", name=t("hs_spot"),
                marker=dict(size=hotspots["n_accidents"].clip(lower=8) * 1.2, color=h.color("red"), opacity=0.65),
                text=hotspots["rank"].astype(str), textfont=dict(color="#ffffff", size=12),
                customdata=hotspots[["rank", "main_address", "n_accidents", "n_killed", "n_hospitalized"]].values,
                hovertemplate="<b>" + t("hs_spot_n") + "%{customdata[0]}</b><br>%{customdata[1]}<br>%{customdata[2]} "
                              + t("hover_accidents") + "<br>" + t("kpi_killed") + " : %{customdata[3]}, "
                              + t("hs_hosp") + " : %{customdata[4]}<extra></extra>")
    fig.update_layout(map=dict(style=h.color("map_style"), center=CITY["center"], zoom=11.5), height=600,
                      margin=dict(l=0, r=0, t=0, b=0),
                      legend=dict(x=0.01, y=0.99, bgcolor=h.color("legend_bg")))
    h.show(fig, "hotspot_map")

    st.subheader(t("hs_top10"))
    st.markdown(t("hs_method"))
    if not hotspots.empty:
        st.dataframe(hotspots[["rank", "main_address", "n_accidents", "n_killed", "n_hospitalized",
                               "n_pedestrians_cyclists_edp", "first_year", "last_year"]].rename(columns={
            "rank": t("col_rank"), "main_address": t("col_address"), "n_accidents": t("col_accidents"),
            "n_killed": t("col_killed"), "n_hospitalized": t("col_hosp"),
            "n_pedestrians_cyclists_edp": t("col_vulnerable"), "first_year": t("col_from"),
            "last_year": t("col_to")}), hide_index=True)
    st.caption(t("osm_credit") + " " + t("source") + ".")
