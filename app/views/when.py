"""Quand ? / When?: hour x weekday, time bands, months."""

import plotly.graph_objects as go
import streamlit as st

import helpers as h
from i18n import months, num, t, weekdays


def render() -> None:
    f: h.Filters = st.session_state["filters"]
    acc = h.apply_filters(h.load_accidents(), f)
    st.title(t("when_title"))
    st.caption(t("selection_n", desc=f.describe(), n=num(len(acc))))

    st.subheader(t("when_grid"))
    metric = st.radio(t("indicator"), ["w_rate", "w_count"], format_func=t, horizontal=True, key="when_metric")
    hw = h.rate_table(acc, ["day_of_week", "hour"], f.threshold)
    value = "killed_per_100" if metric == "w_rate" else "n_accidents"
    grid = hw.pivot(index="day_of_week", columns="hour", values=value).reindex(index=range(7), columns=range(24))
    counts = hw.pivot(index="day_of_week", columns="hour", values="n_accidents").reindex(index=range(7), columns=range(24))
    rate_line = "%{z:.1f} " + t("hover_rate") + "<br>" if value == "killed_per_100" else ""
    fig = go.Figure(go.Heatmap(
        z=grid.values, x=[f"{hr}h" for hr in range(24)], y=weekdays(), xgap=2, ygap=2,
        colorscale=h.color("seq_red") if value == "killed_per_100" else h.color("seq_blue"),
        customdata=counts.values, colorbar=dict(thickness=12, title=""),
        hovertemplate="%{y} %{x}<br>" + rate_line + "%{customdata:,} " + t("hover_accidents") + "<extra></extra>"))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_layout(height=360)
    h.show(fig, "when_heatmap")
    st.caption(t("when_grid_note"))

    left, right = st.columns(2)
    with left:
        st.subheader(t("by_band"))
        bands = h.rate_table(acc, "time_band", f.threshold)
        h.show(h.dot_ci(bands, "time_band"), "when_bands")
        night = bands.set_index("time_band")
        if "Nuit (21h-6h)" in night.index and len(acc):
            share_acc = night.loc["Nuit (21h-6h)", "n_accidents"] / len(acc) * 100
            share_killed = night.loc["Nuit (21h-6h)", "n_killed"] / max(acc["n_killed"].sum(), 1) * 100
            st.markdown(t("night_share", acc=num(share_acc, 1), killed=num(share_killed, 1)))
    with right:
        st.subheader(t("by_month"))
        labels = months()
        by_month = h.rate_table(acc, "month", f.threshold).sort_values("month")
        x = [labels[m - 1] for m in by_month["month"]]
        fig = go.Figure(go.Bar(x=x, y=by_month["n_accidents"], marker_color=h.color("blue"),
                               hovertemplate="%{x} : %{y:,}<extra></extra>"))
        fig.update_layout(height=230, title=dict(text=t("accidents_axis"), font=dict(size=14)))
        h.show(fig, "when_months_acc")
        fig = go.Figure(go.Scatter(x=x, y=by_month["killed_per_100"], mode="lines+markers",
                                   line=dict(color=h.color("orange"), width=2), marker=dict(size=8),
                                   hovertemplate="%{x} : %{y:.2f}<extra></extra>"))
        fig.update_yaxes(rangemode="tozero")
        fig.update_layout(height=230, title=dict(text=t("w_rate"), font=dict(size=14)))
        h.show(fig, "when_months_rate")

    st.subheader(t("week_or_weekend"))
    acc_days = acc.assign(day_type=acc["day_of_week"].map(lambda d: "Week-end" if d >= 5 else "Semaine"))
    h.show(h.dot_ci(h.rate_table(acc_days, "day_type", f.threshold), "day_type", height=220), "when_weekend")
    h.small_sample_note(f.threshold)
