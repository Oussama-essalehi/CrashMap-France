"""Data loading, filters, rates, theme-aware chart style shared by the pages of the web app."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from i18n import LANGUAGES, default_lang, plotly_separators, t, tv

DATA = Path(__file__).resolve().parent / "data"
REPO_URL = "https://github.com/Oussama-essalehi/CrashMap-France"
COVID_YEAR = 2020
TIME_BANDS = ["Matin (6h-10h)", "Journée (10h-17h)", "Soirée (17h-21h)", "Nuit (21h-6h)"]
SPEED_BANDS = ["<= 30 km/h", "40-50 km/h", "60-70 km/h", "80-90 km/h", "100-110 km/h", "130 km/h"]
AGE_BANDS = ["0-13 ans", "14-17 ans", "18-24 ans", "25-34 ans", "35-44 ans", "45-54 ans", "55-64 ans",
             "65-74 ans", "75 ans et +"]

# Colour slots per theme: categorical hues in a fixed order (validated for colour-vision deficiencies),
# single-hue sequential ramps running from the background colour towards high contrast.
PALETTES = {
    "light": {
        "blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a", "yellow": "#eda100", "magenta": "#e87ba4",
        "green": "#008300", "violet": "#6250d6", "red": "#d1342b", "grey": "#8a8985",
        "text": "#1f2933", "text_secondary": "#52514e", "grid": "#e6e5e1",
        "seq_red": ["#fdf0ee", "#f9d2cc", "#f2a99e", "#e87b6c", "#d1342b", "#a82720", "#7a1b16"],
        "seq_blue": ["#eef4fc", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
        "map_style": "open-street-map", "legend_bg": "rgba(255,255,255,0.85)",
    },
    "dark": {
        "blue": "#3987e5", "orange": "#d95926", "aqua": "#199e70", "yellow": "#c98500", "magenta": "#d55181",
        "green": "#008300", "violet": "#9085e9", "red": "#e66767", "grey": "#8a8985",
        "text": "#e6e9ee", "text_secondary": "#aab2bd", "grid": "#2c3440",
        "seq_red": ["#2b1210", "#4a1a15", "#6e221a", "#96291f", "#c03226", "#e5483a", "#ff6f5e"],
        "seq_blue": ["#0f1e33", "#132c4d", "#183b69", "#1f4f8c", "#2866b5", "#3987e5", "#6fb1ff"],
        "map_style": "carto-darkmatter", "legend_bg": "rgba(15,20,25,0.85)",
    },
}


def theme() -> str:
    """'dark' or 'light', as chosen by the visitor (menu > Settings) or their system."""
    try:
        return "dark" if st.context.theme.type == "dark" else "light"
    except Exception:  # no browser context (tests)
        return "light"


def color(name: str):
    return PALETTES[theme()][name]


def categorical() -> list[str]:
    return [color(c) for c in ("blue", "orange", "aqua", "yellow", "magenta", "green", "violet", "red")]


def template() -> go.layout.Template:
    """Plotly template for the current theme and language (transparent backgrounds)."""
    return go.layout.Template(layout=go.Layout(
        font=dict(family="Inter, Segoe UI, Arial, sans-serif", size=13, color=color("text")),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", colorway=categorical(),
        xaxis=dict(showgrid=False, zeroline=False, linecolor=color("grid"), tickfont=dict(color=color("text_secondary")),
                   title_font=dict(color=color("text_secondary"))),
        yaxis=dict(gridcolor=color("grid"), zeroline=False, tickfont=dict(color=color("text_secondary")),
                   title_font=dict(color=color("text_secondary"))),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color=color("text"))),
        margin=dict(l=10, r=10, t=40, b=10), separators=plotly_separators(), hoverlabel=dict(font_size=13),
        coloraxis=dict(colorbar=dict(tickfont=dict(color=color("text_secondary")))),
    ))


# --------------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_accidents() -> pd.DataFrame:
    return pd.read_parquet(DATA / "accidents.parquet")


@st.cache_data(show_spinner=False)
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


@st.cache_data
def load_odds_ratios() -> pd.DataFrame:
    path = DATA / "odds_ratios.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


# --------------------------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------------------------

@dataclass
class Filters:
    years: tuple[int, int]
    regions: list[str]
    departments: list[str]
    localisation: str  # "all", "in", "out"
    threshold: int

    @property
    def n_years(self) -> int:
        return self.years[1] - self.years[0] + 1

    def describe(self) -> str:
        parts = [f"{self.years[0]}-{self.years[1]}" if self.years[0] != self.years[1] else str(self.years[0])]
        if self.departments:
            parts.append(", ".join(self.departments[:3]) + ("…" if len(self.departments) > 3 else ""))
        elif self.regions:
            parts.append(", ".join(tv(r) for r in self.regions[:3]) + ("…" if len(self.regions) > 3 else ""))
        else:
            parts.append(t("whole_country"))
        if self.localisation != "all":
            parts.append(t(f"loc_{self.localisation}").lower())
        return " · ".join(parts)


def language_selector() -> None:
    """FR / EN switch synced with the URL, so a shared link opens in the right language.

    The bound widget writes its label (?lang=English); the short codes ?lang=en / ?lang=fr are read here.
    """
    code = st.query_params.get("lang", "").lower()
    if "lang" not in st.session_state and code in LANGUAGES:
        st.session_state["lang"] = code
    default = {} if "lang" in st.session_state else {"default": default_lang()}
    st.segmented_control(t("language"), list(LANGUAGES), format_func=LANGUAGES.get, key="lang",
                         required=True, bind="query-params", **default)


def sidebar_filters() -> Filters:
    """Sidebar widgets; values persist across pages through their session-state keys."""
    acc = load_accidents()
    deps = load_departments()
    years = sorted(acc["year"].unique().tolist())
    with st.sidebar:
        st.header(t("filters"))
        year_range = st.slider(t("years"), years[0], years[-1], (years[0], years[-1]), key="f_years")
        regions = st.multiselect(t("region"), sorted(deps["region_name"].dropna().unique()), key="f_regions",
                                 placeholder=t("all_regions"), format_func=tv)
        dep_choices = deps if not regions else deps[deps["region_name"].isin(regions)]
        departments = st.multiselect(t("department"), sorted(dep_choices["dep_name"].unique()), key="f_deps",
                                     placeholder=t("all_departments"))
        localisation = st.radio(t("location"), ["all", "in", "out"], format_func=lambda k: t(f"loc_{k}"),
                                key="f_loc")
        threshold = st.slider(t("threshold"), 0, 1000, 100, step=10, key="f_threshold", help=t("threshold_help"))
        st.caption(t("covid_note"))
    return Filters(year_range, regions, departments, localisation, threshold)


def apply_filters(df: pd.DataFrame, f: Filters) -> pd.DataFrame:
    """Works on accidents and victims (both carry year, region, department and in-town columns)."""
    mask = df["year"].between(*f.years)
    if f.departments:
        names = load_departments().set_index("dep_name")["dep_code"]
        mask &= df["dep_code"].isin(names.loc[f.departments].tolist())
    elif f.regions:
        mask &= df["region_name"].isin(f.regions)
    if f.localisation == "in":
        mask &= df["in_town"].fillna(False).astype(bool)
    elif f.localisation == "out":
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
# Charts
# --------------------------------------------------------------------------------------------

def dot_ci(tbl: pd.DataFrame, label: str, value: str = "pct_fatal", color_name: str = "blue",
           x_title: str | None = None, height: int | None = None) -> go.Figure:
    """Horizontal dot plot with Wilson error bars, sorted by value; labels translated for display."""
    tbl = tbl.dropna(subset=[value]).sort_values(value)
    c = color(color_name)
    counts = tbl["n_accidents"] if "n_accidents" in tbl else tbl["n_persons"]
    fig = go.Figure(go.Scatter(
        x=tbl[value], y=[str(tv(v)) for v in tbl[label]], mode="markers", marker=dict(size=11, color=c),
        error_x=dict(type="data", symmetric=False, array=tbl["ci_high"] - tbl[value],
                     arrayminus=tbl[value] - tbl["ci_low"], color=c, thickness=2, width=4),
        customdata=np.stack([counts, tbl["ci_low"], tbl["ci_high"]], axis=-1),
        hovertemplate="<b>%{y}</b><br>%{x:.1f} % (" + t("hover_ci") + " %{customdata[1]:.1f}-%{customdata[2]:.1f})"
                      "<br>%{customdata[0]:,} " + t("hover_cases") + "<extra></extra>"))
    fig.update_xaxes(title_text=x_title or t("pct_fatal_axis"), rangemode="tozero")
    fig.update_layout(height=height or max(260, 42 * len(tbl) + 90), showlegend=False)
    return fig


def show(fig: go.Figure, key: str | None = None) -> None:
    """Render with the theme and language template (Streamlit replaces Plotly's default template)."""
    fig.update_layout(template=template())
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    st.plotly_chart(fig, theme=None, key=key, config={"displaylogo": False})


def small_sample_note(threshold: int) -> None:
    st.caption(t("small_sample", n=threshold, source=t("source")))
