"""Qui ?: travel mode, age and sex, safety equipment (person grain)."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import helpers as h

TWO_WHEELERS = ["Moto > 125 cm3", "Moto 50-125 cm3", "Cyclomoteur <= 50 cm3"]
EQUIPMENT_GROUPS = [
    ("Conducteurs de voiture", "Voiture (VL)", "Conducteur", "seatbelt_worn", "ceinture"),
    ("Passagers de voiture", "Voiture (VL)", "Passager", "seatbelt_worn", "ceinture"),
    ("Conducteurs de moto > 125 cm3", "Moto > 125 cm3", "Conducteur", "helmet_worn", "casque"),
    ("Conducteurs de moto 50-125 cm3", "Moto 50-125 cm3", "Conducteur", "helmet_worn", "casque"),
    ("Conducteurs de cyclomoteur", "Cyclomoteur <= 50 cm3", "Conducteur", "helmet_worn", "casque"),
    ("Cyclistes", "Vélo (y.c. VAE)", "Conducteur", "helmet_worn", "casque"),
    ("Conducteurs d'EDP motorisé", "EDP motorisé (trottinette...)", "Conducteur", "helmet_worn", "casque"),
]


def equipment_table(vic: pd.DataFrame, threshold: int) -> pd.DataFrame:
    rows = []
    known = vic[vic["equipment_known"].fillna(False).astype(bool)]
    for label, mode, catu, column, name in EQUIPMENT_GROUPS:
        sub = known[(known["user_mode"] == mode) & (known["catu_label"] == catu)]
        for worn in (True, False):
            grp = sub[sub[column].fillna(not worn).astype(bool) == worn]
            n, k = len(grp), int(grp["killed"].sum())
            ok = grp["accident_id"].nunique() >= max(threshold, 1)
            low, high = h.wilson(k, n) if n else (float("nan"), float("nan"))
            rows.append({"group": f"{label} ({name})", "worn": "Porté" if worn else "Non porté", "n": n, "killed": k,
                         "pct": k / n * 100 if ok and n else None,
                         "ci_low": float(low) if ok else None, "ci_high": float(high) if ok else None})
    return pd.DataFrame(rows)


def render() -> None:
    f: h.Filters = st.session_state["filters"]
    vic = h.apply_filters(h.load_victims(), f)
    st.title("Qui ?")
    st.caption(f"Sélection : {f.describe()} · {h.fr(len(vic))} personnes impliquées (gravité connue)")
    vic = vic.assign(killed_f=vic["killed"].astype(float))

    st.subheader("Mode de déplacement")
    by_mode = h.share_table(vic, "user_mode", "killed_f", f.threshold)
    by_mode = by_mode[by_mode["n_flag"] >= 1].sort_values("n_flag")
    left, right = st.columns(2)
    with left:
        fig = go.Figure(go.Bar(x=by_mode["n_flag"], y=by_mode["user_mode"].astype(str), orientation="h",
                               marker_color=h.BLUE, text=[h.fr(v) for v in by_mode["n_flag"]], textposition="outside",
                               cliponaxis=False, hovertemplate="%{y} : %{x:,} tués<extra></extra>"))
        fig.update_xaxes(range=[0, by_mode["n_flag"].max() * 1.15])
        fig.update_layout(height=520, title=dict(text="Personnes tuées", font=dict(size=14)))
        h.show(fig, "who_mode_count")
    with right:
        fig = h.dot_ci(by_mode, "user_mode", value="pct", color=h.ORANGE,
                       x_title="% de tués parmi les impliqués (IC 95 %)", height=520)
        fig.update_layout(title=dict(text="Risque d'être tué quand on est impliqué", font=dict(size=14)))
        h.show(fig, "who_mode_rate")
    st.caption("Les piétons sont comptés à part ; les autres usagers selon le véhicule qu'ils occupaient.")

    st.subheader("Âge et sexe")
    age = vic[vic["age_band"].notna() & vic["sexe_label"].notna()]
    counts = age.groupby(["age_band", "sexe_label"], observed=True)["killed"].sum().unstack()
    counts = counts.reindex(h.AGE_BANDS)
    fig = go.Figure()
    for color, (sex, name) in zip((h.BLUE, h.ORANGE), (("Masculin", "Hommes"), ("Féminin", "Femmes"))):
        if sex in counts:
            fig.add_bar(x=counts.index, y=counts[sex], name=name, marker_color=color,
                        hovertemplate=name + " %{x} : %{y:,} tués<extra></extra>")
    fig.update_layout(barmode="group", height=380, yaxis_title="Personnes tuées")
    h.show(fig, "who_age_sex")
    rate_age = h.share_table(age, "age_band", "killed_f", f.threshold).set_index("age_band").reindex(h.AGE_BANDS)
    if rate_age["pct"].notna().any():
        st.markdown(f"Part de tués parmi les personnes impliquées : **{h.fr(rate_age.loc['25-34 ans', 'pct'], 1)} %** "
                    f"chez les 25-34 ans, **{h.fr(rate_age.loc['75 ans et +', 'pct'], 1)} %** chez les 75 ans et plus.")

    st.subheader("Équipement de sécurité")
    eq = equipment_table(vic, f.threshold)
    fig = go.Figure()
    groups = [f"{g[0]} ({g[4]})" for g in EQUIPMENT_GROUPS][::-1]
    for color, worn in zip((h.BLUE, h.ORANGE), ("Porté", "Non porté")):
        sub = eq[eq["worn"] == worn].set_index("group").reindex(groups).dropna(subset=["pct"])
        fig.add_bar(y=sub.index, x=sub["pct"], name=f"Équipement {worn.lower()}", orientation="h", marker_color=color,
                    error_x=dict(type="data", symmetric=False, array=sub["ci_high"] - sub["pct"],
                                 arrayminus=sub["pct"] - sub["ci_low"], color=h.TEXT_SECONDARY),
                    customdata=sub["n"], hovertemplate="%{y}<br>%{x:.1f} % tués sur %{customdata:,} personnes<extra></extra>")
    fig.update_xaxes(title_text="% de tués parmi les usagers impliqués (IC 95 % Wilson)", rangemode="tozero")
    fig.update_layout(barmode="group", height=500, legend=dict(traceorder="normal"))
    h.show(fig, "who_equipment")
    st.info("Association, pas causalité : ne pas porter d'équipement va souvent avec d'autres comportements à "
            "risque, et l'équipement est déclaré après l'accident. Chez les cyclistes, les casqués roulent plus "
            "souvent hors agglomération et plus vite, ce qui explique un taux un peu plus élevé.")
    h.small_sample_note(f.threshold)
