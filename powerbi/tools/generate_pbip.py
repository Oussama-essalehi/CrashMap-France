"""Generate the Power BI Project (PBIP): TMDL semantic model + PBIR report.

Usage (from the repository root, after ``python run.py export``):

    python powerbi/tools/generate_pbip.py

Column types are inferred from the CSV files in ``data/gold/``. Identifiers (lineage tags, logical
ids) are deterministic UUIDs, so re-running the script produces the same files. The visual layout
is also described in ``powerbi/BUILD_GUIDE.md`` to rebuild any visual by hand.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "data" / "gold"
PBI = ROOT / "powerbi"
NAME = "CrashMapFrance"
SM = PBI / f"{NAME}.SemanticModel"
RPT = PBI / f"{NAME}.Report"
NAMESPACE = uuid.UUID("6f1c2a52-6a4e-4d7e-9a43-6d1f0b0c5e11")

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
VISUAL_SCHEMA = f"{SCHEMA}/item/report/definition/visualContainer/2.13.0/schema.json"
PAGE_SCHEMA = f"{SCHEMA}/item/report/definition/page/2.1.0/schema.json"
REPORT_VERSIONS = {"visual": "2.13.0", "page": "2.1.0", "report": "3.3.0"}
THEME_FILE = "CrashMapSignalisation.json"
DEFAULT_DATA_FOLDER = r"C:\CrashMapFrance\data\gold"
TAB = "\t"


def tag(*parts: str) -> str:
    """Deterministic lineage tag."""
    return str(uuid.uuid5(NAMESPACE, "/".join(parts)))


# ============================================================================================
# Semantic model
# ============================================================================================

TABLE_DESCRIPTIONS = {
    "dim_date": "Calendrier continu 2019-2024 (table de dates marquée).",
    "dim_time_band": "Heure de la journée et tranche horaire (nuit, matin, journée, soirée).",
    "dim_location": "Commune et localisation (en / hors agglomération) de l'accident.",
    "dim_population": "Départements, régions, zone (métropole / outre-mer) et population INSEE 2023. "
                      "Utiliser cette table pour filtrer par département ou région.",
    "dim_conditions": "Luminosité, conditions météo et état de la surface (dimension combinée).",
    "dim_road": "Catégorie de route, tranche de vitesse autorisée, tracé et type d'intersection.",
    "dim_user_type": "Catégorie d'usager (conducteur, passager, piéton) et mode de déplacement.",
    "dim_vehicle_type": "Catégorie de véhicule ONISR et regroupement d'analyse.",
    "fact_accident": "Faits au grain accident : une ligne par accident corporel.",
    "fact_vehicle": "Faits au grain véhicule : une ligne par véhicule impliqué.",
    "fact_victim": "Faits au grain personne : une ligne par usager impliqué (y compris indemnes).",
}

# Columns stored as text even if every value looks numeric
FORCE_TEXT = {"dep_code", "com_code", "region_code", "location_key", "vehicle_key", "victim_id", "year_month"}
SUMMARIZE_SUM = {"n_vehicles", "n_users", "n_victims", "n_killed", "n_hospitalized", "n_lightly_injured",
                 "n_unhurt", "killed", "hospitalized", "lightly_injured", "unhurt", "population", "com_population"}
HIDDEN = {
    "fact_accident": {"accident_id", "date_key", "hour", "location_key", "dep_code", "conditions_key", "road_key"},
    "fact_vehicle": {"vehicle_key", "accident_id", "catv"},
    "fact_victim": {"victim_id", "accident_id", "vehicle_key", "user_type_key", "catv", "grav", "severity_order",
                    "age_band_order"},
    "dim_date": {"date_key"},
    "dim_time_band": {"time_band_order"},
    "dim_conditions": {"conditions_key", "lum", "atm", "surf"},
    "dim_road": {"road_key", "catr", "plan", "intersection", "vma_band_order"},
    "dim_user_type": {"user_type_key", "catu"},
    "dim_location": {"location_key"},
}
SORT_BY = {
    ("dim_date", "month_name"): "month",
    ("dim_date", "weekday_name"): "day_of_week",
    ("dim_time_band", "time_band"): "time_band_order",
    ("dim_time_band", "hour_label"): "hour",
    ("dim_road", "vma_band"): "vma_band_order",
    ("fact_victim", "age_band"): "age_band_order",
    ("fact_victim", "severity"): "severity_order",
}
DATA_CATEGORY = {("fact_accident", "lat"): "Latitude", ("fact_accident", "lon"): "Longitude",
                 ("dim_population", "dep_geo"): "County"}
RELATIONSHIPS = [
    ("fact_accident", "date_key", "dim_date", "date_key"),
    ("fact_accident", "hour", "dim_time_band", "hour"),
    ("fact_accident", "location_key", "dim_location", "location_key"),
    ("fact_accident", "dep_code", "dim_population", "dep_code"),
    ("fact_accident", "conditions_key", "dim_conditions", "conditions_key"),
    ("fact_accident", "road_key", "dim_road", "road_key"),
    ("fact_vehicle", "accident_id", "fact_accident", "accident_id"),
    ("fact_vehicle", "catv", "dim_vehicle_type", "catv"),
    ("fact_victim", "accident_id", "fact_accident", "accident_id"),
    ("fact_victim", "user_type_key", "dim_user_type", "user_type_key"),
    ("fact_victim", "catv", "dim_vehicle_type", "catv"),
]

SEUIL = "[Valeur Seuil accidents]"
TWO_WHEELERS = '{"Moto > 125 cm3", "Moto 50-125 cm3", "Cyclomoteur <= 50 cm3"}'

# (name, folder, format, description, DAX lines)
MEASURES: list[tuple[str, str, str, str, list[str]]] = [
    ("Nb Accidents", "1. Volumes", "#,0",
     "Nombre d'accidents corporels (grain accident, jamais compté sur une table jointe).",
     ["COUNTROWS ( fact_accident )"]),
    ("Nb Accidents Mortels", "1. Volumes", "#,0",
     "Nombre d'accidents ayant fait au moins un tué (à 30 jours).",
     ["CALCULATE ( [Nb Accidents], KEEPFILTERS ( fact_accident[fatal] = TRUE () ) )"]),
    ("Nb Tués", "1. Volumes", "#,0",
     "Nombre de personnes tuées (décédées dans les 30 jours), compté au grain personne.",
     ["SUM ( fact_victim[killed] )"]),
    ("Nb Blessés Hospitalisés", "1. Volumes", "#,0",
     "Blessés hospitalisés plus de 24 h. Indicateur non labellisé depuis 2019, non comparable avant 2018.",
     ["SUM ( fact_victim[hospitalized] )"]),
    ("Nb Blessés Légers", "1. Volumes", "#,0",
     "Blessés ayant reçu des soins sans hospitalisation de plus de 24 h.",
     ["SUM ( fact_victim[lightly_injured] )"]),
    ("Nb Victimes", "1. Volumes", "#,0",
     "Victimes = tués + blessés hospitalisés + blessés légers (les indemnes ne sont pas des victimes).",
     ["[Nb Tués] + [Nb Blessés Hospitalisés] + [Nb Blessés Légers]"]),
    ("Nb Personnes Impliquées", "1. Volumes", "#,0",
     "Nombre d'usagers impliqués, indemnes compris.",
     ["COUNTROWS ( fact_victim )"]),
    ("Taux Mortalité (tués / 100 accidents)", "2. Taux", "0.00",
     "Tués pour 100 accidents. Vide si le contexte compte moins d'accidents que le seuil (paramètre Seuil accidents).",
     ["VAR nAccidents = [Nb Accidents]",
      "RETURN",
      f"    IF ( nAccidents >= {SEUIL}, DIVIDE ( [Nb Tués], nAccidents ) * 100 )"]),
    ("Part Accidents Mortels %", "2. Taux", "0.0 %",
     "Part des accidents ayant fait au moins un tué. Vide sous le seuil d'accidents.",
     ["VAR nAccidents = [Nb Accidents]",
      "RETURN",
      f"    IF ( nAccidents >= {SEUIL}, DIVIDE ( [Nb Accidents Mortels], nAccidents ) )"]),
    ("Accidents pour 100k hab", "2. Taux", "0.0",
     "Accidents par an pour 100 000 habitants (population INSEE 2023 des départements du contexte, moyenne "
     "annuelle sur les années filtrées). Territoires sans population exclus. Vide sous le seuil.",
     ["VAR nAccidents = CALCULATE ( [Nb Accidents], KEEPFILTERS ( NOT ISBLANK ( dim_population[population] ) ) )",
      "VAR population = SUM ( dim_population[population] )",
      "VAR nYears = DISTINCTCOUNT ( fact_accident[year] )",
      "RETURN",
      f"    IF ( nAccidents >= {SEUIL}, DIVIDE ( nAccidents, population * nYears ) * 100000 )"]),
    ("Tués pour 100k hab", "2. Taux", "0.0",
     "Tués par an pour 100 000 habitants (population INSEE 2023, moyenne annuelle sur les années filtrées). "
     "Vide sous le seuil d'accidents.",
     ["VAR nAccidents = CALCULATE ( [Nb Accidents], KEEPFILTERS ( NOT ISBLANK ( dim_population[population] ) ) )",
      "VAR nKilled = CALCULATE ( [Nb Tués], KEEPFILTERS ( NOT ISBLANK ( dim_population[population] ) ) )",
      "VAR population = SUM ( dim_population[population] )",
      "VAR nYears = DISTINCTCOUNT ( fact_accident[year] )",
      "RETURN",
      f"    IF ( nAccidents >= {SEUIL}, DIVIDE ( nKilled, population * nYears ) * 100000 )"]),
    ("Nb Accidents N-1", "3. Évolution", "#,0",
     "Accidents sur la même période un an plus tôt (table de dates dim_date).",
     ["CALCULATE ( [Nb Accidents], SAMEPERIODLASTYEAR ( dim_date[date] ) )"]),
    ("Nb Tués N-1", "3. Évolution", "#,0",
     "Tués sur la même période un an plus tôt.",
     ["CALCULATE ( [Nb Tués], SAMEPERIODLASTYEAR ( dim_date[date] ) )"]),
    ("Évolution Accidents %", "3. Évolution", "+0.0 %;-0.0 %;0.0 %",
     "Évolution des accidents de la dernière année sélectionnée par rapport à l'année précédente. Vide sous le seuil.",
     ["VAR lastYear = MAX ( dim_date[year] )",
      "VAR current = CALCULATE ( [Nb Accidents], dim_date[year] = lastYear )",
      "VAR previous = CALCULATE ( [Nb Accidents], dim_date[year] = lastYear - 1 )",
      "RETURN",
      f"    IF ( MIN ( current, previous ) >= {SEUIL}, DIVIDE ( current - previous, previous ) )"]),
    ("Évolution Tués %", "3. Évolution", "+0.0 %;-0.0 %;0.0 %",
     "Évolution des tués de la dernière année sélectionnée par rapport à l'année précédente. Vide sous le seuil.",
     ["VAR lastYear = MAX ( dim_date[year] )",
      "VAR current = CALCULATE ( [Nb Tués], dim_date[year] = lastYear )",
      "VAR previous = CALCULATE ( [Nb Tués], dim_date[year] = lastYear - 1 )",
      "VAR accCurrent = CALCULATE ( [Nb Accidents], dim_date[year] = lastYear )",
      "VAR accPrevious = CALCULATE ( [Nb Accidents], dim_date[year] = lastYear - 1 )",
      "RETURN",
      f"    IF ( MIN ( accCurrent, accPrevious ) >= {SEUIL}, DIVIDE ( current - previous, previous ) )"]),
    ("Rang Département Mortalité", "4. Classement", "0",
     "Rang du département sur les tués pour 100 000 habitants (1 = le plus touché) parmi les départements "
     "visibles ayant un taux.",
     ["IF (",
      "    ISINSCOPE ( dim_population[dep_name] ) && NOT ISBLANK ( [Tués pour 100k hab] ),",
      "    RANKX (",
      "        FILTER ( ALLSELECTED ( dim_population[dep_name] ), NOT ISBLANK ( [Tués pour 100k hab] ) ),",
      "        [Tués pour 100k hab], , DESC, DENSE",
      "    )",
      ")"]),
    ("Part Accidents de Nuit %", "5. Parts", "0.0 %",
     "Part des accidents survenus entre 21h et 6h. Vide sous le seuil d'accidents.",
     ["VAR nAccidents = [Nb Accidents]",
      "VAR nNight = CALCULATE ( [Nb Accidents], KEEPFILTERS ( dim_time_band[time_band] = \"Nuit (21h-6h)\" ) )",
      "RETURN",
      f"    IF ( nAccidents >= {SEUIL}, DIVIDE ( nNight, nAccidents ) )"]),
    ("Part Deux-Roues %", "5. Parts", "0.0 %",
     "Part des accidents impliquant un deux-roues (motorisé ou vélo) ou un EDP. Vide sous le seuil.",
     ["VAR nAccidents = [Nb Accidents]",
      "VAR nTwoWheelers = CALCULATE ( [Nb Accidents], KEEPFILTERS ( fact_accident[two_wheeler_involved] = TRUE () ) )",
      "RETURN",
      f"    IF ( nAccidents >= {SEUIL}, DIVIDE ( nTwoWheelers, nAccidents ) )"]),
    ("% Tués parmi impliqués", "6. Victimes et équipement", "0.0 %",
     "Part des personnes impliquées (gravité connue) qui ont été tuées. Vide si moins d'accidents que le seuil.",
     ["VAR nAccidents = DISTINCTCOUNT ( fact_victim[accident_id] )",
      "VAR nKnown = CALCULATE ( COUNTROWS ( fact_victim ), KEEPFILTERS ( NOT ISBLANK ( fact_victim[grav] ) ) )",
      "RETURN",
      f"    IF ( nAccidents >= {SEUIL}, DIVIDE ( [Nb Tués], nKnown ) )"]),
    ("% Tués ou Hospitalisés", "6. Victimes et équipement", "0.0 %",
     "Part des personnes impliquées (gravité connue) tuées ou hospitalisées. Vide sous le seuil.",
     ["VAR nAccidents = DISTINCTCOUNT ( fact_victim[accident_id] )",
      "VAR nKnown = CALCULATE ( COUNTROWS ( fact_victim ), KEEPFILTERS ( NOT ISBLANK ( fact_victim[grav] ) ) )",
      "RETURN",
      f"    IF ( nAccidents >= {SEUIL}, DIVIDE ( [Nb Tués] + [Nb Blessés Hospitalisés], nKnown ) )"]),
    ("% Tués Voiture avec ceinture", "6. Victimes et équipement", "0.0 %",
     "Occupants de voiture portant la ceinture : part de tués.",
     ["CALCULATE (",
      "    [% Tués parmi impliqués],",
      "    KEEPFILTERS ( dim_user_type[user_mode] = \"Voiture (VL)\" ),",
      "    KEEPFILTERS ( fact_victim[seatbelt_worn] = TRUE () )",
      ")"]),
    ("% Tués Voiture sans ceinture", "6. Victimes et équipement", "0.0 %",
     "Occupants de voiture ne portant pas la ceinture (équipement connu) : part de tués.",
     ["CALCULATE (",
      "    [% Tués parmi impliqués],",
      "    KEEPFILTERS ( dim_user_type[user_mode] = \"Voiture (VL)\" ),",
      "    KEEPFILTERS ( fact_victim[seatbelt_worn] = FALSE () )",
      ")"]),
    ("% Tués 2RM avec casque", "6. Victimes et équipement", "0.0 %",
     "Usagers de deux-roues motorisés (motos, cyclomoteurs) portant le casque : part de tués.",
     ["CALCULATE (",
      "    [% Tués parmi impliqués],",
      f"    KEEPFILTERS ( dim_user_type[user_mode] IN {TWO_WHEELERS} ),",
      "    KEEPFILTERS ( fact_victim[helmet_worn] = TRUE () )",
      ")"]),
    ("% Tués 2RM sans casque", "6. Victimes et équipement", "0.0 %",
     "Usagers de deux-roues motorisés sans casque (équipement connu) : part de tués.",
     ["CALCULATE (",
      "    [% Tués parmi impliqués],",
      f"    KEEPFILTERS ( dim_user_type[user_mode] IN {TWO_WHEELERS} ),",
      "    KEEPFILTERS ( fact_victim[helmet_worn] = FALSE () )",
      ")"]),
]


def infer_type(series: pd.Series, column: str) -> str:
    """TMDL data type from the CSV text values."""
    values = series.dropna()
    if column in FORCE_TEXT or values.empty:
        return "string"
    if column == "date":
        return "dateTime"
    if values.isin(["true", "false"]).all():
        return "boolean"
    if values.str.fullmatch(r"-?\d+").all():
        return "int64"
    if values.str.fullmatch(r"-?\d+(\.\d+)?").all():
        return "double"
    return "string"


def read_columns(table: str) -> list[tuple[str, str]]:
    df = pd.read_csv(GOLD / f"{table}.csv", dtype=str, keep_default_na=False, na_values=[""])
    return [(c, infer_type(df[c], c)) for c in df.columns]


M_TYPES = {"string": "type text", "int64": "Int64.Type", "double": "type number", "boolean": "type logical",
           "dateTime": "type date"}


def q(name: str) -> str:
    """Quote a TMDL object name when needed."""
    return name if name.replace("_", "").isalnum() and not name[0].isdigit() else f"'{name}'"


def column_block(table: str, column: str, dtype: str, source: str | None = None) -> list[str]:
    lines = [f"{TAB}column {q(column)}", f"{TAB*2}dataType: {dtype}"]
    if column in HIDDEN.get(table, set()):
        lines.append(f"{TAB*2}isHidden")
    if table == "dim_date" and column == "date":
        lines.append(f"{TAB*2}isKey")
    if dtype == "int64":
        lines.append(f"{TAB*2}formatString: {'#,0' if column in SUMMARIZE_SUM else '0'}")
    elif dtype == "double":
        lines.append(f"{TAB*2}formatString: 0.000000" if column in ("lat", "lon") else f"{TAB*2}formatString: #,0.00")
    elif dtype == "dateTime":
        lines.append(f"{TAB*2}formatString: dd/MM/yyyy")
    if (table, column) in DATA_CATEGORY:
        lines.append(f"{TAB*2}dataCategory: {DATA_CATEGORY[(table, column)]}")
    lines.append(f"{TAB*2}lineageTag: {tag('column', table, column)}")
    lines.append(f"{TAB*2}summarizeBy: {'sum' if column in SUMMARIZE_SUM else 'none'}")
    lines.append(f"{TAB*2}sourceColumn: {source or column}")
    if (table, column) in SORT_BY:
        lines.append(f"{TAB*2}sortByColumn: {q(SORT_BY[(table, column)])}")
    lines += ["", f"{TAB*2}annotation SummarizationSetBy = Automatic", ""]
    return lines


def table_tmdl(table: str, columns: list[tuple[str, str]]) -> str:
    lines = [f"/// {TABLE_DESCRIPTIONS[table]}", f"table {table}", f"{TAB}lineageTag: {tag('table', table)}"]
    if table == "dim_date":
        lines.append(f"{TAB}dataCategory: Time")
    lines.append("")
    all_columns = list(columns)
    if table == "dim_population":
        all_columns.append(("dep_geo", "string"))
    for column, dtype in all_columns:
        lines += column_block(table, column, dtype)
    transforms = ",\n".join(f'{TAB*4}        {{"{c}", {M_TYPES[t]}}}' for c, t in columns)
    extra = ""
    last = "Typed"
    if table == "dim_population":
        extra = (f',\n{TAB*4}    WithGeo = Table.AddColumn(Typed, "dep_geo", each [dep_name] & ", France", type text)')
        last = "WithGeo"
    lines += [
        f"{TAB}partition {table} = m",
        f"{TAB*2}mode: import",
        f"{TAB*2}source =",
        f"{TAB*4}let",
        f'{TAB*4}    Folder = Text.TrimEnd(DataFolder, {{"\\", "/"}}) & "\\",',
        f'{TAB*4}    Source = Csv.Document(File.Contents(Folder & "{table}.csv"), '
        f'[Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        f"{TAB*4}    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        f"{TAB*4}    Typed = Table.TransformColumnTypes(Headers, {{",
        transforms,
        f'{TAB*4}    }}, "en-US"){extra}',
        f"{TAB*4}in",
        f"{TAB*4}    {last}",
        "",
        f"{TAB}annotation PBI_ResultType = Table",
        "",
    ]
    return "\n".join(lines)


def measures_tmdl() -> str:
    lines = ["/// Mesures DAX du rapport, rangées par dossier d'affichage.", "table _Mesures",
             f"{TAB}lineageTag: {tag('table', '_Mesures')}", ""]
    for name, folder, fmt, description, dax in MEASURES:
        lines.append(f"{TAB}/// {description}")
        if len(dax) == 1:
            lines.append(f"{TAB}measure {q(name)} = {dax[0]}")
        else:
            lines.append(f"{TAB}measure {q(name)} =")
            lines += [f"{TAB*3}{line}" for line in dax]
        lines += [f"{TAB*2}formatString: {fmt}", f"{TAB*2}displayFolder: {folder}",
                  f"{TAB*2}lineageTag: {tag('measure', name)}", ""]
    lines += [
        f"{TAB}column Colonne",
        f"{TAB*2}dataType: string",
        f"{TAB*2}isHidden",
        f"{TAB*2}lineageTag: {tag('column', '_Mesures', 'Colonne')}",
        f"{TAB*2}summarizeBy: none",
        f"{TAB*2}sourceColumn: Colonne",
        "",
        f"{TAB*2}annotation SummarizationSetBy = Automatic",
        "",
        f"{TAB}partition _Mesures = m",
        f"{TAB*2}mode: import",
        f"{TAB*2}source =",
        f"{TAB*4}let",
        f"{TAB*4}    Source = #table(type table [Colonne = text], {{}})",
        f"{TAB*4}in",
        f"{TAB*4}    Source",
        "",
        f"{TAB}annotation PBI_ResultType = Table",
        "",
    ]
    return "\n".join(lines)


def threshold_tmdl() -> str:
    """What-if parameter 'Seuil accidents' (0 to 1000, step 10, default 100)."""
    return "\n".join([
        "/// Paramètre de simulation : nombre minimal d'accidents pour afficher un taux (défaut 100).",
        "table 'Seuil accidents'",
        f"{TAB}lineageTag: {tag('table', 'Seuil accidents')}",
        "",
        f"{TAB}/// Seuil sélectionné (100 par défaut si aucune valeur n'est choisie).",
        f"{TAB}measure 'Valeur Seuil accidents' = SELECTEDVALUE ( 'Seuil accidents'[Seuil accidents], 100 )",
        f"{TAB*2}formatString: 0",
        f"{TAB*2}displayFolder: Paramètres",
        f"{TAB*2}lineageTag: {tag('measure', 'Valeur Seuil accidents')}",
        "",
        f"{TAB}column 'Seuil accidents'",
        f"{TAB*2}dataType: int64",
        f"{TAB*2}formatString: 0",
        f"{TAB*2}lineageTag: {tag('column', 'Seuil accidents', 'Seuil accidents')}",
        f"{TAB*2}summarizeBy: none",
        f"{TAB*2}sourceColumn: [Value]",
        "",
        f"{TAB*2}extendedProperty ParameterMetadata =",
        f"{TAB*4}{{",
        f'{TAB*4}  "version": 0',
        f"{TAB*4}}}",
        "",
        f"{TAB*2}annotation SummarizationSetBy = User",
        "",
        f"{TAB}partition 'Seuil accidents' = calculated",
        f"{TAB*2}mode: import",
        f"{TAB*2}source = GENERATESERIES ( 0, 1000, 10 )",
        "",
        f"{TAB}annotation PBI_Id = {uuid.uuid5(NAMESPACE, 'seuil').hex}",
        "",
    ])


def write_semantic_model(tables: dict[str, list[tuple[str, str]]]) -> None:
    definition = SM / "definition"
    if definition.exists():
        shutil.rmtree(definition)
    (definition / "tables").mkdir(parents=True)
    write_json(SM / "definition.pbism", {
        "$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.0", "settings": {}})
    write_json(SM / ".platform", platform("SemanticModel"))
    (definition / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1600\n\n", encoding="utf-8")
    order = list(tables) + ["_Mesures", "Seuil accidents"]
    model = [
        "model Model",
        f"{TAB}culture: fr-FR",
        f"{TAB}defaultPowerBIDataSourceVersion: powerBI_V3",
        f"{TAB}discourageImplicitMeasures",
        f"{TAB}sourceQueryCulture: fr-FR",
        f"{TAB}dataAccessOptions",
        f"{TAB*2}legacyRedirects",
        f"{TAB*2}returnErrorValuesAsNull",
        "",
        f"{TAB}annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
        f"{TAB}annotation PBI_QueryOrder = {json.dumps(['DataFolder', *tables, '_Mesures'], ensure_ascii=False)}",
        "",
        f"{TAB}annotation PBI_ProTooling = [\"DevMode\"]",
        "",
    ] + [f"ref table {q(t)}" for t in order] + [""]
    (definition / "model.tmdl").write_text("\n".join(model), encoding="utf-8")
    (definition / "expressions.tmdl").write_text("\n".join([
        "/// Dossier contenant les CSV de data/gold (chemin absolu). À adapter puis Actualiser.",
        f'expression DataFolder = "{DEFAULT_DATA_FOLDER}" meta [IsParameterQuery = true, Type = "Text", '
        f'IsParameterQueryRequired = true]',
        f"{TAB}lineageTag: {tag('expression', 'DataFolder')}",
        "",
        f"{TAB}annotation PBI_ResultType = Text",
        "",
    ]), encoding="utf-8")
    rels = []
    for from_t, from_c, to_t, to_c in RELATIONSHIPS:
        rels += [f"relationship {tag('relationship', from_t, from_c, to_t, to_c)}",
                 f"{TAB}fromColumn: {from_t}.{from_c}", f"{TAB}toColumn: {to_t}.{to_c}", ""]
    (definition / "relationships.tmdl").write_text("\n".join(rels), encoding="utf-8")
    for table, columns in tables.items():
        (definition / "tables" / f"{table}.tmdl").write_text(table_tmdl(table, columns), encoding="utf-8")
    (definition / "tables" / "_Mesures.tmdl").write_text(measures_tmdl(), encoding="utf-8")
    (definition / "tables" / "Seuil accidents.tmdl").write_text(threshold_tmdl(), encoding="utf-8")


# ============================================================================================
# Report (PBIR)
# ============================================================================================

def lit(value) -> dict:
    """PBIR literal expression."""
    if isinstance(value, bool):
        return {"expr": {"Literal": {"Value": "true" if value else "false"}}}
    if isinstance(value, (int, float)):
        return {"expr": {"Literal": {"Value": f"{value}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(value).replace("'", "''") + "'"}}}


def measure(name: str, table: str = "_Mesures") -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def column(table: str, name: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def projection(field: dict) -> dict:
    kind = "Measure" if "Measure" in field else "Column"
    entity = field[kind]["Expression"]["SourceRef"]["Entity"]
    prop = field[kind]["Property"]
    return {"field": field, "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}


def visual(name: str, vtype: str, x: int, y: int, w: int, h: int, title: str, roles: dict[str, list[dict]],
           objects: dict | None = None, sort: tuple[dict, str] | None = None, z: int = 0,
           extra_container: dict | None = None, sync_group: str | None = None) -> dict:
    v: dict = {"visualType": vtype,
               "query": {"queryState": {role: {"projections": [projection(f) for f in fields]}
                                        for role, fields in roles.items()}}}
    if sort:
        v["query"]["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}], "isDefaultSort": False}
    if objects:
        v["objects"] = objects
    container = {"title": [{"properties": {"show": lit(True), "text": lit(title)}}]}
    if extra_container:
        container.update(extra_container)
    v["visualContainerObjects"] = container
    if sync_group:
        v["syncGroup"] = {"groupName": sync_group, "fieldChanges": True, "filterChanges": True}
    return {"$schema": VISUAL_SCHEMA, "name": name,
            "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
            "visual": v}


def data_labels() -> dict:
    return {"labels": [{"properties": {"show": lit(True)}}]}


def gradient(field: dict, max_color: str = "#1f5fae") -> dict:
    """Conditional formatting: white -> max_color gradient driven by a measure."""
    return {"solid": {"color": {"expr": {"FillRule": {
        "Input": field,
        "FillRule": {"linearGradient2": {
            "min": {"color": {"Literal": {"Value": "'#FFFFFF'"}}},
            "max": {"color": {"Literal": {"Value": f"'{max_color}'"}}},
            "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}}}}}}}}}


WILDCARD = {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}

M = {name: measure(name) for name, *_ in MEASURES}
YEAR, REGION, DEP = column("dim_date", "year"), column("dim_population", "region_name"), column("dim_population", "dep_name")
IN_TOWN = column("dim_location", "in_town_label")
THRESHOLD = column("Seuil accidents", "Seuil accidents")


def slicers(prefix: str, y: int = 8) -> list[dict]:
    """Year, region, department, in-town and threshold slicers (synced across pages)."""
    specs = [("annee", YEAR, "Année", 210), ("region", REGION, "Région", 230), ("departement", DEP, "Département", 230),
             ("agglo", IN_TOWN, "Localisation", 230), ("seuil", THRESHOLD, "Seuil accidents (taux)", 200)]
    out, x = [], 20
    for key, field, title, width in specs:
        objects = {"data": [{"properties": {"mode": lit("Dropdown")}}],
                   "header": [{"properties": {"show": lit(False)}}]}  # title already names the field
        if key == "seuil":
            objects["selection"] = [{"properties": {"singleSelect": lit(True)}}]
        out.append(visual(f"{prefix}_slc_{key}", "slicer", x, y, width, 80, title, {"Values": [field]},
                          objects=objects,
                          sync_group=f"sync_{key}", z=len(out)))
        x += width + 15
    return out


def card(name: str, mname: str, x: int, y: int, title: str, z: int, w: int = 195) -> dict:
    return visual(name, "card", x, y, w, 105, title, {"Values": [M[mname]]}, z=z,
                  objects={"categoryLabels": [{"properties": {"show": lit(False)}}]})  # title already says it


def page_overview() -> list[dict]:
    p = "ve"
    v = slicers(p)
    kpis = [("Nb Accidents", "Accidents"), ("Nb Tués", "Tués"), ("Taux Mortalité (tués / 100 accidents)", "Tués / 100 accidents"),
            ("Tués pour 100k hab", "Tués / 100 000 hab. / an"), ("Évolution Tués %", "Tués vs année précédente"),
            ("Part Accidents de Nuit %", "Part d'accidents de nuit")]
    for i, (mname, title) in enumerate(kpis):
        v.append(card(f"{p}_kpi_{i}", mname, 20 + i * 207, 95, title, 10 + i))
    v.append(visual(f"{p}_tues_annee", "clusteredColumnChart", 20, 215, 610, 490, "Tués par an (2020 : année COVID)",
                    {"Category": [YEAR], "Y": [M["Nb Tués"]]}, objects=data_labels(), z=20))
    v.append(visual(f"{p}_acc_mois", "lineChart", 645, 215, 615, 490, "Accidents par mois, une courbe par année",
                    {"Category": [column("dim_date", "month_name")], "Y": [M["Nb Accidents"]], "Series": [YEAR]}, z=21,
                    objects={"legend": [{"properties": {"showTitle": lit(False)}}]}))
    return v


def page_map() -> list[dict]:
    p = "cf"
    v = slicers(p)
    v.append(visual(f"{p}_carte", "filledMap", 20, 95, 640, 610, "Tués pour 100 000 habitants par an, par département",
                    {"Category": [column("dim_population", "dep_geo")], "Tooltips": [M["Tués pour 100k hab"]]},
                    objects={"dataPoint": [{"properties": {"fill": gradient(M["Tués pour 100k hab"], "#d1342b")},
                                            "selector": WILDCARD}]},
                    extra_container={"visualTooltip": [{"properties": {"show": lit(True), "type": lit("ReportPage"),
                                                                       "section": lit("info_departement")}}]}, z=10))
    cols = [DEP, M["Tués pour 100k hab"], M["Nb Tués"], M["Nb Accidents"], M["Taux Mortalité (tués / 100 accidents)"],
            M["Rang Département Mortalité"]]
    v.append(visual(f"{p}_top", "tableEx", 675, 95, 585, 300, "Départements les plus touchés (tués / 100 000 hab.)",
                    {"Values": cols}, sort=(M["Tués pour 100k hab"], "Descending"), z=11))
    v.append(visual(f"{p}_bottom", "tableEx", 675, 405, 585, 300, "Départements les moins touchés (tués / 100 000 hab.)",
                    {"Values": cols}, sort=(M["Tués pour 100k hab"], "Ascending"), z=12))
    return v


def page_tooltip() -> list[dict]:
    p = "tt"
    return [
        visual(f"{p}_nom", "card", 10, 10, 300, 70, "Département", {"Values": [DEP]}, z=0),
        visual(f"{p}_details", "multiRowCard", 10, 85, 300, 225, "Indicateurs 2019-2024",
               {"Values": [M["Tués pour 100k hab"], M["Nb Tués"], M["Nb Accidents"],
                           M["Taux Mortalité (tués / 100 accidents)"], M["Rang Département Mortalité"]]}, z=1),
    ]


def page_when() -> list[dict]:
    p = "qd"
    v = slicers(p)
    rows, cols = [column("dim_date", "weekday_name")], [column("dim_time_band", "hour_label")]
    v.append(visual(f"{p}_heat_acc", "pivotTable", 20, 95, 615, 300, "Accidents par jour et par heure",
                    {"Rows": rows, "Columns": cols, "Values": [M["Nb Accidents"]]},
                    objects={"values": [{"properties": {"backColor": gradient(M["Nb Accidents"])},
                                         "selector": {**WILDCARD, "metadata": "_Mesures.Nb Accidents"}}]}, z=10))
    rate = M["Taux Mortalité (tués / 100 accidents)"]
    v.append(visual(f"{p}_heat_taux", "pivotTable", 645, 95, 615, 300, "Tués pour 100 accidents par jour et par heure",
                    {"Rows": rows, "Columns": cols, "Values": [rate]},
                    objects={"values": [{"properties": {"backColor": gradient(rate, "#d1342b")},
                                         "selector": {**WILDCARD, "metadata": "_Mesures.Taux Mortalité (tués / 100 accidents)"}}]},
                    z=11))
    month = column("dim_date", "month_name")
    v.append(visual(f"{p}_mois_acc", "clusteredColumnChart", 20, 405, 410, 300, "Saisonnalité : accidents par mois",
                    {"Category": [month], "Y": [M["Nb Accidents"]]}, z=12))
    v.append(visual(f"{p}_mois_taux", "lineChart", 440, 405, 410, 300, "Saisonnalité : tués pour 100 accidents",
                    {"Category": [month], "Y": [rate]}, z=13))
    v.append(visual(f"{p}_tranche", "clusteredBarChart", 860, 405, 400, 300, "Tués pour 100 accidents par tranche horaire",
                    {"Category": [column("dim_time_band", "time_band")], "Y": [rate]}, objects=data_labels(), z=14))
    return v


def page_conditions() -> list[dict]:
    p = "cd"
    v = slicers(p)
    rate = M["Taux Mortalité (tués / 100 accidents)"]
    specs = [("lum", column("dim_conditions", "lum_label"), "Luminosité", 20, 95),
             ("atm", column("dim_conditions", "atm_label"), "Conditions météo", 440, 95),
             ("surf", column("dim_conditions", "surf_label"), "État de la surface", 860, 95),
             ("catr", column("dim_road", "catr_label"), "Catégorie de route", 20, 300),
             ("vma", column("dim_road", "vma_band"), "Vitesse maximale autorisée", 440, 300)]
    for i, (key, field, label, x, y) in enumerate(specs):
        v.append(visual(f"{p}_{key}", "clusteredBarChart", x, y, 410, 195, f"Tués pour 100 accidents : {label.lower()}",
                        {"Category": [field], "Y": [rate]}, sort=(rate, "Descending"), objects=data_labels(), z=10 + i))
    explain = [column("dim_location", "in_town_label"), column("dim_road", "catr_label"), column("dim_road", "vma_band"),
               column("dim_conditions", "lum_label"), column("dim_time_band", "time_band"),
               column("dim_conditions", "atm_label"), column("dim_road", "intersection_label")]
    v.append(visual(f"{p}_arbre", "decompositionTreeVisual", 860, 300, 400, 405,
                    "Arbre de décomposition : tués pour 100 accidents", {"Analyze": [rate], "ExplainBy": explain}, z=20))
    v.append(visual(f"{p}_trace", "clusteredBarChart", 20, 505, 830, 200, "Tués pour 100 accidents : type d'intersection",
                    {"Category": [column("dim_road", "intersection_label")], "Y": [rate]}, sort=(rate, "Descending"),
                    objects=data_labels(), z=15))
    return v


def page_who() -> list[dict]:
    p = "qui"
    v = slicers(p)
    mode = column("dim_user_type", "user_mode")
    v.append(visual(f"{p}_mode", "clusteredBarChart", 20, 95, 410, 300, "Tués par mode de déplacement",
                    {"Category": [mode], "Y": [M["Nb Tués"]]}, sort=(M["Nb Tués"], "Descending"), objects=data_labels(), z=10))
    v.append(visual(f"{p}_mode_taux", "clusteredBarChart", 440, 95, 410, 300, "% de tués parmi les personnes impliquées",
                    {"Category": [mode], "Y": [M["% Tués parmi impliqués"]]}, sort=(M["% Tués parmi impliqués"], "Descending"),
                    objects=data_labels(), z=11))
    v.append(visual(f"{p}_categorie", "clusteredColumnChart", 860, 95, 400, 300, "Victimes par catégorie d'usager",
                    {"Category": [column("dim_user_type", "catu_label")],
                     "Y": [M["Nb Tués"], M["Nb Blessés Hospitalisés"], M["Nb Blessés Légers"]]}, z=12))
    v.append(visual(f"{p}_age_sexe", "clusteredColumnChart", 20, 405, 620, 300, "Tués par tranche d'âge et par sexe",
                    {"Category": [column("fact_victim", "age_band")], "Y": [M["Nb Tués"]],
                     "Series": [column("fact_victim", "sex")]}, z=13))
    v.append(visual(f"{p}_equipement", "clusteredColumnChart", 650, 405, 610, 300,
                    "Équipement de sécurité et part de tués (à catégorie d'usager égale)",
                    {"Y": [M["% Tués Voiture avec ceinture"], M["% Tués Voiture sans ceinture"],
                           M["% Tués 2RM avec casque"], M["% Tués 2RM sans casque"]]}, objects=data_labels(), z=14))
    return v


PAGES = [
    ("vue_ensemble", "Vue d'ensemble", page_overview, {}),
    ("carte_france", "Carte de France", page_map, {}),
    ("quand", "Quand ?", page_when, {}),
    ("conditions", "Dans quelles conditions ?", page_conditions, {}),
    ("qui", "Qui ?", page_who, {}),
    ("info_departement", "Info-bulle département", page_tooltip,
     {"type": "Tooltip", "width": 320, "height": 320, "visibility": "HiddenInViewMode",
      "pageBinding": {"name": "binding_info_departement", "type": "Tooltip"}}),
]


def write_report() -> None:
    definition = RPT / "definition"
    if definition.exists():
        shutil.rmtree(definition)
    (definition / "pages").mkdir(parents=True)
    write_json(RPT / "definition.pbir", {
        "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    write_json(RPT / ".platform", platform("Report"))
    write_json(definition / "version.json", {
        "$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    write_json(definition / "report.json", {
        "$schema": f"{SCHEMA}/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {"customTheme": {"name": THEME_FILE, "reportVersionAtImport": REPORT_VERSIONS,
                                            "type": "RegisteredResources"}},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                              "items": [{"name": THEME_FILE, "path": THEME_FILE, "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True},
    })
    resources = RPT / "StaticResources" / "RegisteredResources"
    resources.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PBI / "theme.json", resources / THEME_FILE)
    write_json(definition / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": [name for name, *_ in PAGES], "activePageName": PAGES[0][0]})
    for name, display, builder, extra in PAGES:
        folder = definition / "pages" / name
        page = {"$schema": PAGE_SCHEMA, "name": name, "displayName": display, "displayOption": "FitToPage",
                "height": 720, "width": 1280}
        page.update(extra)
        write_json(folder / "page.json", page)
        for vis in builder():
            write_json(folder / "visuals" / vis["name"] / "visual.json", vis)


def platform(item_type: str) -> dict:
    return {"$schema": f"{SCHEMA}/gitIntegration/platformProperties/2.1.0/schema.json",
            "metadata": {"type": item_type, "displayName": NAME},
            "config": {"version": "2.0", "logicalId": tag("logicalId", item_type)}}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    if not (GOLD / "fact_accident.csv").exists():
        raise SystemExit("data/gold is empty: run `python run.py export` first")
    tables = {t: read_columns(t) for t in ["dim_date", "dim_time_band", "dim_location", "dim_population",
                                            "dim_conditions", "dim_road", "dim_user_type", "dim_vehicle_type",
                                            "fact_accident", "fact_vehicle", "fact_victim"]}
    write_semantic_model(tables)
    write_report()
    write_json(PBI / f"{NAME}.pbip", {
        "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}], "settings": {"enableAutoRecovery": True}})
    print(f"Power BI project written to {PBI.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
