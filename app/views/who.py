"""Qui ? / Who?: travel mode, age and sex, safety equipment (person grain)."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import helpers as h
from i18n import num, t, tv

# (label key, travel mode, user category, equipment column)
EQUIPMENT_GROUPS = [
    ("eq_car_drivers", "Voiture (VL)", "Conducteur", "seatbelt_worn"),
    ("eq_car_passengers", "Voiture (VL)", "Passager", "seatbelt_worn"),
    ("eq_moto_big", "Moto > 125 cm3", "Conducteur", "helmet_worn"),
    ("eq_moto_mid", "Moto 50-125 cm3", "Conducteur", "helmet_worn"),
    ("eq_moped", "Cyclomoteur <= 50 cm3", "Conducteur", "helmet_worn"),
    ("eq_cyclists", "Vélo (y.c. VAE)", "Conducteur", "helmet_worn"),
    ("eq_edp", "EDP motorisé (trottinette...)", "Conducteur", "helmet_worn"),
]


def equipment_table(vic: pd.DataFrame, threshold: int) -> pd.DataFrame:
    rows = []
    known = vic[vic["equipment_known"].fillna(False).astype(bool)]
    for key, mode, catu, column in EQUIPMENT_GROUPS:
        sub = known[(known["user_mode"] == mode) & (known["catu_label"] == catu)]
        for worn in (True, False):
            grp = sub[sub[column].fillna(not worn).astype(bool) == worn]
            n, k = len(grp), int(grp["killed"].sum())
            ok = grp["accident_id"].nunique() >= max(threshold, 1)
            low, high = h.wilson(k, n) if n else (float("nan"), float("nan"))
            rows.append({"group": key, "worn": worn, "n": n, "killed": k,
                         "pct": k / n * 100 if ok and n else None,
                         "ci_low": float(low) if ok else None, "ci_high": float(high) if ok else None})
    return pd.DataFrame(rows)


def render() -> None:
    f: h.Filters = st.session_state["filters"]
    vic = h.apply_filters(h.load_victims(), f)
    st.title(t("who_title"))
    st.caption(t("who_caption", desc=f.describe(), n=num(len(vic))))
    vic = vic.assign(killed_f=vic["killed"].astype(float))

    st.subheader(t("travel_mode"))
    by_mode = h.share_table(vic, "user_mode", "killed_f", f.threshold)
    by_mode = by_mode[by_mode["n_flag"] >= 1].sort_values("n_flag")
    left, right = st.columns(2)
    with left:
        fig = go.Figure(go.Bar(x=by_mode["n_flag"], y=[tv(m) for m in by_mode["user_mode"].astype(str)],
                               orientation="h", marker_color=h.color("blue"), text=[num(v) for v in by_mode["n_flag"]],
                               textposition="outside", cliponaxis=False, hovertemplate="%{y} : %{x:,}<extra></extra>"))
        fig.update_xaxes(range=[0, by_mode["n_flag"].max() * 1.15 if len(by_mode) else 1])
        fig.update_layout(height=520, title=dict(text=t("people_killed"), font=dict(size=14)))
        h.show(fig, "who_mode_count")
    with right:
        fig = h.dot_ci(by_mode, "user_mode", value="pct", color_name="orange", x_title=t("risk_axis"), height=520)
        fig.update_layout(title=dict(text=t("risk_title"), font=dict(size=14)))
        h.show(fig, "who_mode_rate")
    st.caption(t("mode_note"))

    st.subheader(t("age_sex"))
    age = vic[vic["age_band"].notna() & vic["sexe_label"].notna()]
    counts = age.groupby(["age_band", "sexe_label"], observed=True)["killed"].sum().unstack().reindex(h.AGE_BANDS)
    fig = go.Figure()
    for color_name, (sex, key) in zip(("blue", "orange"), (("Masculin", "men"), ("Féminin", "women"))):
        if sex in counts:
            fig.add_bar(x=[tv(a) for a in counts.index], y=counts[sex], name=t(key), marker_color=h.color(color_name),
                        hovertemplate=t(key) + " %{x} : %{y:,}<extra></extra>")
    fig.update_layout(barmode="group", height=380, yaxis_title=t("killed_axis"))
    h.show(fig, "who_age_sex")
    rate_age = h.share_table(age, "age_band", "killed_f", f.threshold).set_index("age_band").reindex(h.AGE_BANDS)
    if rate_age["pct"].notna().any():
        st.markdown(t("age_note", young=num(rate_age.loc["25-34 ans", "pct"], 1),
                      old=num(rate_age.loc["75 ans et +", "pct"], 1)))

    st.subheader(t("equipment"))
    eq = equipment_table(vic, f.threshold)
    groups = [g[0] for g in EQUIPMENT_GROUPS][::-1]
    fig = go.Figure()
    for color_name, worn, key in (("blue", True, "worn"), ("orange", False, "not_worn")):
        sub = eq[eq["worn"] == worn].set_index("group").reindex(groups).dropna(subset=["pct"])
        fig.add_bar(y=[t(g) for g in sub.index], x=sub["pct"], name=t(key), orientation="h",
                    marker_color=h.color(color_name),
                    error_x=dict(type="data", symmetric=False, array=sub["ci_high"] - sub["pct"],
                                 arrayminus=sub["pct"] - sub["ci_low"], color=h.color("text_secondary")),
                    customdata=sub["n"],
                    hovertemplate="%{y}<br>%{x:.1f} % " + t("eq_hover") + " %{customdata:,} " + t("people")
                                  + "<extra></extra>")
    fig.update_xaxes(title_text=t("eq_axis"), rangemode="tozero")
    fig.update_layout(barmode="group", height=500, legend=dict(traceorder="normal"))
    h.show(fig, "who_equipment")
    st.info(t("eq_note"))
    h.small_sample_note(f.threshold)
