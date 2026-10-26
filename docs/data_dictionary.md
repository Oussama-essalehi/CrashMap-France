# Dictionnaire de données

Trois grains nettoyés (`data/processed/*.parquet`, produits par `python run.py clean`) et le schéma
en étoile (PostgreSQL `crashmap.*`, CSV `data/gold/*.csv`, modèle Power BI). Les codes et libellés
viennent du PDF ONISR « Description des bases de données annuelles » (voir
[`src/crashmap/codebook.py`](../src/crashmap/codebook.py)). Une valeur vide signifie « non
renseigné » : les codes `-1` et les zéros « non renseigné » ont été convertis en valeurs nulles.

## Grain accident - `accidents.parquet` / `fact_accident`

Une ligne par accident corporel (327 628 lignes, 2019-2024).

| Colonne | Type | Description | Origine |
|---|---|---|---|
| `accident_id` | entier | Identifiant ONISR (`Num_Acc`, `Accident_Id` en 2022) | caractéristiques |
| `year` | entier | Année du fichier | dérivé |
| `date` | date | Date de l'accident (`jour`, `mois`, `an`) | caractéristiques |
| `month`, `day_of_week`, `weekday`, `is_weekend` | | Mois, jour de la semaine (0 = lundi), libellé, week-end | dérivé |
| `hrmn`, `hour`, `minute`, `time_band` | | Heure brute, heure, minute, tranche (Nuit 21h-6h, Matin 6h-10h, Journée 10h-17h, Soirée 17h-21h) | caractéristiques + dérivé |
| `dep_code`, `dep_name`, `region_name`, `zone` | texte | Département standardisé (`01`, `2A`, `971`…), nom, région INSEE, Métropole / DROM / COM | caractéristiques + INSEE |
| `com_code`, `adr` | texte | Code commune INSEE, adresse (en agglomération) | caractéristiques |
| `agg`, `agg_label`, `in_town` | | En / hors agglomération | caractéristiques |
| `lum`, `lum_label`, `night` | | Luminosité ; `night` = nuit (codes 3-5) | caractéristiques |
| `atm`, `atm_label` | | Conditions atmosphériques | caractéristiques |
| `int`, `int_label` | | Type d'intersection | caractéristiques |
| `col`, `col_label` | | Type de collision | caractéristiques |
| `catr`, `catr_label` | | Catégorie de route (voie principale) | lieux |
| `vma`, `vma_band`, `vma_implausible` | | Vitesse maximale autorisée (nulle si hors [10, 130]), tranche, indicateur de valeur impossible | lieux |
| `plan`, `prof`, `circ`, `vosp`, `infra`, `situ`, `surf` (+ `_label`) | | Tracé, profil, régime de circulation, voie réservée, infrastructure, situation, état de surface | lieux |
| `nbv` | entier | Nombre de voies | lieux |
| `lat`, `lon` | réel | Coordonnées WGS84 (nulles hors du cadre du territoire) | caractéristiques |
| `coord_status` | texte | `valide`, `hors zone`, `manquante` | dérivé |
| `coord_repeated`, `coord_precise` | booléen | Point partagé par 5 accidents ou plus (artefact) ; coordonnée exploitable pour les cartes | dérivé |
| `lieux_rows` | entier | Nombre de lignes `lieux` d'origine (plusieurs depuis 2023) | dérivé |
| `n_vehicles`, `n_users` | entier | Véhicules et usagers impliqués | agrégé |
| `n_killed`, `n_hospitalized`, `n_lightly_injured`, `n_unhurt`, `n_severity_unknown`, `n_victims` | entier | Comptes par gravité (victimes = tués + hospitalisés + légers) | agrégé des usagers |
| `n_pedestrians`, `pedestrian_involved` | | Piétons impliqués | agrégé |
| `two_wheeler_involved`, `motorised_two_wheeler_involved`, `bicycle_involved`, `personal_mobility_involved`, `heavy_vehicle_involved` | booléen | Présence d'un deux-roues (2RM/3RM, vélo, EDP), d'un 2RM, d'un vélo, d'un EDP, d'un poids lourd ou bus | agrégé des véhicules |
| `fatal` | booléen | Au moins un tué | dérivé |
| `serious` | booléen | Au moins un tué ou un blessé hospitalisé (comparaisons 2019+ uniquement) | dérivé |
| `covid_year` | booléen | Année 2020 | dérivé |

## Grain véhicule - `vehicles.parquet` / `fact_vehicle`

Une ligne par véhicule (559 847 lignes).

| Colonne | Description |
|---|---|
| `vehicle_key` | `accident_id` + `_` + `id_vehicule` (unique) |
| `accident_id`, `year`, `id_vehicule`, `num_veh` | Clés et identifiants ONISR |
| `catv`, `catv_label`, `vehicle_group` | Catégorie de véhicule (31 codes) et groupe d'analyse |
| `is_two_wheeler`, `is_motorised_two_wheeler`, `is_bicycle`, `is_personal_mobility`, `is_heavy_vehicle` | Familles de véhicules |
| `senc`, `obs`, `obsm`, `choc`, `manv`, `motor` (+ `_label`) | Sens, obstacle fixe, obstacle mobile, point de choc, manœuvre, motorisation |
| `occutc` | Occupants d'un transport en commun |
| `n_users`, `n_killed`, `n_hospitalized`, `n_lightly_injured` | Usagers rattachés au véhicule (piétons heurtés compris) |

Dans `fact_vehicle` les libellés sont renommés : `fixed_obstacle`, `mobile_obstacle`,
`impact_point`, `maneuver`, `engine`.

## Grain victime (personne) - `victims.parquet` / `fact_victim`

Une ligne par usager impliqué, indemnes compris (745 158 lignes).

| Colonne | Description |
|---|---|
| `victim_id` | `accident_id` + `_` + rang de l'usager dans l'accident (unique, toutes années) |
| `id_usager` | Identifiant ONISR (absent en 2019 et 2020) |
| `vehicle_key`, `vehicle_catv`, `vehicle_group` | Véhicule occupé, ou véhicule qui a heurté le piéton |
| `user_mode` | Mode de déplacement : « Piéton » ou groupe du véhicule |
| `catu`, `catu_label` | Conducteur, passager, piéton |
| `grav`, `grav_label` | Indemne, tué, blessé hospitalisé, blessé léger (nul pour 419 usagers en fuite) |
| `killed`, `hospitalized`, `lightly_injured`, `unhurt`, `is_victim`, `killed_or_hospitalized` | Indicateurs de gravité |
| `sexe`, `sexe_label` | Sexe |
| `an_nais`, `age`, `age_band` | Année de naissance, âge à l'accident (nul hors 0-110), tranche d'âge |
| `trajet`, `trajet_label` | Motif du déplacement |
| `secu1..3`, `secu1..3_label` | Équipements de sécurité déclarés (jusqu'à 3) |
| `equipment_known`, `seatbelt_worn`, `helmet_worn` | Équipement connu ; ceinture / casque porté (nul si inconnu) |
| `locp`, `actp`, `etatp` (+ `_label`) | Localisation, action et état du piéton |

Dans `fact_victim` : `severity`, `severity_order`, `sex`, `trip_purpose`, `age_band_order`.

## Dimensions du schéma en étoile

| Table | Clé | Colonnes |
|---|---|---|
| `dim_date` | `date_key` (AAAAMMJJ) | date, année, trimestre, mois, nom du mois, année-mois, jour, jour de la semaine (1 = lundi), nom, week-end, année COVID |
| `dim_time_band` | `hour` | libellé (`08h`), tranche horaire, ordre |
| `dim_location` | `location_key` (`<commune>-<A/H>`) | commune, nom et population INSEE, département, région, zone, en / hors agglomération |
| `dim_population` | `dep_code` | département, région, zone, population INSEE 2023 (vide pour 976, 986, 987, 988), année de population |
| `dim_conditions` | `conditions_key` | luminosité, météo, surface (+ libellés), nuit |
| `dim_road` | `road_key` | catégorie de route, tranche de vitesse (+ ordre), tracé, intersection |
| `dim_user_type` | `user_type_key` | catégorie d'usager, mode de déplacement |
| `dim_vehicle_type` | `catv` | libellé, groupe, familles (deux-roues, 2RM, vélo, EDP, poids lourd) |

## Fichiers de résultats

| Fichier | Contenu |
|---|---|
| `docs/cleaning_report.md` | Volumes avant / après chaque règle, contrôles, taux de manquants, cohérence entre grains |
| `docs/sql_python_crosscheck.md` | Comparaison SQL / Python |
| `reports/sql_results/*.csv` | Résultat de chaque requête de `sql/03_analysis_queries.sql` |
| `reports/tables/*.csv` | Tables d'analyse (taux avec IC de Wilson, khi-deux, rapports de cotes, points noirs…) |
| `reports/key_numbers.json` | Chiffres clés utilisés dans `reports/findings.md` et le README |
