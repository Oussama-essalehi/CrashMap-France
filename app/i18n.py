"""French / English texts of the web app.

* ``t(key, **kwargs)``: interface text in the current language (``str.format`` placeholders).
* ``tv(value)`` / ``tv_series(series)``: data labels (stored in French in the data) translated for
  display; department and region names are proper nouns and stay unchanged.
* ``num(value, digits, suffix)``: number formatting for the current language.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

LANGUAGES = {"fr": "Français", "en": "English"}

UI: dict[str, tuple[str, str]] = {
    # Navigation
    "nav_overview": ("Vue d'ensemble", "Overview"),
    "nav_map": ("Carte de France", "Map of France"),
    "nav_when": ("Quand ?", "When?"),
    "nav_conditions": ("Dans quelles conditions ?", "Under what conditions?"),
    "nav_who": ("Qui ?", "Who?"),
    "nav_hotspots": ("Points noirs à Toulouse", "Toulouse black spots"),
    "nav_about": ("Méthode et sources", "Method and sources"),
    # Sidebar
    "language": ("Langue", "Language"),
    "about_button": ("À propos du projet", "About this project"),
    "theme_hint": ("Thème clair ou sombre : menu ⋮ en haut à droite > Settings.",
                   "Light or dark theme: ⋮ menu at the top right > Settings."),
    "filters": ("Filtres", "Filters"),
    "years": ("Années", "Years"),
    "region": ("Région", "Region"),
    "all_regions": ("Toutes les régions", "All regions"),
    "department": ("Département", "Department"),
    "all_departments": ("Tous les départements", "All departments"),
    "location": ("Localisation", "Location"),
    "loc_all": ("Toutes", "All"),
    "loc_in": ("En agglomération", "In town"),
    "loc_out": ("Hors agglomération", "Out of town"),
    "threshold": ("Seuil minimal d'accidents pour afficher un taux", "Minimum number of accidents to show a rate"),
    "threshold_help": ("Sous ce nombre d'accidents, un taux n'est pas affiché : il serait trop instable.",
                       "Below this number of accidents, no rate is shown: it would be too unstable."),
    "covid_note": ("2020 : année COVID (confinements), à lire comme une anomalie.",
                   "2020: COVID year (lockdowns), to be read as an anomaly."),
    "whole_country": ("France entière", "All of France"),
    "selection": ("Sélection : {desc}", "Selection: {desc}"),
    "selection_n": ("Sélection : {desc} · {n} accidents", "Selection: {desc} · {n} accidents"),
    "small_sample": ("Taux masqués pour les groupes de moins de {n} accidents. {source}.",
                     "Rates hidden for groups of fewer than {n} accidents. {source}."),
    "source": ("Source : ONISR, accidents corporels 2019-2024 (data.gouv.fr), INSEE 2023",
               "Source: ONISR road injury accidents 2019-2024 (data.gouv.fr), INSEE 2023"),
    "indicator": ("Indicateur", "Indicator"),
    "loading": ("Chargement des données…", "Loading data…"),
    # Welcome dialog
    "welcome_title": ("Bienvenue sur CrashMap France", "Welcome to CrashMap France"),
    "welcome_body": (
        "**CrashMap France** analyse les **327 628 accidents corporels** de la route recensés en France "
        "(métropole et outre-mer) de **2019 à 2024** par l'Observatoire national interministériel de la "
        "sécurité routière (ONISR), soit **19 877 personnes tuées**.\n\n"
        "**La question :** où, quand et dans quelles conditions se produisent les accidents les plus graves, "
        "et quels usagers sont les plus exposés ?\n\n"
        "**Ce que vous trouverez :**\n"
        "- :material/map: la mortalité routière par département ;\n"
        "- :material/schedule: les heures et les jours les plus dangereux ;\n"
        "- :material/rainy: l'effet de la luminosité, de la météo, de la route et de la vitesse ;\n"
        "- :material/group: les usagers les plus exposés, la ceinture et le casque ;\n"
        "- :material/location_on: les points noirs de Toulouse.\n\n"
        "**Comment l'utiliser :** choisissez une page dans le menu de gauche, puis affinez avec les filtres "
        "(années, région, département, en ou hors agglomération). Le thème clair ou sombre se règle dans le "
        "menu ⋮ en haut à droite.\n\n"
        "Projet de portfolio de **Oussama Essalehi** : pipeline Python et SQL, statistiques, cartes et "
        "tableau de bord, à partir de données ouvertes (data.gouv.fr, INSEE).",
        "**CrashMap France** analyses the **327,628 road injury accidents** recorded in France (mainland "
        "and overseas) from **2019 to 2024** by the French road safety observatory (ONISR), in which "
        "**19,877 people were killed**.\n\n"
        "**The question:** where, when and under what conditions do the most serious accidents happen, "
        "and which road users are most at risk?\n\n"
        "**What you will find:**\n"
        "- :material/map: road deaths by department;\n"
        "- :material/schedule: the most dangerous hours and days;\n"
        "- :material/rainy: the effect of light, weather, road type and speed limit;\n"
        "- :material/group: the most exposed road users, seatbelts and helmets;\n"
        "- :material/location_on: the accident black spots of Toulouse.\n\n"
        "**How to use it:** pick a page in the left menu, then refine with the filters (years, region, "
        "department, in or out of town). Switch between light and dark themes in the ⋮ menu at the top "
        "right.\n\n"
        "Portfolio project by **Oussama Essalehi**: Python and SQL pipeline, statistics, maps and dashboard, "
        "built on open data (data.gouv.fr, INSEE).",
    ),
    "welcome_explore": ("Explorer les données", "Explore the data"),
    "welcome_other_lang": ("Read in English", "Lire en français"),
    # Overview
    "ov_title": ("CrashMap France", "CrashMap France"),
    "ov_pitch": ("**Où, quand et dans quelles conditions se produisent les accidents de la route les plus graves "
                 "en France ?** Analyse des accidents corporels recensés par l'ONISR de 2019 à 2024.",
                 "**Where, when and under what conditions do the most serious road accidents happen in France?** "
                 "An analysis of the injury accidents recorded by ONISR from 2019 to 2024."),
    "kpi_accidents": ("Accidents", "Accidents"),
    "kpi_killed": ("Tués", "Killed"),
    "kpi_rate": ("Tués pour 100 accidents", "Killed per 100 accidents"),
    "kpi_100k": ("Tués / 100 000 hab. / an", "Killed / 100,000 pop. / year"),
    "kpi_100k_help": ("Population INSEE 2023 des départements sélectionnés ; moyenne annuelle.",
                      "INSEE 2023 population of the selected departments; yearly average."),
    "kpi_night": ("Part d'accidents de nuit", "Share of night accidents"),
    "kpi_night_help": ("Entre 21h et 6h.", "Between 9pm and 6am."),
    "kpi_out": ("Tués hors agglomération", "Killed out of town"),
    "kpi_out_help": ("Part des tués dans des accidents hors agglomération.",
                     "Share of deaths in accidents outside built-up areas."),
    "vs_prev": (" % vs N-1", " % vs previous year"),
    "ov_by_year": ("Évolution par année", "Trend by year"),
    "injury_accidents": ("Accidents corporels", "Injury accidents"),
    "people_killed": ("Personnes tuées", "People killed"),
    "covid_grey": ("En gris : 2020, année des confinements, à ne pas comparer directement aux autres années.",
                   "In grey: 2020, the lockdown year, not directly comparable with other years."),
    "ov_by_month": ("Accidents par mois", "Accidents by month"),
    "accidents_axis": ("Accidents", "Accidents"),
    "ov_key_points": (
        "**À retenir (France entière, 2019-2024)**\n"
        "- Hors agglomération : **36 %** des accidents mais **67 %** des tués.\n"
        "- La nuit (21h-6h) : **16,5 %** des accidents, **26 %** des tués.\n"
        "- La vitesse maximale autorisée est le facteur le plus lié à la mortalité.\n"
        "- Motards, piétons, cyclistes et seniors sont les usagers les plus exposés.\n"
        "- **3 432 tués en 2024**, -1,9 % seulement par rapport à 2019.",
        "**Key takeaways (all of France, 2019-2024)**\n"
        "- Out of town: **36%** of accidents but **67%** of deaths.\n"
        "- At night (9pm-6am): **16.5%** of accidents, **26%** of deaths.\n"
        "- The speed limit is the factor most strongly linked to fatality.\n"
        "- Motorcyclists, pedestrians, cyclists and older people are the most exposed road users.\n"
        "- **3,432 people killed in 2024**, only 1.9% fewer than in 2019.",
    ),
    # Map
    "map_title": ("Carte de France", "Map of France"),
    "m_killed_100k": ("Tués pour 100 000 habitants par an", "Killed per 100,000 inhabitants per year"),
    "m_acc_100k": ("Accidents pour 100 000 habitants par an", "Accidents per 100,000 inhabitants per year"),
    "m_killed_100": ("Tués pour 100 accidents", "Killed per 100 accidents"),
    "map_grey": ("Départements en gris : moins d'accidents que le seuil choisi, ou hors de la sélection.",
                 "Departments in grey: fewer accidents than the chosen threshold, or outside the selection."),
    "top10": ("Les 10 départements les plus touchés", "The 10 most affected departments"),
    "bottom10": ("Les 10 départements les moins touchés", "The 10 least affected departments"),
    "col_department": ("Département", "Department"),
    "col_rate": ("Taux", "Rate"),
    "col_accidents": ("Accidents", "Accidents"),
    "col_killed": ("Tués", "Killed"),
    "col_code": ("Code", "Code"),
    "overseas": ("Outre-mer", "Overseas"),
    "col_territory": ("Territoire", "Territory"),
    "col_zone": ("Zone", "Zone"),
    "col_population": ("Population 2023", "Population 2023"),
    "overseas_note": ("Mayotte, Wallis-et-Futuna, la Polynésie française et la Nouvelle-Calédonie n'ont pas de "
                      "population de référence INSEE 2023 : pas de taux par habitant.",
                      "Mayotte, Wallis and Futuna, French Polynesia and New Caledonia have no INSEE 2023 "
                      "reference population: no per-inhabitant rate."),
    # When
    "when_title": ("Quand ?", "When?"),
    "when_grid": ("Jour de la semaine × heure", "Day of week × hour"),
    "w_rate": ("Tués pour 100 accidents", "Killed per 100 accidents"),
    "w_count": ("Nombre d'accidents", "Number of accidents"),
    "when_grid_note": ("Cases vides : moins d'accidents que le seuil. Les accidents entre minuit et 6h sont les plus "
                       "graves, quel que soit le jour.",
                       "Empty cells: fewer accidents than the threshold. Accidents between midnight and 6am "
                       "are the most severe, whatever the day."),
    "by_band": ("Par tranche horaire", "By time band"),
    "night_share": ("La nuit représente **{acc} %** des accidents et **{killed} %** des tués de la sélection.",
                    "Night accounts for **{acc}%** of accidents and **{killed}%** of deaths in the selection."),
    "by_month": ("Par mois", "By month"),
    "week_or_weekend": ("Semaine ou week-end", "Weekday or weekend"),
    "weekday_label": ("Semaine", "Weekday"),
    "weekend_label": ("Week-end", "Weekend"),
    "pct_fatal_axis": ("% d'accidents mortels (IC 95 % Wilson)", "% fatal accidents (95% Wilson CI)"),
    "hover_rate": ("tués / 100 accidents", "killed / 100 accidents"),
    "hover_accidents": ("accidents", "accidents"),
    "hover_cases": ("cas", "cases"),
    "hover_ci": ("IC", "CI"),
    # Conditions
    "cond_title": ("Dans quelles conditions ?", "Under what conditions?"),
    "factor": ("Facteur", "Factor"),
    "f_lum": ("Luminosité", "Light"),
    "f_atm": ("Conditions météo", "Weather"),
    "f_surf": ("État de la surface", "Road surface"),
    "f_catr": ("Catégorie de route", "Road category"),
    "f_vma": ("Vitesse maximale autorisée", "Speed limit"),
    "f_int": ("Type d'intersection", "Intersection type"),
    "f_plan": ("Tracé de la route", "Road alignment"),
    "f_col": ("Type de collision", "Collision type"),
    "show_table": ("Voir le tableau", "Show table"),
    "col_rate100": ("Tués / 100 acc.", "Killed / 100 acc."),
    "col_pct_fatal": ("% mortels", "% fatal"),
    "speed_location": ("Vitesse autorisée et localisation", "Speed limit and location"),
    "pct_fatal_short": ("% d'accidents mortels", "% fatal accidents"),
    "model_title": ("Quels facteurs comptent vraiment ? (à autres facteurs égaux)",
                    "Which factors really matter? (all else being equal)"),
    "model_intro": ("Une régression logistique sur 322 020 accidents (2019-2024, France entière) mesure l'effet de "
                    "chaque facteur **en tenant compte des autres**. Un *odds ratio* de 2 signifie que la cote d'un "
                    "accident mortel est doublée par rapport à la modalité de référence. Ces résultats portent sur "
                    "toute la période et ne suivent pas les filtres.",
                    "A logistic regression on 322,020 accidents (2019-2024, all of France) measures the effect of "
                    "each factor **while accounting for the others**. An *odds ratio* of 2 means the odds of a fatal "
                    "accident are doubled compared with the reference level. These results cover the whole period "
                    "and do not follow the filters."),
    "ref": ("réf.", "ref."),
    "or_axis": ("Odds ratio (échelle log) - rouge : aggravant, bleu : protecteur, gris : non significatif",
                "Odds ratio (log scale) - red: aggravating, blue: protective, grey: not significant"),
    # Who
    "who_title": ("Qui ?", "Who?"),
    "who_caption": ("Sélection : {desc} · {n} personnes impliquées (gravité connue)",
                    "Selection: {desc} · {n} people involved (known severity)"),
    "travel_mode": ("Mode de déplacement", "Travel mode"),
    "risk_title": ("Risque d'être tué quand on est impliqué", "Risk of being killed when involved"),
    "risk_axis": ("% de tués parmi les impliqués (IC 95 %)", "% killed among those involved (95% CI)"),
    "mode_note": ("Les piétons sont comptés à part ; les autres usagers selon le véhicule qu'ils occupaient.",
                  "Pedestrians are counted separately; other users by the vehicle they were in."),
    "age_sex": ("Âge et sexe", "Age and sex"),
    "men": ("Hommes", "Men"),
    "women": ("Femmes", "Women"),
    "killed_axis": ("Personnes tuées", "People killed"),
    "age_note": ("Part de tués parmi les personnes impliquées : **{young} %** chez les 25-34 ans, **{old} %** chez "
                 "les 75 ans et plus.",
                 "Share killed among people involved: **{young}%** for 25-34 year-olds, **{old}%** for people "
                 "aged 75 and over."),
    "equipment": ("Équipement de sécurité", "Safety equipment"),
    "worn": ("Équipement porté", "Equipment worn"),
    "not_worn": ("Équipement non porté", "Equipment not worn"),
    "eq_axis": ("% de tués parmi les usagers impliqués (IC 95 % Wilson)", "% killed among users involved (95% Wilson CI)"),
    "eq_hover": ("tués sur", "killed out of"),
    "people": ("personnes", "people"),
    "eq_note": ("Association, pas causalité : ne pas porter d'équipement va souvent avec d'autres comportements à "
                "risque, et l'équipement est déclaré après l'accident. Chez les cyclistes, les casqués roulent plus "
                "souvent hors agglomération et plus vite, ce qui explique un taux un peu plus élevé.",
                "Association, not causation: not wearing equipment often goes with other risky behaviour, and "
                "equipment is recorded after the accident. Helmeted cyclists ride more often out of town and "
                "faster, which explains their slightly higher rate."),
    "eq_car_drivers": ("Conducteurs de voiture (ceinture)", "Car drivers (seatbelt)"),
    "eq_car_passengers": ("Passagers de voiture (ceinture)", "Car passengers (seatbelt)"),
    "eq_moto_big": ("Conducteurs de moto > 125 cm3 (casque)", "Motorcyclists > 125 cc (helmet)"),
    "eq_moto_mid": ("Conducteurs de moto 50-125 cm3 (casque)", "Motorcyclists 50-125 cc (helmet)"),
    "eq_moped": ("Conducteurs de cyclomoteur (casque)", "Moped riders (helmet)"),
    "eq_cyclists": ("Cyclistes (casque)", "Cyclists (helmet)"),
    "eq_edp": ("Conducteurs d'EDP motorisé (casque)", "E-scooter riders (helmet)"),
    # Hotspots
    "hs_title": ("Points noirs à Toulouse", "Toulouse black spots"),
    "hs_caption": ("Années {y0}-{y1} · {n} accidents géolocalisés précisément (les filtres de région, département "
                   "et localisation ne s'appliquent pas à cette page).",
                   "Years {y0}-{y1} · {n} precisely located accidents (region, department and location filters do "
                   "not apply to this page)."),
    "hs_located": ("Accidents géolocalisés", "Located accidents"),
    "hs_fatal": ("Accidents mortels", "Fatal accidents"),
    "hs_display": ("Affichage", "Display"),
    "hs_density": ("Densité des accidents", "Accident density"),
    "hs_dbscan": ("Points noirs (DBSCAN)", "Black spots (DBSCAN)"),
    "hs_fatal_marker": ("Accident mortel", "Fatal accident"),
    "hs_accident": ("Accident", "Accident"),
    "hs_spot": ("Point noir", "Black spot"),
    "hs_spot_n": ("Point noir n°", "Black spot #"),
    "hs_light": ("Luminosité", "Light"),
    "hs_road": ("Route", "Road"),
    "hs_hosp": ("hospitalisés", "hospitalised"),
    "hs_top10": ("Les 10 points noirs", "The 10 black spots"),
    "hs_method": ("Regroupement **DBSCAN** des accidents précisément géolocalisés de 2019 à 2024 : un point noir "
                  "rassemble au moins 8 accidents situés à moins de 100 m les uns des autres.",
                  "**DBSCAN** clustering of precisely located accidents from 2019 to 2024: a black spot groups at "
                  "least 8 accidents within 100 m of each other."),
    "col_rank": ("Rang", "Rank"),
    "col_address": ("Adresse principale", "Main address"),
    "col_hosp": ("Blessés hospitalisés", "Hospitalised"),
    "col_vulnerable": ("Piétons, cyclistes, EDP", "Pedestrians, cyclists, PMD"),
    "col_from": ("Depuis", "From"),
    "col_to": ("Jusqu'à", "To"),
    "osm_credit": ("Fond de carte © les contributeurs d'OpenStreetMap.", "Base map © OpenStreetMap contributors."),
    # About
    "about_md": (
        """
### Données
* **ONISR**, bases annuelles des accidents corporels de la circulation routière, 2019 à 2024 :
  4 fichiers par an (caractéristiques, lieux, véhicules, usagers), téléchargés via l'API de data.gouv.fr.
  La structure a changé en 2019 : les années antérieures sont exclues.
* **INSEE**, populations de référence 2023, pour les taux par habitant.
* **Contours des départements** : IGN Admin Express via le projet *france-geojson* (Licence Ouverte).

### Méthode
* **Trois grains séparés** (accident, véhicule, personne). Joindre les 4 fichiers donne une ligne par
  personne (745 158 lignes pour 327 628 accidents) : compter des accidents sur cette jointure les
  surestimerait de 2,3 fois. Les accidents sont donc toujours comptés au grain accident.
* Codes `-1` et « non renseigné » convertis en valeurs vides, jamais en catégorie ; tous les codes
  décodés d'après la documentation officielle de l'ONISR.
* **Tués** (décès dans les 30 jours) comme indicateur principal : la catégorie « blessé hospitalisé »
  n'est plus labellisée depuis 2019.
* **Taux masqués** sous un seuil d'accidents (100 par défaut, réglable dans la barre latérale).
* **Intervalles de confiance de Wilson** à 95 % pour les parts d'accidents mortels.
* **Régression logistique** pour mesurer chaque facteur à autres facteurs égaux ; **DBSCAN** pour les
  points noirs.
* Contrôles : tests automatisés ; tués par an identiques aux bilans officiels de l'ONISR ; résultats
  SQL et Python identiques.

### Limites
* Pas de données de trafic : les taux sont rapportés aux habitants, pas aux kilomètres parcourus.
* Tous les accidents ne sont pas géolocalisés précisément ; certaines données personnelles sont occultées.
* Les écarts liés à l'équipement de sécurité ou aux conditions décrivent des **associations**, pas des
  causes.

### Le projet
Pipeline complet (Python, PostgreSQL, tableau de bord Power BI) : [{repo}]({repo})

**Oussama Essalehi** · [LinkedIn](https://www.linkedin.com/in/oussama-essalehi) ·
[oussama-essalehi.dev](https://oussama-essalehi.dev)
""",
        """
### Data
* **ONISR** (French road safety observatory), annual road injury accident databases, 2019 to 2024:
  4 files per year (characteristics, places, vehicles, users), downloaded through the data.gouv.fr API.
  The format changed in 2019, so earlier years are excluded.
* **INSEE**, 2023 reference populations, for per-inhabitant rates.
* **Department outlines**: IGN Admin Express via the *france-geojson* project (Open Licence).

### Method
* **Three separate grains** (accident, vehicle, person). Joining the 4 files gives one row per person
  (745,158 rows for 327,628 accidents): counting accidents on that join would overstate them 2.3 times.
  Accidents are therefore always counted at the accident grain.
* `-1` and "not filled in" codes are turned into missing values, never into a category; every code is
  decoded from ONISR's official documentation.
* **Deaths** (within 30 days) as the main indicator: the "hospitalised" category has not been certified
  as official statistics since 2019.
* **Rates hidden** below a minimum number of accidents (100 by default, adjustable in the sidebar).
* **Wilson 95% confidence intervals** for shares of fatal accidents.
* **Logistic regression** to measure each factor all else being equal; **DBSCAN** for black spots.
* Checks: automated tests; yearly deaths identical to ONISR's official reports; SQL and Python results
  identical.

### Limitations
* No traffic data: rates are per inhabitant, not per kilometre driven.
* Not every accident is precisely geolocated; some personal details are withheld in the open data.
* Differences linked to safety equipment or conditions describe **associations**, not causes.

### The project
Full pipeline (Python, PostgreSQL, Power BI dashboard): [{repo}]({repo})

**Oussama Essalehi** · [LinkedIn](https://www.linkedin.com/in/oussama-essalehi) ·
[oussama-essalehi.dev](https://oussama-essalehi.dev)
""",
    ),
}

WEEKDAYS = {"fr": ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"],
            "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
MONTHS = {"fr": ["Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin", "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."],
          "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]}

# Data labels (French, as stored) -> English
VALUES_EN: dict[str, str] = {
    # Light
    "Plein jour": "Daylight", "Crépuscule ou aube": "Dusk or dawn",
    "Nuit sans éclairage public": "Night, no street lighting",
    "Nuit avec éclairage public non allumé": "Night, street lighting off",
    "Nuit avec éclairage public allumé": "Night, street lighting on",
    # Weather
    "Normale": "Normal", "Pluie légère": "Light rain", "Pluie forte": "Heavy rain", "Pluie": "Rain",
    "Neige - grêle": "Snow / hail", "Brouillard - fumée": "Fog / smoke", "Vent fort - tempête": "Strong wind / storm",
    "Temps éblouissant": "Dazzling light", "Temps couvert": "Overcast", "Autre": "Other",
    # Surface
    "Mouillée": "Wet", "Flaques": "Puddles", "Inondée": "Flooded", "Enneigée": "Snow-covered", "Boue": "Mud",
    "Verglacée": "Icy", "Corps gras - huile": "Oil / grease", "Neige / verglas": "Snow / ice",
    # Road category
    "Autoroute": "Motorway", "Route nationale": "National road", "Route départementale": "Departmental road",
    "Voie communale": "Local road", "Hors réseau public": "Off public network",
    "Parc de stationnement ouvert à la circulation publique": "Public car park",
    "Route de métropole urbaine": "Metropolitan road", "Autre / parking": "Other / car park",
    # Intersection
    "Hors intersection": "No intersection", "Intersection en X": "X intersection", "Intersection en T": "T intersection",
    "Intersection en Y": "Y intersection", "Intersection à plus de 4 branches": "Intersection with 5+ branches",
    "Giratoire": "Roundabout", "Place": "Square", "Passage à niveau": "Level crossing",
    "Autre intersection": "Other intersection", "Intersection X/T/Y": "X/T/Y intersection",
    # Alignment
    "Partie rectiligne": "Straight", "En courbe à gauche": "Left bend", "En courbe à droite": "Right bend",
    "En « S »": "S-bend",
    # Collision
    "Deux véhicules - frontale": "Two vehicles - head-on", "Deux véhicules - par l'arrière": "Two vehicles - rear-end",
    "Deux véhicules - par le côté": "Two vehicles - side impact",
    "Trois véhicules et plus - en chaîne": "Three+ vehicles - pile-up",
    "Trois véhicules et plus - collisions multiples": "Three+ vehicles - multiple collisions",
    "Autre collision": "Other collision", "Sans collision": "No collision",
    # Time bands
    "Nuit (21h-6h)": "Night (9pm-6am)", "Matin (6h-10h)": "Morning (6-10am)",
    "Journée (10h-17h)": "Daytime (10am-5pm)", "Soirée (17h-21h)": "Evening (5-9pm)",
    # Travel modes and user categories
    "Voiture (VL)": "Car", "Moto > 125 cm3": "Motorcycle > 125 cc", "Moto 50-125 cm3": "Motorcycle 50-125 cc",
    "Cyclomoteur <= 50 cm3": "Moped <= 50 cc", "Piéton": "Pedestrian", "Vélo (y.c. VAE)": "Bicycle (incl. e-bike)",
    "EDP motorisé (trottinette...)": "E-scooter (powered PMD)", "EDP non motorisé": "Unpowered PMD",
    "Utilitaire (VU)": "Van", "Poids lourd": "Heavy goods vehicle", "Bus / car": "Bus / coach",
    "Train / tramway": "Train / tram", "Quad": "Quad", "Voiturette": "Microcar",
    "Engin spécial / agricole": "Special / farm vehicle", "Autre / indéterminé": "Other / unknown",
    "Conducteur": "Driver", "Passager": "Passenger",
    # Age bands and sex
    "0-13 ans": "0-13 yrs", "14-17 ans": "14-17 yrs", "18-24 ans": "18-24 yrs", "25-34 ans": "25-34 yrs",
    "35-44 ans": "35-44 yrs", "45-54 ans": "45-54 yrs", "55-64 ans": "55-64 yrs", "65-74 ans": "65-74 yrs",
    "75 ans et +": "75+ yrs", "Masculin": "Male", "Féminin": "Female",
    # Zones and region
    "Métropole": "Mainland France", "Outre-mer (DROM)": "Overseas (DROM)", "Outre-mer (COM)": "Overseas (COM)",
    "Collectivités d'outre-mer": "Overseas collectivities",
    # Model labels
    "Tranche horaire": "Time band", "Type de jour": "Day type", "Luminosité": "Light", "Météo": "Weather",
    "Surface": "Road surface", "Catégorie de route": "Road category", "Vitesse maximale autorisée": "Speed limit",
    "Localisation": "Location", "Intersection": "Intersection", "Deux-roues ou EDP impliqué": "Two-wheeler or PMD involved",
    "Piéton impliqué": "Pedestrian involved", "Nombre de véhicules": "Number of vehicles",
    "1 véhicule": "1 vehicle", "2 véhicules": "2 vehicles", "3 véhicules et +": "3+ vehicles",
    "Oui": "Yes", "Non": "No", "Semaine": "Weekday", "Week-end": "Weekend",
    "En agglomération": "In town", "Hors agglomération": "Out of town",
}


def lang() -> str:
    """Current language: the sidebar choice, else the browser language, else French."""
    value = st.session_state.get("lang")
    if value in LANGUAGES:
        return value
    return default_lang()


def default_lang() -> str:
    try:
        locale = (st.context.locale or "").lower()
    except Exception:  # no browser context (tests, bare mode)
        locale = ""
    return "en" if locale and not locale.startswith("fr") else "fr"


def t(key: str, **kwargs) -> str:
    text = UI[key][0 if lang() == "fr" else 1]
    return text.format(**kwargs) if kwargs else text


def tv(value):
    """Translate one data label for display (unchanged in French or when unknown)."""
    if lang() == "fr" or not isinstance(value, str):
        return value
    return VALUES_EN.get(value, value)


def tv_series(series: pd.Series) -> pd.Series:
    if lang() == "fr":
        return series.astype(str)
    return series.astype(str).map(lambda v: VALUES_EN.get(v, v))


def weekdays() -> list[str]:
    return WEEKDAYS[lang()]


def months() -> list[str]:
    return MONTHS[lang()]


def num(value, digits: int = 0, suffix: str = "") -> str:
    """Number formatting: '1 234,5' in French, '1,234.5' in English; '-' when missing."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "-"
    text = f"{value:,.{digits}f}"
    if lang() == "fr":
        text = text.replace(",", " ").replace(".", ",")
        return text + suffix
    return text + suffix.replace(" %", "%")


def plotly_separators() -> str:
    """Plotly 'separators' (decimal then thousands) for the current language."""
    return ", " if lang() == "fr" else ".,"
