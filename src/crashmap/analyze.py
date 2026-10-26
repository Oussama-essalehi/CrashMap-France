"""Descriptive and inferential analysis: rates with Wilson intervals, chi-square + Cramér's V,
victim-level severity, safety equipment, trends, departments. Writes CSV tables to
``reports/tables/``, headline numbers to ``reports/key_numbers.json`` and PNG figures to
``reports/figures/``.

Rates
    * ``killed_per_100`` = deaths / accidents x 100 (an accident can have several deaths);
    * ``pct_fatal`` = share of accidents with at least one death, a proportion, so it gets a
      Wilson 95 % confidence interval.
Every rate is blank when the group has fewer than ``analysis.min_accidents_for_rate`` accidents.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import chi2_contingency
from statsmodels.stats.proportion import proportion_confint

from crashmap import codebook, viz
from crashmap.config import ROOT, get_paths, load_config, min_accidents

log = logging.getLogger(__name__)

TABLES_DIR = ROOT / "reports" / "tables"
SOURCE = "Source : ONISR, accidents corporels 2019-2024 (data.gouv.fr) - traitement CrashMap France"

FACTORS = {
    "time_band": "Tranche horaire",
    "weekday": "Jour de la semaine",
    "lum_label": "Luminosité",
    "atm_label": "Conditions météo",
    "surf_label": "État de la surface",
    "catr_label": "Catégorie de route",
    "vma_band": "Vitesse maximale autorisée",
    "plan_label": "Tracé",
    "int_label": "Type d'intersection",
    "in_town_label": "Localisation",
    "col_label": "Type de collision",
    "weekend_label": "Semaine / week-end",
    "two_wheeler_label": "Deux-roues ou EDP impliqué",
    "pedestrian_label": "Piéton impliqué",
    "vehicles_label": "Nombre de véhicules",
}


# --------------------------------------------------------------------------------------------
# Statistics helpers
# --------------------------------------------------------------------------------------------

def wilson_ci(successes: pd.Series | int, n: pd.Series | int, alpha: float = 0.05) -> tuple[Any, Any]:
    """Wilson score interval for a proportion (vectorised), in %."""
    low, high = proportion_confint(successes, n, alpha=alpha, method="wilson")
    return np.asarray(low) * 100, np.asarray(high) * 100


def cramers_v(table: pd.DataFrame) -> tuple[float, float, int, float]:
    """Chi-square test of independence and Cramér's V for a contingency table.

    Returns (chi2, p_value, dof, V). V = sqrt(chi2 / (n * (min(rows, cols) - 1))).
    """
    chi2, p, dof, _ = chi2_contingency(table, correction=False)
    n = table.to_numpy().sum()
    k = min(table.shape) - 1
    return float(chi2), float(p), int(dof), float(np.sqrt(chi2 / (n * k))) if k > 0 else float("nan")


def rate_table(df: pd.DataFrame, by: str | list[str], min_n: int | None = None) -> pd.DataFrame:
    """Accidents, deaths, deaths per 100 accidents and % fatal accidents (Wilson CI) per group."""
    min_n = min_accidents() if min_n is None else min_n
    g = df.dropna(subset=[by] if isinstance(by, str) else by).groupby(by, observed=True)
    out = g.agg(n_accidents=("accident_id", "size"), n_killed=("n_killed", "sum"),
                n_fatal=("fatal", "sum")).reset_index()
    enough = out["n_accidents"] >= min_n
    out["killed_per_100"] = (out["n_killed"] / out["n_accidents"] * 100).round(2).where(enough)
    out["pct_fatal"] = (out["n_fatal"] / out["n_accidents"] * 100).round(2).where(enough)
    low, high = wilson_ci(out["n_fatal"], out["n_accidents"])
    out["pct_fatal_ci_low"] = pd.Series(low, index=out.index).round(2).where(enough)
    out["pct_fatal_ci_high"] = pd.Series(high, index=out.index).round(2).where(enough)
    return out


def share_table(df: pd.DataFrame, by: str | list[str], flag: str, min_n: int | None = None) -> pd.DataFrame:
    """Persons, number and % with ``flag`` (Wilson CI) per group, for victim-level tables."""
    min_n = min_accidents() if min_n is None else min_n
    sub = df.dropna(subset=[by] if isinstance(by, str) else by)
    sub = sub[sub[flag].notna()]
    g = sub.groupby(by, observed=True)
    out = g.agg(n_persons=(flag, "size"), n_flag=(flag, "sum"),
                n_accidents=("accident_id", "nunique")).reset_index()
    out["n_flag"] = out["n_flag"].astype(int)
    enough = out["n_accidents"] >= min_n
    out["pct"] = (out["n_flag"] / out["n_persons"] * 100).round(2).where(enough)
    low, high = wilson_ci(out["n_flag"], out["n_persons"])
    out["ci_low"] = pd.Series(low, index=out.index).round(2).where(enough)
    out["ci_high"] = pd.Series(high, index=out.index).round(2).where(enough)
    return out


# --------------------------------------------------------------------------------------------
# Data preparation
# --------------------------------------------------------------------------------------------

def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    paths = get_paths()
    acc = pd.read_parquet(paths.processed / "accidents.parquet")
    vic = pd.read_parquet(paths.processed / "victims.parquet")
    deps = pd.read_parquet(paths.processed / "departments.parquet")
    acc = add_analysis_labels(acc)
    return acc, vic, deps


def add_analysis_labels(acc: pd.DataFrame) -> pd.DataFrame:
    """Readable labels for boolean / numeric factors (missing stays missing)."""
    acc = acc.copy()
    acc["in_town_label"] = acc["in_town"].map({True: "En agglomération", False: "Hors agglomération"})
    acc["weekend_label"] = acc["is_weekend"].map({True: "Week-end", False: "Semaine"})
    acc["two_wheeler_label"] = acc["two_wheeler_involved"].map({True: "Oui", False: "Non"})
    acc["pedestrian_label"] = acc["pedestrian_involved"].map({True: "Oui", False: "Non"})
    acc["vehicles_label"] = pd.cut(acc["n_vehicles"], bins=[0, 1, 2, np.inf],
                                   labels=["1 véhicule", "2 véhicules", "3 véhicules et +"]).astype("string")
    return acc


# --------------------------------------------------------------------------------------------
# Analyses
# --------------------------------------------------------------------------------------------

def factor_tables(acc: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {col: rate_table(acc, col) for col in FACTORS}


def chi_square_tests(acc: pd.DataFrame) -> pd.DataFrame:
    """Chi-square + Cramér's V between each factor and the fatal indicator."""
    rows = []
    for col, label in FACTORS.items():
        sub = acc[[col, "fatal"]].dropna()
        table = pd.crosstab(sub[col], sub["fatal"])
        chi2, p, dof, v = cramers_v(table)
        rows.append({"factor": col, "label": label, "n": len(sub), "levels": table.shape[0],
                     "chi2": round(chi2, 1), "dof": dof, "p_value": p, "cramers_v": round(v, 4)})
    return pd.DataFrame(rows).sort_values("cramers_v", ascending=False).reset_index(drop=True)


def victim_tables(vic: pd.DataFrame) -> dict[str, pd.DataFrame]:
    known = vic[vic["grav"].notna()].copy()
    known["killed_f"] = known["killed"].astype(float)
    known["kh_f"] = known["killed_or_hospitalized"].astype(float)
    by_mode = share_table(known, "user_mode", "killed_f").rename(
        columns={"n_flag": "n_killed", "pct": "pct_killed", "ci_low": "pct_killed_ci_low", "ci_high": "pct_killed_ci_high"})
    kh = share_table(known, "user_mode", "kh_f")[["user_mode", "n_flag", "pct"]].rename(
        columns={"n_flag": "n_killed_or_hosp", "pct": "pct_killed_or_hosp"})
    by_mode = by_mode.merge(kh, on="user_mode").sort_values("n_killed", ascending=False)
    by_catu = share_table(known, "catu_label", "killed_f")
    by_age_sex = share_table(known, ["age_band", "sexe_label"], "killed_f")
    by_age = share_table(known, "age_band", "killed_f")
    return {"victims_by_mode": by_mode, "victims_by_user_category": by_catu,
            "victims_by_age_sex": by_age_sex, "victims_by_age": by_age}


EQUIPMENT_GROUPS = [
    # (label, filter, equipment column, equipment name)
    ("Conducteurs de voiture", lambda v: (v["user_mode"] == "Voiture (VL)") & (v["catu"] == 1), "seatbelt_worn", "Ceinture"),
    ("Passagers de voiture", lambda v: (v["user_mode"] == "Voiture (VL)") & (v["catu"] == 2), "seatbelt_worn", "Ceinture"),
    ("Conducteurs de moto > 125 cm3", lambda v: (v["user_mode"] == "Moto > 125 cm3") & (v["catu"] == 1), "helmet_worn", "Casque"),
    ("Conducteurs de moto 50-125 cm3", lambda v: (v["user_mode"] == "Moto 50-125 cm3") & (v["catu"] == 1), "helmet_worn", "Casque"),
    ("Conducteurs de cyclomoteur", lambda v: (v["user_mode"] == "Cyclomoteur <= 50 cm3") & (v["catu"] == 1), "helmet_worn", "Casque"),
    ("Cyclistes", lambda v: (v["user_mode"] == "Vélo (y.c. VAE)") & (v["catu"] == 1), "helmet_worn", "Casque"),
    ("Conducteurs d'EDP motorisé", lambda v: (v["user_mode"] == "EDP motorisé (trottinette...)") & (v["catu"] == 1), "helmet_worn", "Casque"),
]


def equipment_table(vic: pd.DataFrame) -> pd.DataFrame:
    """Share killed / killed-or-hospitalized with vs without the equipment, among comparable users."""
    known = vic[vic["grav"].notna() & vic["equipment_known"]].copy()
    rows = []
    for label, mask_fn, col, equipment in EQUIPMENT_GROUPS:
        sub = known[mask_fn(known)]
        for worn in (True, False):
            grp = sub[sub[col] == worn]
            n = len(grp)
            k = int(grp["killed"].sum())
            kh = int(grp["killed_or_hospitalized"].sum())
            n_acc = grp["accident_id"].nunique()
            ok = n_acc >= min_accidents()
            lo, hi = wilson_ci(kh, n) if n else (np.nan, np.nan)
            lo_k, hi_k = wilson_ci(k, n) if n else (np.nan, np.nan)
            rows.append({
                "group": label, "equipment": equipment, "worn": "Porté" if worn else "Non porté",
                "n_persons": n, "n_killed": k, "n_killed_or_hosp": kh,
                "pct_killed": round(k / n * 100, 2) if ok else None,
                "pct_killed_ci_low": round(float(lo_k), 2) if ok else None,
                "pct_killed_ci_high": round(float(hi_k), 2) if ok else None,
                "pct_killed_or_hosp": round(kh / n * 100, 2) if ok else None,
                "ci_low": round(float(lo), 2) if ok else None, "ci_high": round(float(hi), 2) if ok else None,
            })
    out = pd.DataFrame(rows)
    worn = out[out["worn"] == "Porté"].set_index("group")
    not_worn = out[out["worn"] == "Non porté"].set_index("group")
    rr = (not_worn["pct_killed"] / worn["pct_killed"]).round(2)
    out["relative_risk_killed_not_worn"] = out["group"].map(rr)
    return out


def trend_tables(acc: pd.DataFrame, vic: pd.DataFrame) -> dict[str, pd.DataFrame]:
    covid = int(load_config()["analysis"]["covid_year"])
    yearly = acc.groupby("year").agg(n_accidents=("accident_id", "size"), n_killed=("n_killed", "sum"),
                                     n_fatal=("fatal", "sum"), n_hospitalized=("n_hospitalized", "sum")).reset_index()
    yearly["killed_per_100"] = (yearly["n_killed"] / yearly["n_accidents"] * 100).round(2)
    base = yearly.iloc[0]
    yearly["pct_change_killed_vs_first_year"] = ((yearly["n_killed"] / base["n_killed"] - 1) * 100).round(1)
    yearly["pct_change_accidents_vs_first_year"] = ((yearly["n_accidents"] / base["n_accidents"] - 1) * 100).round(1)
    yearly["covid_year"] = yearly["year"] == covid
    monthly = acc.groupby([acc["date"].dt.to_period("M").astype(str)]).agg(
        n_accidents=("accident_id", "size"), n_killed=("n_killed", "sum")).reset_index(names="year_month")
    monthly["killed_rolling_12m"] = monthly["n_killed"].rolling(12).mean().round(1)
    by_mode_year = vic[vic["grav"].notna()].pivot_table(index="user_mode", columns="year", values="killed",
                                                         aggfunc="sum").astype(int)
    return {"trend_yearly": yearly, "trend_monthly": monthly, "trend_killed_by_mode": by_mode_year.reset_index()}


def hour_weekday(acc: pd.DataFrame) -> pd.DataFrame:
    return rate_table(acc, ["day_of_week", "weekday", "hour"])


def department_table(acc: pd.DataFrame, deps: pd.DataFrame) -> pd.DataFrame:
    n_years = acc["year"].nunique()
    g = acc.groupby("dep_code").agg(n_accidents=("accident_id", "size"), n_killed=("n_killed", "sum")).reset_index()
    g = g.merge(deps[["dep_code", "dep_name", "region_name", "zone", "population"]], on="dep_code", how="left")
    ok = g["n_accidents"] >= min_accidents()
    pop = g["population"].astype(float)
    g["killed_per_100k_per_year"] = (g["n_killed"] / n_years / pop * 1e5).round(2).where(ok)
    g["accidents_per_100k_per_year"] = (g["n_accidents"] / n_years / pop * 1e5).round(1).where(ok)
    g["killed_per_100_accidents"] = (g["n_killed"] / g["n_accidents"] * 100).round(2).where(ok)
    g["rank_killed_per_100k"] = g["killed_per_100k_per_year"].rank(ascending=False, method="min")
    return g.sort_values("killed_per_100k_per_year", ascending=False, na_position="last").reset_index(drop=True)


# --------------------------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------------------------

def fig_trend(yearly: pd.DataFrame, path) -> None:
    covid = load_config()["analysis"]["covid_year"]
    colors = [viz.GREY if y == covid else viz.BLUE for y in yearly["year"]]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Accidents corporels", "Personnes tuées"),
                        horizontal_spacing=0.1)
    for col, measure in ((1, "n_accidents"), (2, "n_killed")):
        fig.add_bar(x=yearly["year"].astype(str), y=yearly[measure], marker_color=colors, row=1, col=col,
                    text=yearly[measure].map(lambda v: f"{v:,}".replace(",", " ")), textposition="outside",
                    showlegend=False, cliponaxis=False)
        fig.update_yaxes(rangemode="tozero", row=1, col=col)
    fig.update_layout(title=viz.subtitle("Accidents et tués par an, 2019-2024",
                                         f"2020 en gris : confinements COVID-19, année traitée comme une anomalie. {SOURCE}"))
    viz.save(fig, path)


def fig_hour_weekday(hw: pd.DataFrame, path) -> None:
    z = hw.pivot(index="weekday", columns="hour", values="killed_per_100").reindex(codebook.WEEKDAYS)
    n = hw.pivot(index="weekday", columns="hour", values="n_accidents").reindex(codebook.WEEKDAYS)
    fig = go.Figure(go.Heatmap(
        z=z.values, x=[f"{h}h" for h in z.columns], y=z.index, colorscale=viz.SEQUENTIAL_BLUE,
        colorbar=dict(title="Tués /<br>100 acc."), customdata=n.values, xgap=2, ygap=2,
        hovertemplate="%{y} %{x}<br>%{z:.1f} tués / 100 accidents<br>%{customdata} accidents<extra></extra>"))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_layout(title=viz.subtitle("Gravité selon l'heure et le jour : tués pour 100 accidents",
                                         "Entre minuit et 6h, la gravité est la plus forte, quel que soit le jour. " + SOURCE),
                      margin=dict(l=110))
    viz.save(fig, path, height=520)


def fig_hourly(hourly: pd.DataFrame, path) -> None:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
                        subplot_titles=("Nombre d'accidents par heure", "Tués pour 100 accidents"))
    fig.add_bar(x=hourly["hour"], y=hourly["n_accidents"], marker_color=viz.BLUE, showlegend=False, row=1, col=1)
    fig.add_scatter(x=hourly["hour"], y=hourly["killed_per_100"], mode="lines+markers", line=dict(color=viz.ORANGE, width=2),
                    marker=dict(size=8), showlegend=False, row=2, col=1)
    fig.update_xaxes(tickmode="array", tickvals=list(range(24)), ticktext=[f"{h}h" for h in range(24)], row=2, col=1)
    fig.update_yaxes(rangemode="tozero")
    fig.update_layout(title=viz.subtitle("Moins d'accidents la nuit, mais beaucoup plus graves",
                                         SOURCE))
    viz.save(fig, path, height=680)


def _dot_ci(fig, tbl: pd.DataFrame, label_col: str, row: int, col: int, color: str, name: str | None = None,
            showlegend: bool = False) -> None:
    tbl = tbl.dropna(subset=["pct_fatal"]).sort_values("pct_fatal")
    fig.add_scatter(
        x=tbl["pct_fatal"], y=viz.short(tbl[label_col]), mode="markers", marker=dict(size=10, color=color),
        error_x=dict(type="data", symmetric=False, array=tbl["pct_fatal_ci_high"] - tbl["pct_fatal"],
                     arrayminus=tbl["pct_fatal"] - tbl["pct_fatal_ci_low"], color=color, thickness=2, width=4),
        customdata=tbl[["n_accidents"]].values, name=name, showlegend=showlegend,
        hovertemplate="%{y}: %{x:.1f} % d'accidents mortels<br>%{customdata[0]} accidents<extra></extra>",
        row=row, col=col)


def fig_conditions(tables: dict[str, pd.DataFrame], path) -> None:
    panels = [("lum_label", "Luminosité"), ("atm_label", "Météo"), ("surf_label", "Surface")]
    fig = make_subplots(rows=1, cols=3, subplot_titles=[p[1] for p in panels], horizontal_spacing=0.14)
    for i, (col, _) in enumerate(panels, start=1):
        _dot_ci(fig, tables[col], col, 1, i, viz.BLUE)
    fig.update_xaxes(title_text="% d'accidents mortels (IC 95 % Wilson)", rangemode="tozero")
    fig.update_layout(title=viz.subtitle("Part d'accidents mortels selon les conditions",
                                         f"Groupes de moins de {min_accidents()} accidents masqués. " + SOURCE),
                      margin=dict(l=180))
    viz.save(fig, path, width=1500, height=640)


def fig_road_speed(acc: pd.DataFrame, tables: dict[str, pd.DataFrame], path) -> None:
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Catégorie de route", "Vitesse maximale autorisée"),
                        horizontal_spacing=0.12)
    _dot_ci(fig, tables["catr_label"], "catr_label", 1, 1, viz.BLUE)
    for color, (flag, name) in zip((viz.BLUE, viz.ORANGE), ((True, "En agglomération"), (False, "Hors agglomération"))):
        tbl = rate_table(acc[acc["in_town"] == flag], "vma_band")
        order = {label: i for i, (_, _, label) in enumerate(codebook.SPEED_BANDS)}
        tbl = tbl.dropna(subset=["pct_fatal"]).sort_values("vma_band", key=lambda s: s.map(order))
        fig.add_scatter(x=tbl["vma_band"], y=tbl["pct_fatal"], mode="lines+markers", name=name,
                        line=dict(color=color, width=2), marker=dict(size=9, color=color),
                        error_y=dict(type="data", symmetric=False, array=tbl["pct_fatal_ci_high"] - tbl["pct_fatal"],
                                     arrayminus=tbl["pct_fatal"] - tbl["pct_fatal_ci_low"], color=color),
                        row=1, col=2)
    fig.update_xaxes(title_text="% d'accidents mortels", row=1, col=1, rangemode="tozero")
    fig.update_yaxes(title_text="% d'accidents mortels", row=1, col=2, rangemode="tozero")
    fig.update_layout(title=viz.subtitle("Route et vitesse : hors agglomération, la gravité explose",
                                         "IC 95 % Wilson. " + SOURCE), margin=dict(l=200, t=130),
                      legend=dict(x=0.6, y=1.08, xanchor="left"))
    viz.save(fig, path, width=1500, height=600)


def fig_cramers_v(chi: pd.DataFrame, path) -> None:
    tbl = chi.sort_values("cramers_v")
    fig = go.Figure(go.Bar(x=tbl["cramers_v"], y=tbl["label"], orientation="h", marker_color=viz.BLUE,
                           text=tbl["cramers_v"].map(lambda v: f"{v:.3f}".replace(".", ",")), textposition="outside",
                           cliponaxis=False))
    fig.update_xaxes(title_text="V de Cramér (lien avec « accident mortel »)", rangemode="tozero")
    fig.update_layout(title=viz.subtitle("Quels facteurs sont le plus liés à la mortalité ?",
                                         "Khi-deux : tous significatifs (p < 0,001) vu la taille de l'échantillon ; "
                                         "la taille d'effet (V) permet de les classer."), margin=dict(l=220))
    viz.save(fig, path, height=640)


def fig_user_mode(by_mode: pd.DataFrame, path) -> None:
    tbl = by_mode[by_mode["n_killed"] >= 50].sort_values("n_killed")
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.04,
                        subplot_titles=("Personnes tuées (2019-2024)", "% de tués parmi les personnes impliquées"))
    fig.add_bar(x=tbl["n_killed"], y=tbl["user_mode"], orientation="h", marker_color=viz.BLUE, showlegend=False,
                text=tbl["n_killed"].map(lambda v: f"{v:,}".replace(",", " ")), textposition="outside", cliponaxis=False,
                row=1, col=1)
    fig.add_scatter(x=tbl["pct_killed"], y=tbl["user_mode"], mode="markers", marker=dict(size=10, color=viz.ORANGE),
                    error_x=dict(type="data", symmetric=False, array=tbl["pct_killed_ci_high"] - tbl["pct_killed"],
                                 arrayminus=tbl["pct_killed"] - tbl["pct_killed_ci_low"], color=viz.ORANGE),
                    showlegend=False, row=1, col=2)
    fig.update_xaxes(rangemode="tozero")
    fig.update_layout(title=viz.subtitle("Qui meurt sur la route ? Mode de déplacement des victimes",
                                         "Les piétons sont rattachés au véhicule qui les a heurtés. " + SOURCE),
                      margin=dict(l=230))
    viz.save(fig, path, width=1400, height=620)


def fig_age_sex(age_sex: pd.DataFrame, path) -> None:
    order = [label for _, _, label in codebook.AGE_BANDS]
    fig = go.Figure()
    for color, sex in zip((viz.BLUE, viz.ORANGE), ("Masculin", "Féminin")):
        tbl = age_sex[age_sex["sexe_label"] == sex].set_index("age_band").reindex(order)
        fig.add_bar(x=order, y=tbl["n_flag"], name="Hommes" if sex == "Masculin" else "Femmes", marker_color=color)
    fig.update_yaxes(title_text="Personnes tuées (2019-2024)")
    fig.update_layout(barmode="group", title=viz.subtitle("Tués par âge et par sexe",
                                                          "Personnes dont l'âge et le sexe sont connus. " + SOURCE))
    viz.save(fig, path)


def fig_equipment(eq: pd.DataFrame, path) -> None:
    groups = [g for g, *_ in EQUIPMENT_GROUPS][::-1]
    fig = go.Figure()
    for color, worn in zip((viz.BLUE, viz.ORANGE), ("Porté", "Non porté")):
        tbl = eq[(eq["worn"] == worn) & eq["pct_killed"].notna()].set_index("group").reindex(groups).dropna(subset=["pct_killed"])
        labels = tbl.index + " (" + tbl["equipment"].str.lower() + ")"
        fig.add_bar(y=labels, x=tbl["pct_killed"], name=f"Équipement {worn.lower()}", orientation="h",
                    marker_color=color,
                    error_x=dict(type="data", symmetric=False, array=tbl["pct_killed_ci_high"] - tbl["pct_killed"],
                                 arrayminus=tbl["pct_killed"] - tbl["pct_killed_ci_low"], color=viz.TEXT_SECONDARY))
    fig.update_xaxes(title_text="% de tués parmi les usagers impliqués (IC 95 % Wilson)", rangemode="tozero")
    fig.update_layout(barmode="group", margin=dict(l=330), legend=dict(traceorder="normal"),
                      title=viz.subtitle("Équipement de sécurité et risque d'être tué, à catégorie d'usager égale",
                                         "Usagers dont l'équipement est connu. Association, pas causalité. " + SOURCE))
    viz.save(fig, path, width=1300, height=680)


def fig_departments(dep: pd.DataFrame, path, top: int = 15) -> None:
    tbl = dep.dropna(subset=["killed_per_100k_per_year"])
    tbl = tbl[tbl["zone"] != "Outre-mer (COM)"].head(top).sort_values("killed_per_100k_per_year")
    total_pop = dep.loc[dep["population"].notna() & (dep["zone"] != "Outre-mer (COM)"), "population"].sum()
    total_killed = dep.loc[dep["population"].notna() & (dep["zone"] != "Outre-mer (COM)"), "n_killed"].sum()
    national = total_killed / 6 / total_pop * 1e5
    colors = [viz.ORANGE if z != "Métropole" else viz.BLUE for z in tbl["zone"]]
    fig = go.Figure(go.Bar(x=tbl["killed_per_100k_per_year"], y=tbl["dep_name"] + " (" + tbl["dep_code"] + ")",
                           orientation="h", marker_color=colors, showlegend=False,
                           text=tbl["killed_per_100k_per_year"].map(lambda v: f"{v:.1f}".replace(".", ",")),
                           textposition="outside", cliponaxis=False))
    fig.add_vline(x=national, line=dict(color=viz.TEXT_SECONDARY, width=1))
    fig.add_annotation(x=national, y=-0.02, yref="paper", yanchor="top", xanchor="left",
                       text=f" France (dép. avec population) : {national:.1f}".replace(".", ","),
                       showarrow=False, font=dict(color=viz.TEXT_SECONDARY, size=12))
    fig.update_xaxes(title_text="Tués pour 100 000 habitants par an (moyenne 2019-2024)", rangemode="tozero")
    fig.update_layout(title=viz.subtitle(f"Les {top} départements les plus touchés (tués / 100 000 hab.)",
                                         "Orange : départements d'outre-mer. Population INSEE 2023. " + SOURCE),
                      margin=dict(l=230))
    viz.save(fig, path, height=640)


# --------------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------------

def key_numbers(acc, vic, factors, chi, eq, trend, dep) -> dict[str, Any]:
    y = trend["trend_yearly"].set_index("year")
    last = int(y.index.max())
    night = factors["time_band"].set_index("time_band")
    town = factors["in_town_label"].set_index("in_town_label")
    ped = factors["pedestrian_label"].set_index("pedestrian_label")
    two = factors["two_wheeler_label"].set_index("two_wheeler_label")
    km = vic[vic["grav"].notna()]
    killed_by_mode = km.groupby("user_mode")["killed"].sum()
    out_town_killed = acc.loc[acc["in_town"] == False, "n_killed"].sum()  # noqa: E712
    return {
        "years": [int(y.index.min()), last],
        "accidents_total": int(len(acc)),
        "killed_total": int(acc["n_killed"].sum()),
        "accidents_by_year": {int(k): int(v) for k, v in y["n_accidents"].items()},
        "killed_by_year": {int(k): int(v) for k, v in y["n_killed"].items()},
        "killed_change_last_vs_first_pct": float(y.loc[last, "pct_change_killed_vs_first_year"]),
        "killed_per_100_overall": round(acc["n_killed"].sum() / len(acc) * 100, 2),
        "killed_per_100_night_band": float(night.loc["Nuit (21h-6h)", "killed_per_100"]),
        "killed_per_100_day_band": float(night.loc["Journée (10h-17h)", "killed_per_100"]),
        "share_accidents_night_band_pct": round(night.loc["Nuit (21h-6h)", "n_accidents"] / len(acc) * 100, 1),
        "share_killed_night_band_pct": round(night.loc["Nuit (21h-6h)", "n_killed"] / acc["n_killed"].sum() * 100, 1),
        "killed_per_100_out_of_town": float(town.loc["Hors agglomération", "killed_per_100"]),
        "killed_per_100_in_town": float(town.loc["En agglomération", "killed_per_100"]),
        "share_accidents_out_of_town_pct": round(town.loc["Hors agglomération", "n_accidents"] / len(acc) * 100, 1),
        "share_killed_out_of_town_pct": round(out_town_killed / acc["n_killed"].sum() * 100, 1),
        "killed_per_100_pedestrian_involved": float(ped.loc["Oui", "killed_per_100"]),
        "killed_per_100_two_wheeler_involved": float(two.loc["Oui", "killed_per_100"]),
        "top_cramers_v": chi.head(5)[["label", "cramers_v"]].to_dict("records"),
        "killed_by_mode": {k: int(v) for k, v in killed_by_mode.sort_values(ascending=False).items()},
        "share_killed_car_pct": round(killed_by_mode.get("Voiture (VL)", 0) / killed_by_mode.sum() * 100, 1),
        "share_killed_motorbike_pct": round(killed_by_mode[[m for m in killed_by_mode.index if m.startswith("Moto") or m.startswith("Cyclomoteur")]].sum() / killed_by_mode.sum() * 100, 1),
        "share_killed_pedestrian_pct": round(killed_by_mode.get("Piéton", 0) / killed_by_mode.sum() * 100, 1),
        "share_killed_men_pct": round(km.loc[km["sexe_label"] == "Masculin", "killed"].sum() / km.loc[km["sexe_label"].notna(), "killed"].sum() * 100, 1),
        "equipment": eq[["group", "worn", "n_persons", "pct_killed", "pct_killed_or_hosp", "relative_risk_killed_not_worn"]].to_dict("records"),
        "top_departments_killed_per_100k": dep.dropna(subset=["killed_per_100k_per_year"]).head(10)[
            ["dep_code", "dep_name", "zone", "killed_per_100k_per_year", "n_accidents"]].to_dict("records"),
        "bottom_departments_killed_per_100k": dep.dropna(subset=["killed_per_100k_per_year"]).tail(5)[
            ["dep_code", "dep_name", "zone", "killed_per_100k_per_year", "n_accidents"]].to_dict("records"),
    }


def main() -> None:
    paths = get_paths()
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    acc, vic, deps = load_data()

    factors = factor_tables(acc)
    for col, tbl in factors.items():
        tbl.to_csv(TABLES_DIR / f"rates_by_{col.replace('_label', '')}.csv", index=False)
    chi = chi_square_tests(acc)
    chi.to_csv(TABLES_DIR / "chi2_cramers_v.csv", index=False)
    victims = victim_tables(vic)
    for name, tbl in victims.items():
        tbl.to_csv(TABLES_DIR / f"{name}.csv", index=False)
    eq = equipment_table(vic)
    eq.to_csv(TABLES_DIR / "safety_equipment.csv", index=False)
    trend = trend_tables(acc, vic)
    for name, tbl in trend.items():
        tbl.to_csv(TABLES_DIR / f"{name}.csv", index=False)
    hw = hour_weekday(acc)
    hw.to_csv(TABLES_DIR / "hour_weekday.csv", index=False)
    hourly = rate_table(acc, "hour")
    hourly.to_csv(TABLES_DIR / "rates_by_hour.csv", index=False)
    dep = department_table(acc, deps)
    dep.to_csv(TABLES_DIR / "departments.csv", index=False)

    numbers = key_numbers(acc, vic, factors, chi, eq, trend, dep)
    (ROOT / "reports" / "key_numbers.json").write_text(json.dumps(numbers, indent=2, ensure_ascii=False, default=float),
                                                      encoding="utf-8")

    fig_dir = paths.figures
    fig_trend(trend["trend_yearly"], fig_dir / "fig01_trend_yearly.png")
    fig_hour_weekday(hw, fig_dir / "fig02_hour_weekday_heatmap.png")
    fig_hourly(hourly, fig_dir / "fig03_hourly_severity.png")
    fig_conditions(factors, fig_dir / "fig04_conditions.png")
    fig_road_speed(acc, factors, fig_dir / "fig05_road_speed.png")
    fig_cramers_v(chi, fig_dir / "fig06_cramers_v.png")
    fig_user_mode(victims["victims_by_mode"], fig_dir / "fig08_user_mode.png")
    fig_age_sex(victims["victims_by_age_sex"], fig_dir / "fig09_age_sex.png")
    fig_equipment(eq, fig_dir / "fig10_safety_equipment.png")
    fig_departments(dep, fig_dir / "fig11_departments.png")
    log.info("Analysis done: tables in %s", TABLES_DIR.relative_to(ROOT))


if __name__ == "__main__":
    from crashmap.config import setup_logging

    setup_logging()
    main()
