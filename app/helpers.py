"""Data loading, filters, rates and chart style shared by the pages of the web app."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

DATA = Path(__file__).resolve().parent / "data"
REPO_URL = "https://github.com/Oussama-essalehi/CrashMap-France"
SOURCE = "Source : ONISR, accidents corporels 2019-2024 (data.gouv.fr), INSEE 2023"

# Same colour rules as the static figures: categorical hues in a fixed order, single-hue ramps.
BLUE, ORANGE, AQUA, YELLOW, RED, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#d1342b", "#8a8985"
TEXT, TEXT_SECONDARY, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#ffffff"
SEQUENTIAL_BLUE = ["#eef4fc", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SEQUENTIAL_RED = ["#fdf0ee", "#f9d2cc", "#f2a99e", "#e87b6c", "#d1342b", "#a82720", "#7a1b16"]

WEEKDAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MONTHS = ["Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin", "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."]
TIME_BANDS = ["Matin (6h-10h)", "Journée (10h-17h)", "Soirée (17h-21h)", "Nuit (21h-6h)"]
SPEED_BANDS = ["<= 30 km/h", "40-50 km/h", "60-70 km/h", "80-90 km/h", "100-110 km/h", "130 km/h"]
AGE_BANDS = ["0-13 ans", "14-17 ans", "18-24 ans", "25-34 ans", "35-44 ans", "45-54 ans", "55-64 ans",
             "65-74 ans", "75 ans et +"]
COVID_YEAR = 2020

pio.templates["crashmap_web"] = go.layout.Template(layout=go.Layout(
    font=dict(family="Inter, Segoe UI, Arial, sans-serif", size=13, color=TEXT),
    paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, colorway=[BLUE, ORANGE, AQUA, YELLOW, RED],
    xaxis=dict(showgrid=False, zeroline=False, linecolor=GRID, tickfont=dict(color=TEXT_SECONDARY),
               title_font=dict(color=TEXT_SECONDARY)),
    yaxis=dict(gridcolor=GRID, zeroline=False, tickfont=dict(color=TEXT_SECONDARY),
               title_font=dict(color=TEXT_SECONDARY)),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    margin=dict(l=10, r=10, t=40, b=10), separators=", ", hoverlabel=dict(font_size=13),
))
pio.templates.default = "crashmap_web"


# --------------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------------

@st.cache_data(show_spinner="Chargement des données…")
def load_accidents() -> pd.DataFrame:
    return pd.read_parquet(DATA / "accidents.parquet")


@st.cache_data(show_spinner="Chargement des victimes…")
def load_victims() -> pd.DataFrame:
    return pd.read_parquet(DATA / "victims.parquet")


@st.cache_data
def load_departments() -> pd.DataFrame:
    return pd.read_parquet(DATA / "departments.parquet")


@st.cache_data
def load_geojson() -> dict:
    return json.loads((DATA / "departements.geojson").read_text(encoding="utf-8"))


@st.cache_data
def load_hotspots(city: str = "toulouse") -> pd.DataFrame:
    path = DATA / f"hotspots_{city}.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


# --------------------------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------------------------

@dataclass
class Filters:
    years: tuple[int, int]
    regions: list[str]
    departments: list[str]
    localisation: str
    threshold: int

    @property
    def n_years(self) -> int:
        return self.years[1] - self.years[0] + 1

    def describe(self) -> str:
        parts = [f"{self.years[0]}-{self.years[1]}" if self.years[0] != self.years[1] else str(self.years[0])]
        if self.departments:
            parts.append(", ".join(self.departments[:3]) + ("…" if len(self.departments) > 3 else ""))
        elif self.regions:
            parts.append(", ".join(self.regions[:3]) + ("…" if len(self.regions) > 3 else ""))
        else:
            parts.append("France entière")
        if self.localisation != "Toutes":
            parts.append(self.localisation.lower())
        return " · ".join(parts)


def sidebar_filters() -> Filters:
    """Sidebar widgets; values persist across pages through their session-state keys."""
    acc = load_accidents()
    deps = load_departments()
    years = sorted(acc["year"].unique().tolist())
    with st.sidebar:
        st.header("Filtres")
        year_range = st.slider("Années", years[0], years[-1], (years[0], years[-1]), key="f_years")
        regions = st.multiselect("Région", sorted(deps["region_name"].dropna().unique()), key="f_regions",
                                 placeholder="Toutes les régions")
        dep_choices = deps if not regions else deps[deps["region_name"].isin(regions)]
        departments = st.multiselect("Département", sorted(dep_choices["dep_name"].unique()), key="f_deps",
                                     placeholder="Tous les départements")
        localisation = st.radio("Localisation", ["Toutes", "En agglomération", "Hors agglomération"],
                                key="f_loc")
        threshold = st.slider("Seuil minimal d'accidents pour afficher un taux", 0, 1000, 100, step=10,
                              key="f_threshold",
                              help="Sous ce nombre d'accidents, un taux n'est pas affiché : il serait trop instable.")
        st.caption("2020 : année COVID (confinements), à lire comme une anomalie.")
    return Filters(year_range, regions, departments, localisation, threshold)


def apply_filters(df: pd.DataFrame, f: Filters) -> pd.DataFrame:
    """Works on accidents and victims (both carry year, region, department and in-town columns)."""
    mask = df["year"].between(*f.years)
    if f.departments:
        names = load_departments().set_index("dep_name")["dep_code"]
        mask &= df["dep_code"].isin(names.loc[f.departments].tolist())
    elif f.regions:
        mask &= df["region_name"].isin(f.regions)
    if f.localisation == "En agglomération":
        mask &= df["in_town"].fillna(False).astype(bool)
    elif f.localisation == "Hors agglomération":
        mask &= ~df["in_town"].fillna(True).astype(bool)
    return df[mask]


# --------------------------------------------------------------------------------------------
# Rates
# --------------------------------------------------------------------------------------------

def wilson(successes, n, z: float = 1.96):
    """Wilson 95 % interval for a proportion, vectorised, in %."""
    k = np.asarray(successes, dtype=float)
    n = np.asarray(n, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = k / n
        denom = 1 + z**2 / n
        centre = (p + z**2 / (2 * n)) / denom
        half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (centre - half) * 100, (centre + half) * 100


def rate_table(acc: pd.DataFrame, by: str | list[str], threshold: int) -> pd.DataFrame:
    """Accidents, deaths, deaths per 100 accidents and % fatal accidents (Wilson CI) per group.
    Rates are blank (NaN) below the accident threshold."""
    g = acc.groupby(by, observed=True).agg(n_accidents=("accident_id", "size"), n_killed=("n_killed", "sum"),
                                           n_fatal=("fatal", "sum")).reset_index()
    ok = g["n_accidents"] >= max(threshold, 1)
    g["killed_per_100"] = (g["n_killed"] / g["n_accidents"] * 100).where(ok)
    g["pct_fatal"] = (g["n_fatal"] / g["n_accidents"] * 100).where(ok)
    low, high = wilson(g["n_fatal"], g["n_accidents"])
    g["ci_low"] = pd.Series(low, index=g.index).where(ok)
    g["ci_high"] = pd.Series(high, index=g.index).where(ok)
    return g


def share_table(vic: pd.DataFrame, by: str | list[str], flag: str, threshold: int) -> pd.DataFrame:
    """Persons and % with ``flag`` (Wilson CI) per group; blank when the group has too few accidents."""
    sub = vic[vic[flag].notna()]
    g = sub.groupby(by, observed=True).agg(n_persons=(flag, "size"), n_flag=(flag, "sum"),
                                           n_accidents=("accident_id", "nunique")).reset_index()
    ok = g["n_accidents"] >= max(threshold, 1)
    g["pct"] = (g["n_flag"] / g["n_persons"] * 100).where(ok)
    low, high = wilson(g["n_flag"], g["n_persons"])
    g["ci_low"] = pd.Series(low, index=g.index).where(ok)
    g["ci_high"] = pd.Series(high, index=g.index).where(ok)
    return g


def population(f: Filters) -> int:
    """Population (INSEE 2023) of the departments in the selection that have one."""
    deps = load_departments()
    if f.departments:
        deps = deps[deps["dep_name"].isin(f.departments)]
    elif f.regions:
        deps = deps[deps["region_name"].isin(f.regions)]
    return int(deps["population"].dropna().sum())


def with_population(acc: pd.DataFrame) -> pd.DataFrame:
    """Accidents in departments that have an INSEE population (numerator consistent with the denominator)."""
    deps = load_departments()
    return acc[acc["dep_code"].isin(deps.loc[deps["population"].notna(), "dep_code"])]


# --------------------------------------------------------------------------------------------
# Formatting and charts
# --------------------------------------------------------------------------------------------

def fr(value, digits: int = 0, suffix: str = "") -> str:
    """French number formatting (narrow no-break space thousands, decimal comma); '-' when missing."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "-"
    text = f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")
    return text + suffix


def dot_ci(tbl: pd.DataFrame, label: str, value: str = "pct_fatal", color: str = BLUE,
           x_title: str = "% d'accidents mortels (IC 95 % Wilson)", height: int | None = None) -> go.Figure:
    """Horizontal dot plot with Wilson error bars, sorted by value."""
    tbl = tbl.dropna(subset=[value]).sort_values(value)
    fig = go.Figure(go.Scatter(
        x=tbl[value], y=tbl[label].astype(str), mode="markers", marker=dict(size=11, color=color),
        error_x=dict(type="data", symmetric=False, array=tbl["ci_high"] - tbl[value],
                     arrayminus=tbl[value] - tbl["ci_low"], color=color, thickness=2, width=4),
        customdata=np.stack([tbl.get("n_accidents", tbl.get("n_persons")), tbl["ci_low"], tbl["ci_high"]], axis=-1),
        hovertemplate="<b>%{y}</b><br>%{x:.1f} % (IC %{customdata[1]:.1f}-%{customdata[2]:.1f})"
                      "<br>%{customdata[0]:,} cas<extra></extra>"))
    fig.update_xaxes(title_text=x_title, rangemode="tozero")
    fig.update_layout(height=height or max(260, 42 * len(tbl) + 90), showlegend=False)
    return fig


def show(fig: go.Figure, key: str | None = None) -> None:
    """Render with the project template (Streamlit replaces Plotly's default template when it loads)."""
    fig.update_layout(template=pio.templates["crashmap_web"])
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    st.plotly_chart(fig, theme=None, key=key, config={"displaylogo": False, "locale": "fr"})


def small_sample_note(threshold: int) -> None:
    st.caption(f"Taux masqués pour les groupes de moins de {threshold} accidents. {SOURCE}.")
