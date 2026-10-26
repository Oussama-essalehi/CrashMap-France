# Guide de construction du rapport Power BI

Ce dossier contient un **Power BI Project** (`.pbip`) :

* `CrashMapFrance.SemanticModel/` : le modèle sémantique au format **TMDL** (tables, relations,
  mesures DAX, paramètre `DataFolder`) ;
* `CrashMapFrance.Report/` : le rapport au format **PBIR** (un fichier JSON par page et par visuel) ;
* `theme.json` : le thème « CrashMap Signalisation » ;
* `tools/generate_pbip.py` : régénère le projet à partir des CSV de `data/gold/` ;
* `tools/validate_pbip.py` : valide les fichiers JSON contre les schémas publiés par Microsoft et
  contrôle la cohérence du TMDL (références de colonnes, relations, mesures).

La mise en page PBIR est fragile d'une version de Power BI Desktop à l'autre. Ce guide décrit donc
chaque visuel pour pouvoir le reconstruire à la main si besoin.

## 1. Prérequis

* Power BI Desktop (Windows), version de 2026 ou plus récente. Le projet utilise les schémas PBIR
  `report 3.3.0`, `page 2.1.0`, `visualContainer 2.13.0` et le schéma de thème `2.159`
  (octobre 2026).
* Le format PBIR et TMDL est le format par défaut des versions récentes. Sur une version plus
  ancienne : *Fichier > Options > Fonctionnalités en préversion* > cocher « Format de rapport
  amélioré (PBIR) » et « Format de modèle sémantique TMDL », puis redémarrer.
* Les CSV de `data/gold/`. Les trois tables de faits (plus de 50 Mo) ne sont pas dans Git :
  les régénérer avec `python run.py all` (ou `python run.py download clean export` étape par étape).

## 2. Ouvrir, régler `DataFolder` et actualiser

1. Ouvrir `powerbi/CrashMapFrance.pbip` dans Power BI Desktop.
2. *Accueil > Transformer les données > Modifier les paramètres* : renseigner **DataFolder** avec
   le chemin **absolu** du dossier `data/gold`, par exemple
   `C:\Users\Oussama\Projets\crashmap-france\data\gold` (avec ou sans `\` final).
3. *Accueil > Actualiser*. Le chargement prend une à deux minutes (environ 1,6 million de lignes).
4. Enregistrer (`Ctrl+S`). Power BI met à jour les fichiers du dossier ; les fichiers locaux
   (`.pbi/localSettings.json`, `cache.abf`) sont ignorés par Git.

Valeurs attendues après actualisation, sans filtre : **327 628 accidents**, **19 877 tués**,
**6,07 tués pour 100 accidents**. En 2024 seule : 54 402 accidents et 3 432 tués.

## 3. Modèle sémantique

### Tables

| Table | Grain / rôle | Clé |
|---|---|---|
| `fact_accident` | 1 ligne par accident | `accident_id` |
| `fact_vehicle` | 1 ligne par véhicule | `vehicle_key` |
| `fact_victim` | 1 ligne par personne impliquée (indemnes compris) | `victim_id` |
| `dim_date` | calendrier 2019-2024, **marquée comme table de dates** (colonne `date`) | `date_key` |
| `dim_time_band` | heure 0-23 et tranche horaire | `hour` |
| `dim_location` | commune × en / hors agglomération | `location_key` |
| `dim_population` | département, région, zone, population INSEE 2023 | `dep_code` |
| `dim_conditions` | luminosité × météo × surface | `conditions_key` |
| `dim_road` | catégorie de route × tranche de vitesse × tracé × intersection | `road_key` |
| `dim_user_type` | catégorie d'usager × mode de déplacement | `user_type_key` |
| `dim_vehicle_type` | catégorie de véhicule et groupe | `catv` |
| `_Mesures` | table vide qui porte les mesures | - |
| `Seuil accidents` | paramètre de simulation (0 à 1 000, pas de 10, défaut 100) | - |

Chaque table est chargée par Power Query avec `Csv.Document(File.Contents(DataFolder & ...))`,
encodage UTF-8 (65001), types appliqués avec la culture `en-US` (point décimal, dates ISO, booléens
`true` / `false`). La table `dim_population` reçoit une colonne calculée `dep_geo` =
`dep_name & ", France"` (catégorie de données « Comté ») pour la carte.

### Relations (toutes plusieurs-à-un, filtrage dans un seul sens)

| De (plusieurs) | Vers (un) |
|---|---|
| `fact_accident[date_key]` | `dim_date[date_key]` |
| `fact_accident[hour]` | `dim_time_band[hour]` |
| `fact_accident[location_key]` | `dim_location[location_key]` |
| `fact_accident[dep_code]` | `dim_population[dep_code]` |
| `fact_accident[conditions_key]` | `dim_conditions[conditions_key]` |
| `fact_accident[road_key]` | `dim_road[road_key]` |
| `fact_vehicle[accident_id]` | `fact_accident[accident_id]` |
| `fact_vehicle[catv]` | `dim_vehicle_type[catv]` |
| `fact_victim[accident_id]` | `fact_accident[accident_id]` |
| `fact_victim[user_type_key]` | `dim_user_type[user_type_key]` |
| `fact_victim[catv]` | `dim_vehicle_type[catv]` |

Les filtres des dimensions « accident » (date, lieu, conditions, route) descendent jusqu'aux
véhicules et aux victimes via `fact_accident`. Il n'existe qu'un chemin entre deux tables, donc pas
d'ambiguïté. **Filtrer les départements et régions avec `dim_population`** (c'est elle qui porte la
population utilisée dans les taux).

Tris : `month_name` par `month`, `weekday_name` par `day_of_week`, `time_band` par
`time_band_order`, `hour_label` par `hour`, `vma_band` par `vma_band_order`, `age_band` par
`age_band_order`, `severity` par `severity_order`. Les clés techniques sont masquées. Les mesures
implicites sont désactivées (`discourageImplicitMeasures`) : utiliser les mesures de `_Mesures`.

### Mesures (`_Mesures`)

Toutes ont une description (visible au survol dans le volet Données) et un format français.

| Dossier | Mesure | Définition |
|---|---|---|
| 1. Volumes | Nb Accidents | `COUNTROWS(fact_accident)` |
| | Nb Accidents Mortels | accidents avec `fatal = TRUE` |
| | Nb Tués / Nb Blessés Hospitalisés / Nb Blessés Légers | somme au grain personne (`fact_victim`) |
| | Nb Victimes | tués + hospitalisés + légers |
| | Nb Personnes Impliquées | `COUNTROWS(fact_victim)` |
| 2. Taux | Taux Mortalité (tués / 100 accidents) | tués / accidents × 100, vide sous le seuil |
| | Part Accidents Mortels % | accidents mortels / accidents, vide sous le seuil |
| | Accidents pour 100k hab | accidents / (population × nb d'années) × 100 000, vide sous le seuil |
| | Tués pour 100k hab | tués / (population × nb d'années) × 100 000, vide sous le seuil |
| 3. Évolution | Nb Accidents N-1, Nb Tués N-1 | `SAMEPERIODLASTYEAR(dim_date[date])` |
| | Évolution Accidents %, Évolution Tués % | (N - N-1) / N-1, pour une seule année, vide sous le seuil |
| 4. Classement | Rang Département Mortalité | `RANKX` des départements visibles sur Tués pour 100k hab |
| 5. Parts | Part Accidents de Nuit % | accidents 21h-6h / accidents, vide sous le seuil |
| | Part Deux-Roues % | accidents avec deux-roues ou EDP / accidents, vide sous le seuil |
| 6. Victimes et équipement | % Tués parmi impliqués, % Tués ou Hospitalisés | au grain personne, gravité connue |
| | % Tués Voiture avec / sans ceinture, % Tués 2RM avec / sans casque | idem, sur une population comparable |
| Paramètres | Valeur Seuil accidents (table `Seuil accidents`) | `SELECTEDVALUE(..., 100)` |

Règle commune : un taux est **vide** quand le contexte compte moins d'accidents que le seuil choisi
(100 par défaut). Sur la page « Qui ? », utiliser les mesures du dossier 6 : `Nb Accidents` ne
réagit pas aux filtres sur les usagers (la relation va de l'accident vers les personnes).

## 4. Thème

Le thème `CrashMap Signalisation` est déclaré dans `report.json` et copié dans
`StaticResources/RegisteredResources/CrashMapSignalisation.json`. S'il n'apparaît pas :
*Affichage > Thèmes > Parcourir les thèmes* > `powerbi/theme.json`.

Palette inspirée de la signalisation routière : bleu autoroute `#1F5FAE`, jaune chantier
`#E8A20C`, vert direction `#16825D`, rouge danger `#D1342B`, bleu ciel `#4AA3DF`. L'ordre a été
vérifié pour les daltonismes (protanopie, deutéranopie, tritanopie) sur les couleurs voisines. Le
jaune et le bleu ciel ont un contraste inférieur à 3:1 sur fond blanc : garder les **étiquettes de
données** activées sur les visuels qui les utilisent. Titres affichés sur tous les visuels, fond de
page gris clair `#F4F5F7`, cartes blanches à bordure arrondie.

## 5. Pages et visuels

Canevas 1 280 × 720 px, « Ajuster à la page ». Positions en pixels (x, y, largeur, hauteur).

### Bandeau de segments (identique sur les 5 pages)

Cinq segments en liste déroulante, en haut de page (y = 8, hauteur 70), **synchronisés** entre
les pages (*Affichage > Synchroniser les segments*, groupes `sync_annee`, `sync_region`…) :

| Segment | Champ | Position |
|---|---|---|
| Année | `dim_date[year]` | 20, 8, 210 × 70 |
| Région | `dim_population[region_name]` | 245, 8, 230 × 70 |
| Département | `dim_population[dep_name]` | 490, 8, 230 × 70 |
| Localisation | `dim_location[in_town_label]` | 735, 8, 230 × 70 |
| Seuil accidents (taux) | `'Seuil accidents'[Seuil accidents]`, sélection unique | 980, 8, 200 × 70 |

### Page 1 - Vue d'ensemble

| Visuel | Type | Champs | Position | Mise en forme |
|---|---|---|---|---|
| Accidents | Carte | Nb Accidents | 20, 95, 195 × 105 | |
| Tués | Carte | Nb Tués | 227, 95 | |
| Tués / 100 accidents | Carte | Taux Mortalité (tués / 100 accidents) | 434, 95 | |
| Tués / 100 000 hab. / an | Carte | Tués pour 100k hab | 641, 95 | |
| Évolution des tués vs N-1 | Carte | Évolution Tués % | 848, 95 | s'affiche quand une seule année est sélectionnée |
| Part d'accidents de nuit | Carte | Part Accidents de Nuit % | 1055, 95 | |
| Tués par an (2020 : année COVID) | Histogramme groupé | Axe X : `dim_date[year]` ; Y : Nb Tués | 20, 215, 610 × 490 | étiquettes de données ; mettre la barre 2020 en gris (*Colonnes > Couleur > fx*, ou couleur manuelle) |
| Accidents par mois, une courbe par année | Graphique en courbes | Axe X : `dim_date[month_name]` ; Y : Nb Accidents ; Légende : `dim_date[year]` | 645, 215, 615 × 490 | |

### Page 2 - Carte de France

| Visuel | Type | Champs | Position | Mise en forme |
|---|---|---|---|---|
| Tués pour 100 000 habitants par an, par département | Carte choroplèthe (`filledMap`) | Emplacement : `dim_population[dep_geo]` ; Info-bulles : Tués pour 100k hab | 20, 95, 640 × 610 | *Couleurs de remplissage > fx* : dégradé blanc → `#D1342B` basé sur Tués pour 100k hab ; *Info-bulles* : type « Page de rapport », page « Info-bulle département » |
| Départements les plus touchés | Tableau | `dim_population[dep_name]`, Tués pour 100k hab, Nb Tués, Nb Accidents, Taux Mortalité, Rang Département Mortalité | 675, 95, 585 × 300 | tri décroissant sur Tués pour 100k hab ; option : filtre visuel Top N = 10 sur `dep_name` par Tués pour 100k hab |
| Départements les moins touchés | Tableau | mêmes champs | 675, 405, 585 × 300 | tri croissant ; option : filtre Bas N = 10 |

**Page d'info-bulle « Info-bulle département »** (masquée, type Info-bulle, 320 × 320) :
une carte `dim_population[dep_name]` (10, 10, 300 × 70) et une carte à plusieurs lignes
(10, 85, 300 × 225) avec Tués pour 100k hab, Nb Tués, Nb Accidents, Taux Mortalité, Rang
Département Mortalité. *Mise en forme de la page > Informations sur la page > Autoriser l'utilisation
comme info-bulle* doit être activé.

Si la carte choroplèthe Bing n'est pas disponible (retrait des visuels Bing Maps au profit
d'Azure Maps selon la version ou la politique du locataire) : accepter la conversion proposée vers
**Azure Maps** (couche « Remplissage » sur `dep_geo`, même dégradé), ou utiliser le visuel **Carte de
formes** avec un TopoJSON des départements (convertir `data/raw/geo/departements.geojson` avec
mapshaper.org, clé `nom` = `dim_population[dep_name]`). Les départements d'outre-mer sont lisibles
dans les tableaux.

### Page 3 - Quand ?

| Visuel | Type | Champs | Position | Mise en forme |
|---|---|---|---|---|
| Accidents par jour et par heure | Matrice | Lignes : `dim_date[weekday_name]` ; Colonnes : `dim_time_band[hour_label]` ; Valeurs : Nb Accidents | 20, 95, 615 × 300 | *Éléments de cellule > Couleur d'arrière-plan > fx* : dégradé blanc → `#1F5FAE` ; désactiver les totaux si besoin |
| Tués pour 100 accidents par jour et par heure | Matrice | mêmes lignes et colonnes ; Valeurs : Taux Mortalité | 645, 95, 615 × 300 | dégradé blanc → `#D1342B` ; les cellules sous le seuil restent vides |
| Saisonnalité : accidents par mois | Histogramme groupé | X : `dim_date[month_name]` ; Y : Nb Accidents | 20, 405, 410 × 300 | |
| Saisonnalité : tués pour 100 accidents | Courbes | X : `dim_date[month_name]` ; Y : Taux Mortalité | 440, 405, 410 × 300 | |
| Tués pour 100 accidents par tranche horaire | Barres groupées | Y : `dim_time_band[time_band]` ; X : Taux Mortalité | 860, 405, 400 × 300 | étiquettes de données |

### Page 4 - Dans quelles conditions ?

Cinq graphiques en barres groupées, Valeur = **Taux Mortalité (tués / 100 accidents)**, tri
décroissant sur la valeur, étiquettes de données activées :

| Titre | Axe | Position |
|---|---|---|
| Tués pour 100 accidents : luminosité | `dim_conditions[lum_label]` | 20, 95, 410 × 195 |
| … : conditions météo | `dim_conditions[atm_label]` | 440, 95, 410 × 195 |
| … : état de la surface | `dim_conditions[surf_label]` | 860, 95, 410 × 195 |
| … : catégorie de route | `dim_road[catr_label]` | 20, 300, 410 × 195 |
| … : vitesse maximale autorisée | `dim_road[vma_band]` | 440, 300, 410 × 195 |
| … : type d'intersection | `dim_road[intersection_label]` | 20, 505, 830 × 200 |

Plus un **arbre de décomposition** (860, 300, 400 × 405) : Analyser = Taux Mortalité ; Expliquer
par = `dim_location[in_town_label]`, `dim_road[catr_label]`, `dim_road[vma_band]`,
`dim_conditions[lum_label]`, `dim_time_band[time_band]`, `dim_conditions[atm_label]`,
`dim_road[intersection_label]`. Ouvrir par exemple « Hors agglomération » puis « Vitesse » puis
« Luminosité » pour voir les combinaisons les plus graves.

### Page 5 - Qui ?

| Visuel | Type | Champs | Position | Mise en forme |
|---|---|---|---|---|
| Tués par mode de déplacement | Barres groupées | Y : `dim_user_type[user_mode]` ; X : Nb Tués | 20, 95, 410 × 300 | tri décroissant, étiquettes |
| % de tués parmi les personnes impliquées | Barres groupées | Y : `dim_user_type[user_mode]` ; X : % Tués parmi impliqués | 440, 95, 410 × 300 | tri décroissant, étiquettes |
| Victimes par catégorie d'usager | Histogramme groupé | X : `dim_user_type[catu_label]` ; Y : Nb Tués, Nb Blessés Hospitalisés, Nb Blessés Légers | 860, 95, 400 × 300 | |
| Tués par tranche d'âge et par sexe | Histogramme groupé | X : `fact_victim[age_band]` ; Y : Nb Tués ; Légende : `fact_victim[sex]` | 20, 405, 620 × 300 | |
| Équipement de sécurité et part de tués | Histogramme groupé | Y : % Tués Voiture avec ceinture, % Tués Voiture sans ceinture, % Tués 2RM avec casque, % Tués 2RM sans casque | 650, 405, 610 × 300 | étiquettes ; sous-titre conseillé : « Association, pas causalité » |

## 6. Ce qu'il faut vérifier à la première ouverture

1. **Ouverture sans erreur** du `.pbip`. Si Desktop signale un fichier invalide, le message cite le
   fichier JSON ou TMDL concerné : le corriger ou supprimer le visuel et le recréer avec ce guide.
2. **Paramètre `DataFolder`** renseigné, puis actualisation sans erreur Power Query (colonnes et
   types).
3. **Totaux** : 327 628 accidents et 19 877 tués sans filtre ; 3 432 tués en 2024.
4. **Table de dates** : *Outils de table > Marquer comme table de dates* doit afficher `dim_date`
   avec la colonne `date` (sinon le faire à la main). Tester Évolution Tués % en sélectionnant 2024
   (+1,0 % attendu par rapport à 2023).
5. **Relations** : vue Modèle, 11 relations plusieurs-à-un, à sens unique.
6. **Paramètre Seuil accidents** : passer à 1 000 doit vider les taux des petits départements.
7. **Thème** appliqué (bleu signalisation sur les premiers graphiques).
8. **Carte** : les départements sont bien coloriés (sinon voir l'alternative Azure Maps / Carte de
   formes ci-dessus) et l'info-bulle de page s'affiche au survol.
9. **Mise en forme conditionnelle** des deux matrices de la page « Quand ? ».
10. Faire des captures d'écran des 5 pages et les enregistrer dans
    `reports/figures/dashboard_1_vue_ensemble.png` … `dashboard_5_qui.png` (références du README).

## 7. Régénérer et valider le projet

```bash
python run.py export                       # CSV de data/gold
python powerbi/tools/generate_pbip.py      # écrit le TMDL et le PBIR
python powerbi/tools/validate_pbip.py      # schémas Microsoft + cohérence du modèle
```

`validate_pbip.py` contrôle les 71 fichiers JSON contre leurs schémas publiés
(`developer.microsoft.com/json-schemas/fabric/...`) et le thème contre `reportThemeSchema-2.159`.
Il n'existe pas de schéma JSON pour le TMDL : le script vérifie la structure (indentation,
mots-clés, propriétés connues) et que chaque relation, tri, référence DAX et champ de visuel pointe
vers un objet existant. La validation sémantique complète du DAX et l'analyse du TMDL par le moteur
ne se font qu'à l'ouverture dans Power BI Desktop.
