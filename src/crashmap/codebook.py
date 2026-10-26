"""Code-to-label mappings for the ONISR annual road accident files (2019 format).

Reference document: "Description des bases de données annuelles des accidents corporels de la
circulation routière - Années de 2005 à 2024", ONISR, 21 October 2025
(``description-des-bases-de-donnees-annuelles.pdf`` on data.gouv.fr, downloaded to
``data/raw/onisr/``). Page numbers below refer to that PDF.

General rule (PDF p.3): most variables may contain an empty cell, a zero or a dot, which all mean
"not filled in by the police" or "not applicable". The code ``-1`` explicitly means "Non renseigné".
``MISSING_CODES`` lists, per variable, which codes are converted to null. Codes that carry a real
meaning ("0 - Aucun", "0 - Sans objet", "0 - Aucun équipement") are kept as categories.

The groupings at the end of the file (vehicle groups, speed bands, age bands...) are project
definitions, not ONISR codes; they are documented in docs/methodology.md.
"""

from __future__ import annotations

# --------------------------------------------------------------------------------------------
# CARACTERISTIQUES
# --------------------------------------------------------------------------------------------

# PDF p.4 - "lum": lighting conditions
LUM = {
    1: "Plein jour",
    2: "Crépuscule ou aube",
    3: "Nuit sans éclairage public",
    4: "Nuit avec éclairage public non allumé",
    5: "Nuit avec éclairage public allumé",
}

# PDF p.4 - "agg": localisation
AGG = {
    1: "Hors agglomération",
    2: "En agglomération",
}

# PDF p.4 - "int": intersection
INT = {
    1: "Hors intersection",
    2: "Intersection en X",
    3: "Intersection en T",
    4: "Intersection en Y",
    5: "Intersection à plus de 4 branches",
    6: "Giratoire",
    7: "Place",
    8: "Passage à niveau",
    9: "Autre intersection",
}

# PDF p.5 - "atm": atmospheric conditions
ATM = {
    1: "Normale",
    2: "Pluie légère",
    3: "Pluie forte",
    4: "Neige - grêle",
    5: "Brouillard - fumée",
    6: "Vent fort - tempête",
    7: "Temps éblouissant",
    8: "Temps couvert",
    9: "Autre",
}

# PDF p.5 - "col": type of collision
COL = {
    1: "Deux véhicules - frontale",
    2: "Deux véhicules - par l'arrière",
    3: "Deux véhicules - par le côté",
    4: "Trois véhicules et plus - en chaîne",
    5: "Trois véhicules et plus - collisions multiples",
    6: "Autre collision",
    7: "Sans collision",
}

# --------------------------------------------------------------------------------------------
# LIEUX
# --------------------------------------------------------------------------------------------

# PDF p.5 - "catr": road category
CATR = {
    1: "Autoroute",
    2: "Route nationale",
    3: "Route départementale",
    4: "Voie communale",
    5: "Hors réseau public",
    6: "Parc de stationnement ouvert à la circulation publique",
    7: "Route de métropole urbaine",
    9: "Autre",
}

# PDF p.6 - "circ": traffic regime
CIRC = {
    1: "A sens unique",
    2: "Bidirectionnelle",
    3: "A chaussées séparées",
    4: "Avec voies d'affectation variable",
}

# PDF p.6 - "vosp": reserved lane
VOSP = {
    0: "Sans objet",
    1: "Piste cyclable",
    2: "Bande cyclable",
    3: "Voie réservée",
}

# PDF p.6 - "prof": longitudinal profile
PROF = {
    1: "Plat",
    2: "Pente",
    3: "Sommet de côte",
    4: "Bas de côte",
}

# PDF p.6 - "plan": horizontal alignment (layout)
PLAN = {
    1: "Partie rectiligne",
    2: "En courbe à gauche",
    3: "En courbe à droite",
    4: "En « S »",
}

# PDF p.6-7 - "surf": road surface condition
SURF = {
    1: "Normale",
    2: "Mouillée",
    3: "Flaques",
    4: "Inondée",
    5: "Enneigée",
    6: "Boue",
    7: "Verglacée",
    8: "Corps gras - huile",
    9: "Autre",
}

# PDF p.7 - "infra": infrastructure
INFRA = {
    0: "Aucun",
    1: "Souterrain - tunnel",
    2: "Pont - autopont",
    3: "Bretelle d'échangeur ou de raccordement",
    4: "Voie ferrée",
    5: "Carrefour aménagé",
    6: "Zone piétonne",
    7: "Zone de péage",
    8: "Chantier",
    9: "Autres",
}

# PDF p.7 - "situ": situation of the accident
SITU = {
    0: "Aucun",
    1: "Sur chaussée",
    2: "Sur bande d'arrêt d'urgence",
    3: "Sur accotement",
    4: "Sur trottoir",
    5: "Sur piste cyclable",
    6: "Sur autre voie spéciale",
    8: "Autres",
}

# --------------------------------------------------------------------------------------------
# VEHICULES
# --------------------------------------------------------------------------------------------

# PDF p.7-8 - "senc": direction of traffic ("0 - Inconnu" is treated as missing)
SENC = {
    1: "PK ou PR ou numéro d'adresse postale croissant",
    2: "PK ou PR ou numéro d'adresse postale décroissant",
    3: "Absence de repère",
}

# PDF p.8 - "catv": vehicle category (codes 04-06, 08-09, 11-12, 18-19 unused since 2006)
CATV = {
    0: "Indéterminable",
    1: "Bicyclette",
    2: "Cyclomoteur <50cm3",
    3: "Voiturette (quadricycle à moteur carrossé)",
    7: "VL seul",
    10: "VU seul 1,5T <= PTAC <= 3,5T avec ou sans remorque",
    13: "PL seul 3,5T < PTCA <= 7,5T",
    14: "PL seul > 7,5T",
    15: "PL > 3,5T + remorque",
    16: "Tracteur routier seul",
    17: "Tracteur routier + semi-remorque",
    20: "Engin spécial",
    21: "Tracteur agricole",
    30: "Scooter < 50 cm3",
    31: "Motocyclette > 50 cm3 et <= 125 cm3",
    32: "Scooter > 50 cm3 et <= 125 cm3",
    33: "Motocyclette > 125 cm3",
    34: "Scooter > 125 cm3",
    35: "Quad léger <= 50 cm3",
    36: "Quad lourd > 50 cm3",
    37: "Autobus",
    38: "Autocar",
    39: "Train",
    40: "Tramway",
    41: "3RM <= 50 cm3",
    42: "3RM > 50 cm3 <= 125 cm3",
    43: "3RM > 125 cm3",
    50: "EDP à moteur",
    60: "EDP sans moteur",
    80: "VAE",
    99: "Autre véhicule",
}

# PDF p.8-9 - "obs": fixed obstacle hit
OBS = {
    0: "Sans objet",
    1: "Véhicule en stationnement",
    2: "Arbre",
    3: "Glissière métallique",
    4: "Glissière béton",
    5: "Autre glissière",
    6: "Bâtiment, mur, pile de pont",
    7: "Support de signalisation verticale ou poste d'appel d'urgence",
    8: "Poteau",
    9: "Mobilier urbain",
    10: "Parapet",
    11: "Ilot, refuge, borne haute",
    12: "Bordure de trottoir",
    13: "Fossé, talus, paroi rocheuse",
    14: "Autre obstacle fixe sur chaussée",
    15: "Autre obstacle fixe sur trottoir ou accotement",
    16: "Sortie de chaussée sans obstacle",
    17: "Buse - tête d'aqueduc",
}

# PDF p.9 - "obsm": mobile obstacle hit
OBSM = {
    0: "Aucun",
    1: "Piéton",
    2: "Véhicule",
    4: "Véhicule sur rail",
    5: "Animal domestique",
    6: "Animal sauvage",
    9: "Autre",
}

# PDF p.9 - "choc": initial point of impact
CHOC = {
    0: "Aucun",
    1: "Avant",
    2: "Avant droit",
    3: "Avant gauche",
    4: "Arrière",
    5: "Arrière droit",
    6: "Arrière gauche",
    7: "Côté droit",
    8: "Côté gauche",
    9: "Chocs multiples (tonneaux)",
}

# PDF p.9-10 - "manv": main manoeuvre before the accident ("0 - Inconnue" treated as missing)
MANV = {
    1: "Sans changement de direction",
    2: "Même sens, même file",
    3: "Entre 2 files",
    4: "En marche arrière",
    5: "A contresens",
    6: "En franchissant le terre-plein central",
    7: "Dans le couloir bus, dans le même sens",
    8: "Dans le couloir bus, dans le sens inverse",
    9: "En s'insérant",
    10: "En faisant demi-tour sur la chaussée",
    11: "Changeant de file à gauche",
    12: "Changeant de file à droite",
    13: "Déporté à gauche",
    14: "Déporté à droite",
    15: "Tournant à gauche",
    16: "Tournant à droite",
    17: "Dépassant à gauche",
    18: "Dépassant à droite",
    19: "Traversant la chaussée",
    20: "Manœuvre de stationnement",
    21: "Manœuvre d'évitement",
    22: "Ouverture de porte",
    23: "Arrêté (hors stationnement)",
    24: "En stationnement (avec occupants)",
    25: "Circulant sur trottoir",
    26: "Autres manœuvres",
}

# PDF p.10 - "motor": engine type ("0 - Inconnue" treated as missing)
MOTOR = {
    1: "Hydrocarbures",
    2: "Hybride électrique",
    3: "Electrique",
    4: "Hydrogène",
    5: "Humaine",
    6: "Autre",
}

# --------------------------------------------------------------------------------------------
# USAGERS
# --------------------------------------------------------------------------------------------

# PDF p.11 - "catu": user category
CATU = {
    1: "Conducteur",
    2: "Passager",
    3: "Piéton",
}

# PDF p.11 - "grav": injury severity
GRAV = {
    1: "Indemne",
    2: "Tué",
    3: "Blessé hospitalisé",
    4: "Blessé léger",
}
GRAV_UNHURT, GRAV_KILLED, GRAV_HOSPITALIZED, GRAV_LIGHT = 1, 2, 3, 4

# PDF p.11 - "sexe"
SEXE = {
    1: "Masculin",
    2: "Féminin",
}

# PDF p.11 - "trajet": purpose of the trip ("0 - Non renseigné" treated as missing)
TRAJET = {
    1: "Domicile - travail",
    2: "Domicile - école",
    3: "Courses - achats",
    4: "Utilisation professionnelle",
    5: "Promenade - loisirs",
    9: "Autre",
}

# PDF p.11-12 - "secu1", "secu2", "secu3": safety equipment used (up to 3 per user since 2019)
SECU = {
    0: "Aucun équipement",
    1: "Ceinture",
    2: "Casque",
    3: "Dispositif enfants",
    4: "Gilet réfléchissant",
    5: "Airbag (2RM/3RM)",
    6: "Gants (2RM/3RM)",
    7: "Gants + Airbag (2RM/3RM)",
    8: "Non déterminable",
    9: "Autre",
}
SECU_NONE, SECU_SEATBELT, SECU_HELMET, SECU_UNDETERMINABLE = 0, 1, 2, 8

# PDF p.12 - "locp": pedestrian location
LOCP = {
    0: "Sans objet",
    1: "Sur chaussée - à + 50 m du passage piéton",
    2: "Sur chaussée - à - 50 m du passage piéton",
    3: "Sur passage piéton - sans signalisation lumineuse",
    4: "Sur passage piéton - avec signalisation lumineuse",
    5: "Sur trottoir",
    6: "Sur accotement",
    7: "Sur refuge ou BAU",
    8: "Sur contre allée",
    9: "Inconnue",
}

# PDF p.12-13 - "actp": pedestrian action (alphanumeric codes A and B)
ACTP = {
    "1": "Se déplaçant - sens véhicule heurtant",
    "2": "Se déplaçant - sens inverse du véhicule",
    "3": "Traversant",
    "4": "Masqué",
    "5": "Jouant - courant",
    "6": "Avec animal",
    "9": "Autre",
    "A": "Monte/descend du véhicule",
    "B": "Inconnue",
}

# PDF p.13 - "etatp": pedestrian alone or not
ETATP = {
    1: "Seul",
    2: "Accompagné",
    3: "En groupe",
}

# --------------------------------------------------------------------------------------------
# Missing-value codes per variable (PDF p.3 general rule + "-1 - Non renseigné" in each list)
# --------------------------------------------------------------------------------------------

MISSING_CODES: dict[str, set] = {
    # caracteristiques
    "lum": {-1, 0},
    "agg": {-1, 0},
    "int": {-1, 0},
    "atm": {-1, 0},
    "col": {-1, 0},
    # lieux
    "catr": {-1, 0},
    "circ": {-1, 0},
    "vosp": {-1},
    "prof": {-1, 0},
    "plan": {-1, 0},
    "surf": {-1, 0},
    "infra": {-1},
    "situ": {-1},
    "vma": {-1, 0},
    "nbv": {-1},
    # vehicules
    "senc": {-1, 0},
    "catv": {-1},
    "obs": {-1},
    "obsm": {-1},
    "choc": {-1},
    "manv": {-1, 0},
    "motor": {-1, 0},
    # usagers
    "place": {-1, 0},
    "catu": {-1, 0},
    "grav": {-1, 0},
    "sexe": {-1, 0},
    "trajet": {-1, 0},
    "secu1": {-1},
    "secu2": {-1},
    "secu3": {-1},
    "locp": {-1},
    "actp": {"-1", "0"},
    "etatp": {-1, 0},
}

# Variable -> mapping, used to decode every coded column into a "<var>_label" column.
LABELS: dict[str, dict] = {
    "lum": LUM,
    "agg": AGG,
    "int": INT,
    "atm": ATM,
    "col": COL,
    "catr": CATR,
    "circ": CIRC,
    "vosp": VOSP,
    "prof": PROF,
    "plan": PLAN,
    "surf": SURF,
    "infra": INFRA,
    "situ": SITU,
    "senc": SENC,
    "catv": CATV,
    "obs": OBS,
    "obsm": OBSM,
    "choc": CHOC,
    "manv": MANV,
    "motor": MOTOR,
    "catu": CATU,
    "grav": GRAV,
    "sexe": SEXE,
    "trajet": TRAJET,
    "secu1": SECU,
    "secu2": SECU,
    "secu3": SECU,
    "locp": LOCP,
    "actp": ACTP,
    "etatp": ETATP,
}

# --------------------------------------------------------------------------------------------
# Project groupings (not ONISR codes) - see docs/methodology.md
# --------------------------------------------------------------------------------------------

# Vehicle category (catv) -> analysis group
VEHICLE_GROUP: dict[int, str] = {
    1: "Vélo (y.c. VAE)",
    80: "Vélo (y.c. VAE)",
    50: "EDP motorisé (trottinette...)",
    60: "EDP non motorisé",
    2: "Cyclomoteur <= 50 cm3",
    30: "Cyclomoteur <= 50 cm3",
    41: "Cyclomoteur <= 50 cm3",
    31: "Moto 50-125 cm3",
    32: "Moto 50-125 cm3",
    42: "Moto 50-125 cm3",
    33: "Moto > 125 cm3",
    34: "Moto > 125 cm3",
    43: "Moto > 125 cm3",
    3: "Voiturette",
    7: "Voiture (VL)",
    10: "Utilitaire (VU)",
    13: "Poids lourd",
    14: "Poids lourd",
    15: "Poids lourd",
    16: "Poids lourd",
    17: "Poids lourd",
    37: "Bus / car",
    38: "Bus / car",
    39: "Train / tramway",
    40: "Train / tramway",
    35: "Quad",
    36: "Quad",
    20: "Engin spécial / agricole",
    21: "Engin spécial / agricole",
    0: "Autre / indéterminé",
    99: "Autre / indéterminé",
}

# Motorised two- and three-wheelers (2RM/3RM)
MOTORISED_TWO_WHEELERS = {2, 30, 31, 32, 33, 34, 41, 42, 43}
BICYCLES = {1, 80}
PERSONAL_MOBILITY = {50, 60}  # EDP: e-scooters, monowheels, kick scooters...
# "Two-wheeler involved" flag = motorised 2RM/3RM + bicycles + EDP (unprotected vehicle users)
TWO_WHEELERS = MOTORISED_TWO_WHEELERS | BICYCLES | PERSONAL_MOBILITY
HEAVY_VEHICLES = {13, 14, 15, 16, 17, 37, 38}

# Ordering used to pick the main road when "lieux" has several rows for one accident
# (lower = higher in the road hierarchy). Category 7 (urban metropolitan roads) are former
# departmental roads, placed just after them.
ROAD_PRIORITY = {1: 1, 2: 2, 3: 3, 7: 4, 4: 5, 9: 6, 6: 7, 5: 8}

# Weekday labels (Monday = 0)
WEEKDAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MONTHS = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]

# Time bands by hour of day (project definition)
TIME_BANDS = [
    ("Nuit (21h-6h)", list(range(21, 24)) + list(range(0, 6))),
    ("Matin (6h-10h)", list(range(6, 10))),
    ("Journée (10h-17h)", list(range(10, 17))),
    ("Soirée (17h-21h)", list(range(17, 21))),
]
HOUR_TO_TIME_BAND = {h: label for label, hours in TIME_BANDS for h in hours}
TIME_BAND_ORDER = [label for label, _ in TIME_BANDS]

# Age bands (ONISR-style)
AGE_BANDS = [
    (0, 13, "0-13 ans"),
    (14, 17, "14-17 ans"),
    (18, 24, "18-24 ans"),
    (25, 34, "25-34 ans"),
    (35, 44, "35-44 ans"),
    (45, 54, "45-54 ans"),
    (55, 64, "55-64 ans"),
    (65, 74, "65-74 ans"),
    (75, 200, "75 ans et +"),
]

# Speed limit bands (vma, km/h)
SPEED_BANDS = [
    (0, 30, "<= 30 km/h"),
    (31, 50, "40-50 km/h"),
    (51, 70, "60-70 km/h"),
    (71, 90, "80-90 km/h"),
    (91, 110, "100-110 km/h"),
    (111, 130, "130 km/h"),
]
MAX_PLAUSIBLE_VMA = 130

# Department codes -> territory type
DROM = {"971", "972", "973", "974", "976"}
COM = {"975", "977", "978", "986", "987", "988"}

# Bounding boxes (lat_min, lat_max, lon_min, lon_max) for coordinate validation, per territory.
# Generous boxes around each territory; metropolitan France includes Corsica.
BOUNDING_BOXES: dict[str, tuple[float, float, float, float]] = {
    "metropole": (41.2, 51.2, -5.3, 9.7),
    "971": (15.8, 16.6, -61.9, -60.9),    # Guadeloupe
    "972": (14.3, 14.95, -61.3, -60.75),  # Martinique
    "973": (2.0, 6.0, -54.7, -51.5),      # Guyane
    "974": (-21.45, -20.8, 55.15, 55.9),  # La Réunion
    "976": (-13.1, -12.6, 44.9, 45.35),   # Mayotte
    "975": (46.7, 47.2, -56.5, -56.0),    # Saint-Pierre-et-Miquelon
    "977": (17.85, 17.98, -62.95, -62.78),  # Saint-Barthélemy
    "978": (18.0, 18.13, -63.17, -62.95),   # Saint-Martin
    "986": (-14.4, -13.1, -178.3, -176.1),  # Wallis-et-Futuna
    "987": (-28.0, -7.5, -155.0, -134.0),   # Polynésie française
    "988": (-23.0, -19.5, 163.5, 168.2),    # Nouvelle-Calédonie
}

# Department names for territories not in the INSEE department file
EXTRA_DEPARTMENT_NAMES = {
    "976": ("Mayotte", "Mayotte"),
    "975": ("Saint-Pierre-et-Miquelon", "Collectivités d'outre-mer"),
    "977": ("Saint-Barthélemy", "Collectivités d'outre-mer"),
    "978": ("Saint-Martin", "Collectivités d'outre-mer"),
    "986": ("Wallis-et-Futuna", "Collectivités d'outre-mer"),
    "987": ("Polynésie française", "Collectivités d'outre-mer"),
    "988": ("Nouvelle-Calédonie", "Collectivités d'outre-mer"),
}
