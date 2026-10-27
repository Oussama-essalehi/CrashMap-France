"""Quand ?: hour x weekday, time bands, months."""

import plotly.graph_objects as go
import streamlit as st

import helpers as h


def render() -> None:
    f: h.Filters = st.session_state["filters"]
    acc = h.apply_filters(h.load_accidents(), f)
    st.title("Quand ?")
    st.caption(f"Sélection : {f.describe()} · {h.fr(len(acc))} accidents")

    st.subheader("Jour de la semaine × heure")
    metric = st.radio("Indicateur", ["Tués pour 100 accidents", "Nombre d'accidents"], horizontal=True,
                      key="when_metric")
    hw = h.rate_table(acc, ["day_of_week", "hour"], f.threshold)
    value = "killed_per_100" if metric.startswith("Tués") else "n_accidents"
    grid = hw.pivot(index="day_of_week", columns="hour", values=value).reindex(index=range(7), columns=range(24))
    counts = hw.pivot(index="day_of_week", columns="hour", values="n_accidents").reindex(index=range(7), columns=range(24))
    fig = go.Figure(go.Heatmap(
        z=grid.values, x=[f"{hr}h" for hr in range(24)], y=h.WEEKDAYS, xgap=2, ygap=2,
        colorscale=h.SEQUENTIAL_RED if value == "killed_per_100" else h.SEQUENTIAL_BLUE,
        customdata=counts.values, colorbar=dict(thickness=12, title=""),
        hovertemplate="%{y} %{x}<br>" + ("%{z:.1f} tués / 100 accidents<br>" if value == "killed_per_100" else "")
                      + "%{customdata:,} accidents<extra></extra>"))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_layout(height=360)
    h.show(fig, "when_heatmap")
    st.caption("Cases vides : moins d'accidents que le seuil. Les accidents entre minuit et 6h sont les plus graves, "
               "quel que soit le jour.")

    left, right = st.columns(2)
    with left:
        st.subheader("Par tranche horaire")
        bands = h.rate_table(acc, "time_band", f.threshold)
        h.show(h.dot_ci(bands, "time_band"), "when_bands")
        night = bands.set_index("time_band")
        if "Nuit (21h-6h)" in night.index and len(acc):
            share_acc = night.loc["Nuit (21h-6h)", "n_accidents"] / len(acc) * 100
            share_killed = night.loc["Nuit (21h-6h)", "n_killed"] / max(acc["n_killed"].sum(), 1) * 100
            st.markdown(f"La nuit représente **{h.fr(share_acc, 1)} %** des accidents et "
                        f"**{h.fr(share_killed, 1)} %** des tués de la sélection.")
    with right:
        st.subheader("Par mois")
        months = h.rate_table(acc, "month", f.threshold).sort_values("month")
        fig = go.Figure(go.Bar(x=[h.MONTHS[m - 1] for m in months["month"]], y=months["n_accidents"],
                               marker_color=h.BLUE, hovertemplate="%{x} : %{y:,} accidents<extra></extra>"))
        fig.update_layout(height=230, title=dict(text="Accidents", font=dict(size=14)))
        h.show(fig, "when_months_acc")
        fig = go.Figure(go.Scatter(x=[h.MONTHS[m - 1] for m in months["month"]], y=months["killed_per_100"],
                                   mode="lines+markers", line=dict(color=h.ORANGE, width=2), marker=dict(size=8),
                                   hovertemplate="%{x} : %{y:.2f} tués / 100 accidents<extra></extra>"))
        fig.update_yaxes(rangemode="tozero")
        fig.update_layout(height=230, title=dict(text="Tués pour 100 accidents", font=dict(size=14)))
        h.show(fig, "when_months_rate")

    st.subheader("Semaine ou week-end")
    acc_days = acc.assign(day_type=acc["day_of_week"].map(lambda d: "Week-end" if d >= 5 else "Semaine"))
    h.show(h.dot_ci(h.rate_table(acc_days, "day_type", f.threshold), "day_type", height=220), "when_weekend")
    h.small_sample_note(f.threshold)
