"""Vue d'ensemble: KPIs, trend by year, monthly pattern."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import helpers as h


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

    st.title("CrashMap France")
    st.markdown("**Où, quand et dans quelles conditions se produisent les accidents de la route les plus graves "
                "en France ?** Analyse des accidents corporels recensés par l'ONISR de 2019 à 2024.")
    st.caption(f"Sélection : {f.describe()} · {h.fr(len(acc))} accidents")

    k = kpis(acc, f)
    delta = {}
    if f.years[0] == f.years[1] and f.years[0] > int(acc_all["year"].min()):
        prev_f = h.Filters((f.years[0] - 1, f.years[0] - 1), f.regions, f.departments, f.localisation, f.threshold)
        prev = kpis(h.apply_filters(acc_all, prev_f), prev_f)
        if prev["accidents"]:
            delta["accidents"] = (k["accidents"] / prev["accidents"] - 1) * 100
        if prev["killed"]:
            delta["killed"] = (k["killed"] / prev["killed"] - 1) * 100

    cols = st.columns(6)
    cols[0].metric("Accidents", h.fr(k["accidents"]),
                   h.fr(delta.get("accidents"), 1, " % vs N-1") if "accidents" in delta else None, delta_color="inverse")
    cols[1].metric("Tués", h.fr(k["killed"]),
                   h.fr(delta.get("killed"), 1, " % vs N-1") if "killed" in delta else None, delta_color="inverse")
    cols[2].metric("Tués pour 100 accidents", h.fr(k["killed_per_100"], 2))
    cols[3].metric("Tués / 100 000 hab. / an", h.fr(k["killed_per_100k"], 1),
                   help="Population INSEE 2023 des départements sélectionnés ; moyenne annuelle.")
    cols[4].metric("Part d'accidents de nuit", h.fr(k["night_share"], 1, " %"), help="Entre 21h et 6h.")
    cols[5].metric("Tués hors agglomération", h.fr(k["out_of_town_killed"], 1, " %"),
                   help="Part des tués dans des accidents hors agglomération.")

    st.subheader("Évolution par année")
    yearly = acc.groupby("year").agg(accidents=("accident_id", "size"), killed=("n_killed", "sum")).reset_index()
    colors = [h.GREY if y == h.COVID_YEAR else h.BLUE for y in yearly["year"]]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Accidents corporels", "Personnes tuées"), horizontal_spacing=0.08)
    for i, col in enumerate(("accidents", "killed"), start=1):
        fig.add_bar(x=yearly["year"].astype(str), y=yearly[col], marker_color=colors, showlegend=False,
                    text=[h.fr(v) for v in yearly[col]], textposition="outside", cliponaxis=False, row=1, col=i,
                    hovertemplate="%{x} : %{y:,}<extra></extra>")
    fig.update_yaxes(rangemode="tozero")
    fig.update_layout(height=360, margin=dict(t=50))
    h.show(fig, "overview_yearly")
    st.caption("En gris : 2020, année des confinements, à ne pas comparer directement aux autres années.")

    st.subheader("Accidents par mois")
    monthly = acc.groupby(["year", "month"]).size().rename("accidents").reset_index()
    fig = go.Figure()
    palette = [h.BLUE, h.ORANGE, h.AQUA, h.YELLOW, "#e87ba4", "#008300", "#6250d6", h.RED]
    for i, (year, grp) in enumerate(monthly.groupby("year")):
        fig.add_scatter(x=[h.MONTHS[m - 1] for m in grp["month"]], y=grp["accidents"], mode="lines+markers",
                        name=str(year), line=dict(width=2, color=palette[i % len(palette)],
                                                  dash="dot" if year == h.COVID_YEAR else "solid"),
                        hovertemplate=f"{year} %{{x}} : %{{y:,}} accidents<extra></extra>")
    fig.update_yaxes(rangemode="tozero", title_text="Accidents")
    fig.update_layout(height=380)
    h.show(fig, "overview_monthly")

    with st.container(border=True):
        st.markdown(
            "**À retenir (France entière, 2019-2024)**\n"
            "- Hors agglomération : **36 %** des accidents mais **67 %** des tués.\n"
            "- La nuit (21h-6h) : **16,5 %** des accidents, **26 %** des tués.\n"
            "- La vitesse maximale autorisée est le facteur le plus lié à la mortalité.\n"
            "- Motards, piétons, cyclistes et seniors sont les usagers les plus exposés.\n"
            "- **3 432 tués en 2024**, -1,9 % seulement par rapport à 2019."
        )
    h.small_sample_note(f.threshold)
