"""Interactive HTML maps (folium / Leaflet), written to ``reports/maps/``.

1. ``france_deaths_per_100k.html``: choropleth of deaths per 100,000 inhabitants per year by
   department (metropolitan France; overseas departments listed in a side panel).
2. ``<city>_heatmap.html``: heatmap of precisely geolocated accidents in the focus city
   (``maps.focus_city`` in config.yaml) with a toggle layer of fatal accidents (popups: date, time,
   conditions, users involved; no personal data).
3. ``<city>_hotspots.html``: DBSCAN clusters ("points noirs") on the same accidents; the top
   clusters are also written to ``reports/tables/hotspots_<city>.csv``.

Accidents whose coordinates are invalid or shared by many accidents (geocoding artefacts) are
excluded from the city maps (``coord_precise``).
"""

from __future__ import annotations

import html
import json
import logging
import re

import folium
import numpy as np
import pandas as pd
from folium.plugins import HeatMap
from sklearn.cluster import DBSCAN

from crashmap.analyze import TABLES_DIR, department_table
from crashmap.config import ROOT, get_paths, load_config

log = logging.getLogger(__name__)

EARTH_RADIUS_M = 6_371_000
ATTRIBUTION = ("Données : ONISR (data.gouv.fr), INSEE 2023, contours IGN Admin Express via "
               "france-geojson (Licence Ouverte)")
# Communes split into municipal arrondissements in the accident files
ARRONDISSEMENT_PREFIX = {"75056": "751", "69123": "6938", "13055": "132"}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def add_source_note(m: folium.Map) -> None:
    """Data sources caption (bottom right, above the tile attribution)."""
    m.get_root().html.add_child(folium.Element(
        "<div style='position:fixed;bottom:22px;right:10px;z-index:9999;background:rgba(255,255,255,.85);"
        f"padding:2px 6px;font:11px Arial,sans-serif;color:#52514e'>{ATTRIBUTION}</div>"))


def _check_size(path) -> None:
    max_mb = float(load_config()["maps"]["max_html_mb"])
    size_mb = path.stat().st_size / 1e6
    if size_mb > max_mb:
        raise RuntimeError(f"{path.name} is {size_mb:.1f} MB (limit {max_mb} MB)")
    log.info("Map written: %s (%.2f MB)", path.name, size_mb)


# --------------------------------------------------------------------------------------------
# 1. France choropleth
# --------------------------------------------------------------------------------------------

def france_choropleth(acc: pd.DataFrame, deps: pd.DataFrame, geojson_path, out_path) -> None:
    rates = department_table(acc, deps)
    geo = json.loads(geojson_path.read_text(encoding="utf-8"))
    by_code = rates.set_index("dep_code")
    for feature in geo["features"]:
        code = feature["properties"]["code"]
        row = by_code.loc[code] if code in by_code.index else None
        props = feature["properties"]
        props["taux"] = "n.d." if row is None or pd.isna(row["killed_per_100k_per_year"]) else \
            f"{row['killed_per_100k_per_year']:.1f}".replace(".", ",")
        props["tues"] = "n.d." if row is None else f"{int(row['n_killed']):,}".replace(",", " ")
        props["accidents"] = "n.d." if row is None else f"{int(row['n_accidents']):,}".replace(",", " ")
        props["rang"] = "n.d." if row is None or pd.isna(row["rank_killed_per_100k"]) else int(row["rank_killed_per_100k"])

    m = folium.Map(location=[46.6, 2.4], zoom_start=6, tiles="OpenStreetMap")
    metro = rates[rates["zone"] == "Métropole"]
    folium.Choropleth(
        geo_data=geo, data=metro, columns=["dep_code", "killed_per_100k_per_year"],
        key_on="feature.properties.code", fill_color="Reds", fill_opacity=0.8, line_opacity=0.4,
        nan_fill_color="#dddddd", bins=7,
        legend_name="Tués pour 100 000 habitants par an (moyenne 2019-2024)",
    ).add_to(m)
    folium.GeoJson(
        geo, style_function=lambda _: {"fillOpacity": 0, "weight": 0},
        tooltip=folium.GeoJsonTooltip(
            fields=["nom", "code", "taux", "tues", "accidents", "rang"],
            aliases=["Département", "Code", "Tués / 100 000 hab. / an", "Tués 2019-2024", "Accidents 2019-2024",
                     "Rang national"]),
    ).add_to(m)

    overseas = rates[rates["zone"] == "Outre-mer (DROM)"].sort_values("killed_per_100k_per_year", ascending=False)
    rows = "".join(
        f"<tr><td>{html.escape(r.dep_name)}</td><td style='text-align:right'>"
        f"{'n.d.' if pd.isna(r.killed_per_100k_per_year) else f'{r.killed_per_100k_per_year:.1f}'.replace('.', ',')}</td></tr>"
        for r in overseas.itertuples())
    panel = (
        "<div style='position:fixed;bottom:30px;left:12px;z-index:9999;background:white;padding:8px 12px;"
        "border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.3);font:13px Arial,sans-serif'>"
        "<b>Outre-mer</b> (tués / 100 000 hab. / an)<table>" + rows + "</table>"
        "<div style='color:#666;font-size:11px'>Mayotte : pas de population de référence INSEE 2023</div></div>"
    )
    title = ("<div style='position:fixed;top:10px;left:60px;z-index:9999;background:white;padding:6px 12px;"
             "border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.3);font:15px Arial,sans-serif'>"
             "<b>CrashMap France</b> - tués pour 100 000 habitants par an, 2019-2024</div>")
    m.get_root().html.add_child(folium.Element(title + panel))
    add_source_note(m)
    m.save(out_path)
    _check_size(out_path)


# --------------------------------------------------------------------------------------------
# 2-3. Focus city
# --------------------------------------------------------------------------------------------

def city_accidents(acc: pd.DataFrame, insee_code: str) -> pd.DataFrame:
    prefix = ARRONDISSEMENT_PREFIX.get(insee_code)
    mask = acc["com_code"].str.startswith(prefix) if prefix else acc["com_code"] == insee_code
    city = acc[mask]
    log.info("Focus city %s: %d accidents, %d precisely geolocated", insee_code, len(city),
             int(city["coord_precise"].sum()))
    return city[city["coord_precise"]].copy()


def users_summary(victims: pd.DataFrame, accident_ids) -> pd.Series:
    """Per accident, a short description of the users involved (travel modes and severities)."""
    v = victims[victims["accident_id"].isin(accident_ids)]
    def describe(group: pd.DataFrame) -> str:
        parts = []
        for mode, sub in group.groupby("user_mode", dropna=False):
            killed = int(sub["killed"].sum())
            label = "Inconnu" if pd.isna(mode) else mode
            parts.append(f"{label} : {len(sub)} pers." + (f" dont {killed} tué(s)" if killed else ""))
        return " ; ".join(parts)
    return v.groupby("accident_id").apply(describe, include_groups=False)


def _popup(row, users: str) -> str:
    def val(x):
        return "n.r." if pd.isna(x) else html.escape(str(x))
    return (f"<b>Accident mortel</b><br>{row.date:%d/%m/%Y} à {val(row.hrmn)}<br>"
            f"Luminosité : {val(row.lum_label)}<br>Météo : {val(row.atm_label)}<br>"
            f"Route : {val(row.catr_label)}, {val(row.vma)} km/h<br>"
            f"Tués : {row.n_killed}, blessés hospitalisés : {row.n_hospitalized}<br>"
            f"Usagers : {html.escape(users)}")


def city_heatmap(city: pd.DataFrame, victims: pd.DataFrame, cfg: dict, out_path) -> None:
    m = folium.Map(location=cfg["center"], zoom_start=cfg["zoom"], tiles="OpenStreetMap")
    HeatMap(city[["lat", "lon"]].values.tolist(), name="Densité des accidents (2019-2024)", radius=12, blur=15,
            min_opacity=0.3).add_to(m)
    fatal = city[city["fatal"]]
    users = users_summary(victims, fatal["accident_id"])
    layer = folium.FeatureGroup(name=f"Accidents mortels ({len(fatal)})", show=True)
    for row in fatal.itertuples():
        folium.CircleMarker(
            location=[row.lat, row.lon], radius=6, color="#ffffff", weight=1.5, fill=True, fill_color="#e34948",
            fill_opacity=0.95, popup=folium.Popup(_popup(row, users.get(row.accident_id, "")), max_width=320),
        ).add_to(layer)
    layer.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    title = (f"<div style='position:fixed;top:10px;left:60px;z-index:9999;background:white;padding:6px 12px;"
             f"border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.3);font:15px Arial,sans-serif'>"
             f"<b>{html.escape(cfg['name'])}</b> - {len(city):,} accidents géolocalisés, 2019-2024</div>").replace(",", " ")
    m.get_root().html.add_child(folium.Element(title))
    add_source_note(m)
    m.save(out_path)
    _check_size(out_path)


def find_hotspots(city: pd.DataFrame, victims: pd.DataFrame, radius_m: float, min_samples: int,
                  top: int) -> tuple[pd.DataFrame, np.ndarray]:
    """DBSCAN with the haversine metric on (lat, lon) in radians; eps = radius / Earth radius."""
    coords = np.radians(city[["lat", "lon"]].to_numpy())
    labels = DBSCAN(eps=radius_m / EARTH_RADIUS_M, min_samples=min_samples, metric="haversine",
                    algorithm="ball_tree").fit_predict(coords)
    city = city.assign(cluster=labels)
    clustered = city[city["cluster"] >= 0]
    vic = victims[victims["accident_id"].isin(clustered["accident_id"])]
    vic = vic.merge(clustered[["accident_id", "cluster"]], on="accident_id")
    vulnerable = vic.groupby("cluster")["user_mode"].agg(
        lambda s: int(s.isin(["Piéton", "Vélo (y.c. VAE)", "EDP motorisé (trottinette...)"]).sum()))
    stats = clustered.groupby("cluster").agg(
        n_accidents=("accident_id", "size"), n_killed=("n_killed", "sum"), n_hospitalized=("n_hospitalized", "sum"),
        n_fatal_accidents=("fatal", "sum"), lat=("lat", "mean"), lon=("lon", "mean"),
        first_year=("year", "min"), last_year=("year", "max"),
        main_address=("adr", lambda s: s.dropna().str.upper().value_counts().index[0] if s.notna().any() else None),
        in_town_share=("in_town", "mean"),
    )
    stats["n_pedestrians_cyclists_edp"] = vulnerable
    stats["severity_score"] = stats["n_killed"] * 10 + stats["n_hospitalized"] * 3 + stats["n_accidents"]
    stats = stats.sort_values(["n_accidents", "severity_score"], ascending=False).head(top).reset_index()
    stats.insert(0, "rank", np.arange(1, len(stats) + 1))
    stats[["lat", "lon"]] = stats[["lat", "lon"]].round(5)
    return stats, labels


def hotspot_map(city: pd.DataFrame, hotspots: pd.DataFrame, labels: np.ndarray, cfg: dict, radius_m: float,
                out_path) -> None:
    m = folium.Map(location=cfg["center"], zoom_start=cfg["zoom"], tiles="OpenStreetMap")
    noise = folium.FeatureGroup(name="Accidents hors points noirs", show=False)
    for lat, lon in city.loc[labels < 0, ["lat", "lon"]].to_numpy():
        folium.CircleMarker([lat, lon], radius=2, color="#8a8985", weight=0, fill=True, fill_opacity=0.5).add_to(noise)
    noise.add_to(m)
    clustered_pts = folium.FeatureGroup(name="Accidents dans un point noir", show=True)
    for lat, lon in city.loc[labels >= 0, ["lat", "lon"]].to_numpy():
        folium.CircleMarker([lat, lon], radius=3, color="#2a78d6", weight=0, fill=True, fill_opacity=0.7).add_to(clustered_pts)
    clustered_pts.add_to(m)
    top = folium.FeatureGroup(name=f"Top {len(hotspots)} points noirs", show=True)
    for r in hotspots.itertuples():
        text = (f"<b>Point noir n°{r.rank}</b><br>{html.escape(str(r.main_address or 'adresse non renseignée'))}<br>"
                f"{r.n_accidents} accidents ({r.first_year}-{r.last_year})<br>"
                f"Tués : {r.n_killed}, blessés hospitalisés : {r.n_hospitalized}<br>"
                f"Piétons, cyclistes, EDP impliqués : {r.n_pedestrians_cyclists_edp}")
        folium.Circle([r.lat, r.lon], radius=radius_m * 1.5, color="#e34948", weight=2, fill=True, fill_opacity=0.15,
                      popup=folium.Popup(text, max_width=300)).add_to(top)
        folium.Marker([r.lat, r.lon], icon=folium.DivIcon(
            html=f"<div style='font:bold 13px Arial;color:#e34948;transform:translate(-4px,-8px)'>{r.rank}</div>")).add_to(top)
    top.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    if len(hotspots):
        m.fit_bounds([[hotspots["lat"].min(), hotspots["lon"].min()], [hotspots["lat"].max(), hotspots["lon"].max()]],
                     padding=(40, 40))
    title = (f"<div style='position:fixed;top:10px;left:60px;z-index:9999;background:white;padding:6px 12px;"
             f"border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.3);font:15px Arial,sans-serif'>"
             f"<b>{html.escape(cfg['name'])}</b> - points noirs (DBSCAN, rayon {radius_m:.0f} m), 2019-2024</div>")
    m.get_root().html.add_child(folium.Element(title))
    add_source_note(m)
    m.save(out_path)
    _check_size(out_path)


def main() -> None:
    paths = get_paths()
    cfg = load_config()["maps"]
    acc = pd.read_parquet(paths.processed / "accidents.parquet")
    victims = pd.read_parquet(paths.processed / "victims.parquet",
                              columns=["accident_id", "user_mode", "killed"])
    deps = pd.read_parquet(paths.processed / "departments.parquet")

    france_choropleth(acc, deps, paths.raw_geo / "departements.geojson", paths.maps / "france_deaths_per_100k.html")

    city_cfg = cfg["focus_city"]
    city = city_accidents(acc, str(city_cfg["insee_code"]))
    name = slug(city_cfg["name"])
    city_heatmap(city, victims, city_cfg, paths.maps / f"{name}_heatmap.html")

    radius = float(cfg["dbscan"]["radius_m"])
    hotspots, labels = find_hotspots(city, victims, radius, int(cfg["dbscan"]["min_samples"]), int(cfg["top_hotspots"]))
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    hotspots.to_csv(TABLES_DIR / f"hotspots_{name}.csv", index=False)
    log.info("%d DBSCAN clusters in %s, top %d saved", int(labels.max()) + 1, city_cfg["name"], len(hotspots))
    hotspot_map(city, hotspots, labels, city_cfg, radius, paths.maps / f"{name}_hotspots.html")


if __name__ == "__main__":
    from crashmap.config import setup_logging

    setup_logging()
    main()
