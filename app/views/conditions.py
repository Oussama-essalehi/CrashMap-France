"""Dans quelles conditions ? / Under what conditions?: severity by condition, speed x location, model."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import helpers as h
from i18n import num, t, tv, tv_series

# factor key -> data column
FACTORS = {"f_lum": "lum_label", "f_atm": "atm_label", "f_surf": "surf_label", "f_catr": "catr_label",
           "f_vma": "vma_band", "f_int": "int_label", "f_plan": "plan_label", "f_col": "col_label"}


def render() -> None:
    f: h.Filters = st.session_state["filters"]
    acc = h.apply_filters(h.load_accidents(), f)
    st.title(t("cond_title"))
    st.caption(t("selection_n", desc=f.describe(), n=num(len(acc))))

    factor = st.selectbox(t("factor"), list(FACTORS), format_func=t, key="cond_factor")
    column = FACTORS[factor]
    tbl = h.rate_table(acc, column, f.threshold)
    h.show(h.dot_ci(tbl, column), "cond_dot")
    with st.expander(t("show_table")):
        shown = tbl.sort_values("killed_per_100", ascending=False).copy()
        shown[column] = tv_series(shown[column])
        st.dataframe(
            shown[[column, "n_accidents", "n_killed", "killed_per_100", "pct_fatal"]].rename(columns={
                column: t(factor), "n_accidents": t("col_accidents"), "n_killed": t("col_killed"),
                "killed_per_100": t("col_rate100"), "pct_fatal": t("col_pct_fatal")}),
            hide_index=True,
            column_config={t("col_accidents"): st.column_config.NumberColumn(format="localized"),
                           t("col_killed"): st.column_config.NumberColumn(format="localized"),
                           t("col_rate100"): st.column_config.NumberColumn(format="%.2f"),
                           t("col_pct_fatal"): st.column_config.NumberColumn(format="%.1f")})

    st.subheader(t("speed_location"))
    fig = go.Figure()
    for color_name, (flag, key) in zip(("blue", "orange"), ((True, "loc_in"), (False, "loc_out"))):
        sub = acc[acc["in_town"].fillna(not flag).astype(bool) == flag]
        rt = h.rate_table(sub, "vma_band", f.threshold).dropna(subset=["pct_fatal"])
        rt = rt.set_index("vma_band").reindex(h.SPEED_BANDS).dropna(subset=["pct_fatal"]).reset_index()
        c = h.color(color_name)
        fig.add_scatter(x=rt["vma_band"], y=rt["pct_fatal"], mode="lines+markers", name=t(key),
                        line=dict(color=c, width=2), marker=dict(size=9),
                        error_y=dict(type="data", symmetric=False, array=rt["ci_high"] - rt["pct_fatal"],
                                     arrayminus=rt["pct_fatal"] - rt["ci_low"], color=c),
                        hovertemplate=t(key) + "<br>%{x} : %{y:.1f} %<extra></extra>")
    fig.update_yaxes(title_text=t("pct_fatal_axis"), rangemode="tozero")
    fig.update_layout(height=380)
    h.show(fig, "cond_speed")

    st.subheader(t("model_title"))
    st.markdown(t("model_intro"))
    ors = h.load_odds_ratios()
    if not ors.empty:
        ors = ors[ors["n_accidents"] >= 500].copy()
        ors["label"] = [f"{tv(v)} : {tv(lv)} ({t('ref')} {tv(r)})"
                        for v, lv, r in zip(ors["variable_label"], ors["level"], ors["reference"])]
        ors = ors.sort_values("odds_ratio")
        colors = np.where(ors["ci_low"] > 1, h.color("red"), np.where(ors["ci_high"] < 1, h.color("blue"), h.color("grey")))
        fig = go.Figure(go.Scatter(
            x=ors["odds_ratio"], y=ors["label"], mode="markers", marker=dict(size=9, color=colors),
            error_x=dict(type="data", symmetric=False, array=ors["ci_high"] - ors["odds_ratio"],
                         arrayminus=ors["odds_ratio"] - ors["ci_low"], color=h.color("text_secondary")),
            hovertemplate="%{y}<br>odds ratio %{x:.2f}<extra></extra>"))
        fig.add_vline(x=1, line=dict(color=h.color("text_secondary"), width=1))
        ticks = [0.3, 0.5, 0.7, 1, 1.5, 2, 3, 5, 7]
        fig.update_xaxes(type="log", tickvals=ticks, title_text=t("or_axis"))
        fig.update_layout(height=900, showlegend=False)
        h.show(fig, "cond_odds")
    h.small_sample_note(f.threshold)
