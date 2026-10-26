"""Shared chart style for the static figures (Plotly -> PNG through kaleido).

Palette: categorical hues in a fixed order (validated for colour-vision deficiencies on adjacent
pairs), a single-hue sequential ramp for magnitudes, no dual axes, recessive grid.
PNG export needs Chrome/Chromium for kaleido >= 1.0: run ``plotly_get_chrome`` once, or set
``BROWSER_PATH`` to an existing Chrome/Chromium binary.
"""

from __future__ import annotations

import logging
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

log = logging.getLogger(__name__)

# Categorical slots (fixed order, never cycled)
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948",
)
CATEGORICAL = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED]
# Sequential single-hue ramp (light -> dark blue)
SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
GREY = "#8a8985"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
SURFACE = "#fcfcfb"
GRID = "#e6e5e1"

pio.templates["crashmap"] = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Inter, Segoe UI, Arial, sans-serif", size=14, color=TEXT),
        title=dict(font=dict(size=19, color=TEXT), x=0.01, xanchor="left", y=0.97),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        colorway=CATEGORICAL,
        xaxis=dict(showgrid=False, zeroline=False, linecolor=GRID, ticks="outside", tickcolor=GRID,
                   title_font=dict(color=TEXT_SECONDARY, size=13), tickfont=dict(color=TEXT_SECONDARY)),
        yaxis=dict(gridcolor=GRID, zeroline=False, linecolor=GRID,
                   title_font=dict(color=TEXT_SECONDARY, size=13), tickfont=dict(color=TEXT_SECONDARY)),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0,
                    font=dict(color=TEXT_SECONDARY)),
        margin=dict(l=70, r=30, t=95, b=70),
        bargap=0.25,
        separators=", ",  # French formatting: decimal comma, thin-space thousands
    )
)
pio.templates.default = "crashmap"


# Shorter display labels for long codebook labels (figures only)
SHORT_LABELS = {
    "Nuit avec éclairage public non allumé": "Nuit, éclairage éteint",
    "Nuit avec éclairage public allumé": "Nuit, éclairage allumé",
    "Nuit sans éclairage public": "Nuit sans éclairage",
    "Parc de stationnement ouvert à la circulation publique": "Parking ouvert au public",
    "Route de métropole urbaine": "Route métropolitaine",
}


def short(series):
    """Apply SHORT_LABELS to a pandas Series of labels."""
    return series.replace(SHORT_LABELS)


def subtitle(title: str, sub: str) -> str:
    """Title with a smaller secondary line (source, scope, reading note)."""
    return f"{title}<br><span style='font-size:13px;color:{TEXT_SECONDARY}'>{sub}</span>"


def save(fig: go.Figure, path: Path, width: int = 1100, height: int = 620) -> Path | None:
    """Write ``fig`` as PNG; log a warning (and skip) when no Chrome is available for kaleido."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fig.write_image(path, width=width, height=height, scale=2)
    except Exception as exc:  # kaleido raises various errors when Chrome is missing
        log.warning("Could not export %s (%s). Run `plotly_get_chrome` or set BROWSER_PATH.", path.name, exc)
        return None
    log.info("Figure written: %s", path.name)
    return path
