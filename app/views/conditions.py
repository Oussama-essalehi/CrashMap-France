"""Dans quelles conditions ?: severity by condition, speed x location, multivariate model."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import helpers as h

FACTORS = {
    "Luminosité": "lum_label",
    "Conditions météo": "atm_label",
    "État de la surface": "surf_label",
    "Catégorie de route": "catr_label",
    "Vitesse maximale autorisée": "vma_band",
    "Type d'intersection": "int_label",
    "Tracé de la route": "plan_label",
    "Type de collision": "col_label",
}


def render() -> None:
    f: h.Filters = st.session_state["filters"]
    acc = h.apply_filters(h.load_accidents(), f)
    st.title("Dans quelles conditions ?")
    st.caption(f"Sélection : {f.describe()} · {h.fr(len(acc))} accidents")

    label = st.selectbox("Facteur", list(FACTORS), key="cond_factor")
    column = FACTORS[label]
    tbl = h.rate_table(acc, column, f.threshold)
    h.show(h.dot_ci(tbl, column), "cond_dot")
    with st.expander("Voir le tableau"):
        st.dataframe(
            tbl.sort_values("killed_per_100", ascending=False)[[column, "n_accidents", "n_killed", "killed_per_100", "pct_fatal"]]
            .rename(columns={column: label, "n_accidents": "Accidents", "n_killed": "Tués",
                             "killed_per_100": "Tués / 100 acc.", "pct_fatal": "% mortels"}),
            hide_index=True,
            column_config={"Accidents": st.column_config.NumberColumn(format="localized"),
                           "Tués": st.column_config.NumberColumn(format="localized"),
                           "Tués / 100 acc.": st.column_config.NumberColumn(format="%.2f"),
                           "% mortels": st.column_config.NumberColumn(format="%.1f")})

    st.subheader("Vitesse autorisée et localisation")
    fig = go.Figure()
    for color, (flag, name) in zip((h.BLUE, h.ORANGE), ((True, "En agglomération"), (False, "Hors agglomération"))):
        sub = acc[acc["in_town"].fillna(not flag).astype(bool) == flag]
        rt = h.rate_table(sub, "vma_band", f.threshold).dropna(subset=["pct_fatal"])
        rt = rt.set_index("vma_band").reindex(h.SPEED_BANDS).dropna(subset=["pct_fatal"]).reset_index()
        fig.add_scatter(x=rt["vma_band"], y=rt["pct_fatal"], mode="lines+markers", name=name,
                        line=dict(color=color, width=2), marker=dict(size=9),
                        error_y=dict(type="data", symmetric=False, array=rt["ci_high"] - rt["pct_fatal"],
                                     arrayminus=rt["pct_fatal"] - rt["ci_low"], color=color),
                        hovertemplate=name + "<br>%{x} : %{y:.1f} % d'accidents mortels<extra></extra>")
    fig.update_yaxes(title_text="% d'accidents mortels (IC 95 % Wilson)", rangemode="tozero")
    fig.update_layout(height=380)
    h.show(fig, "cond_speed")

    st.subheader("Quels facteurs comptent vraiment ? (à autres facteurs égaux)")
    st.markdown(
        "Une régression logistique sur 322 020 accidents (2019-2024, France entière) mesure l'effet de chaque "
        "facteur **en tenant compte des autres**. Un *odds ratio* de 2 signifie que la cote d'un accident mortel "
        "est doublée par rapport à la modalité de référence. Ces résultats portent sur toute la période et "
        "ne suivent pas les filtres.")
    path = h.DATA / "odds_ratios.csv"
    if path.exists():
        ors = pd.read_csv(path)
        ors = ors[ors["n_accidents"] >= 500].copy()
        ors["label"] = ors["variable_label"] + " : " + ors["level"] + " (réf. " + ors["reference"] + ")"
        ors = ors.sort_values("odds_ratio")
        colors = np.where(ors["ci_low"] > 1, h.RED, np.where(ors["ci_high"] < 1, h.BLUE, h.GREY))
        fig = go.Figure(go.Scatter(
            x=ors["odds_ratio"], y=ors["label"], mode="markers", marker=dict(size=9, color=colors),
            error_x=dict(type="data", symmetric=False, array=ors["ci_high"] - ors["odds_ratio"],
                         arrayminus=ors["odds_ratio"] - ors["ci_low"], color=h.TEXT_SECONDARY),
            hovertemplate="%{y}<br>odds ratio %{x:.2f}<extra></extra>"))
        fig.add_vline(x=1, line=dict(color=h.TEXT_SECONDARY, width=1))
        ticks = [0.3, 0.5, 0.7, 1, 1.5, 2, 3, 5, 7]
        fig.update_xaxes(type="log", tickvals=ticks, ticktext=[str(t).replace(".", ",") for t in ticks],
                         title_text="Odds ratio (échelle log) - rouge : aggravant, bleu : protecteur, gris : non significatif")
        fig.update_layout(height=900, showlegend=False)
        h.show(fig, "cond_odds")
    h.small_sample_note(f.threshold)
