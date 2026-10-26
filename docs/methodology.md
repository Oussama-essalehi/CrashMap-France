# Méthodologie

Ce document décrit chaque règle de préparation des données, avec les volumes avant / après.
Les chiffres détaillés (régénérés à chaque exécution de `python run.py clean`) sont dans
[`cleaning_report.md`](cleaning_report.md). Les codes et libellés viennent du PDF officiel
« Description des bases de données annuelles des accidents corporels de la circulation routière -
Années de 2005 à 2024 » (ONISR, 21 octobre 2025), repris dans
[`src/crashmap/codebook.py`](../src/crashmap/codebook.py) avec le numéro de page de chaque liste.

## 1. Sources et périmètre

| Source | Contenu | Version utilisée |
|---|---|---|
| data.gouv.fr, jeu `53698f4ca3a729239d2036df` (ONISR) | 4 fichiers CSV par an : caractéristiques, lieux, véhicules, usagers | 2019 à 2024 (dernière année publiée) |
| ONISR, PDF de description | Codes et définitions | 21/10/2025 |
| INSEE, « Populations de référence 2023 » (fichier d'ensemble) | Population totale par département et par commune | En vigueur au 1er janvier 2026 |
| `gregoiredavid/france-geojson` (IGN Admin Express, Licence Ouverte) | Contours simplifiés des départements | Branche `master` |

* **Années** : 2019 à 2024. La structure des fichiers a changé en 2019 (nouvelles variables, nouveaux
  codes, équipements de sécurité en 3 variables) : les années antérieures sont hors périmètre.
* **Territoires** : métropole, DROM (971 à 974, 976) et collectivités d'outre-mer (975, 977, 978, 986
  à 988), comme dans le bilan national de l'ONISR. La colonne `zone` permet de filtrer.
* **URLs** : jamais codées en dur. `download.py` interroge l'API data.gouv.fr et reconnaît les
  fichiers par leur titre (`caract-2023.csv`, `carcteristiques-2022.csv`, `Caract_2024.csv`…),
  en excluant le jeu distinct des « véhicules immatriculés ». Un `manifest.json` garde l'identifiant
  de ressource, la taille et le SHA-256 de chaque fichier téléchargé.

## 2. Différences entre années (standardisation)

Constatées en inspectant les 24 fichiers ; traitées dans `standardize.py` :

| Différence | Années | Traitement |
|---|---|---|
| Clé de l'accident nommée `Accident_Id` au lieu de `Num_Acc` | caractéristiques 2022 | Renommée `num_acc` |
| Colonne `id_usager` absente | usagers 2019, 2020 | Ajoutée vide ; clé `victim_id` construite pour toutes les années |
| Fins de ligne CRLF | 2020 (lieux, véhicules, usagers) | Lecture indifférente |
| Codes précédés d'un espace (`" -1"`) | toutes | `strip()` puis conversion en entier |
| Séparateur de milliers dans les identifiants (`"138 306 524"`) | toutes | Espaces supprimés |
| Code département sans zéro (`"1"`) | 2019 | Complété à 2 caractères (`"01"`) ; `2A`, `2B`, `971`… inchangés |
| Coordonnées avec virgule décimale, 7 à 10 décimales | toutes | Converties en `float` |
| Valeurs parasites : `#VALEURMULTI`, `#ERREUR`, `(1)`, `N/A`, `null` | lieux | Valeur nulle |

Tous les fichiers sont en UTF-8 avec `;` comme séparateur (une lecture Latin-1 de secours est prévue).
Une colonne `year` est ajoutée à chaque table.

## 3. Clés, grains et piège du double comptage

* `Num_Acc` est unique dans `caracteristiques` chaque année (0 doublon).
* **`lieux` contient plusieurs lignes par accident depuis 2023** (une par voie à une intersection) :
  15 870 lignes en trop en 2023 et 15 645 en 2024 (31 515 accidents concernés, 359 512 → 327 628
  lignes). Règle : on garde **la voie principale** = la catégorie de route la plus haute dans la
  hiérarchie (autoroute > nationale > départementale > route de métropole urbaine > communale >
  autre), puis la vitesse maximale autorisée la plus élevée, puis l'ordre du fichier. Le nombre de
  lignes d'origine est conservé dans `lieux_rows`.
* **Clés étrangères** : 0 ligne de lieux, véhicules ou usagers orpheline ; 0 usager sans véhicule.
  Des véhicules n'ont aucun usager (conducteurs en fuite non créés, cf. PDF p.3) : 2 040 en 2019,
  1 899 en 2020, 6 en 2021, 0 en 2022, 40 en 2023, 24 en 2024. Ils sont conservés.
* **Le piège** : un accident a plusieurs véhicules et chaque véhicule plusieurs usagers. La jointure
  accident × véhicule × usager compte **745 158 lignes pour 327 628 accidents** (×2,27). Compter
  des lignes ou sommer un attribut d'accident sur cette table surestime tout.
  On construit donc trois grains distincts, en agrégeant toujours *vers le haut* :

| Grain | Fichier | Lignes | Contenu |
|---|---|---:|---|
| Accident | `accidents.parquet` | 327 628 | Conditions, lieu, date/heure + comptes agrégés (véhicules, usagers, tués, hospitalisés, blessés légers, indemnes) et indicateurs (piéton, deux-roues, poids lourd impliqués) |
| Véhicule | `vehicles.parquet` | 559 847 | Catégorie, groupe, obstacle, choc, manœuvre, motorisation + comptes d'occupants |
| Victime (personne) | `victims.parquet` | 745 158 | Catégorie d'usager, gravité, sexe, âge, équipements, mode de déplacement |

Des tests (`tests/test_clean.py`) vérifient que le nombre d'accidents et de tués est identique
quel que soit le grain utilisé ; le rapport de nettoyage le vérifie aussi sur les données réelles
(identique pour les 6 années).

## 4. Valeurs manquantes

Le PDF (p.3) indique qu'une cellule vide, un zéro ou un point signifie « non renseigné » ou « sans
objet », et la plupart des listes ont un code `-1 - Non renseigné`. Règle : ces codes deviennent des
valeurs nulles, **jamais une catégorie**. Les zéros qui ont un sens (« 0 - Aucun équipement »,
« 0 - Sans objet » pour un obstacle, « 0 - Aucun » pour l'infrastructure) sont conservés. La liste
exacte par variable est `MISSING_CODES` dans le codebook. Les codes absents du PDF (182 valeurs
`actp` = 7 ou 8) sont aussi mis à nul.

Taux de valeurs manquantes après nettoyage (principales colonnes) :

| Grain | Colonne | % manquant |
|---|---|---:|
| Accident | luminosité, intersection, date, heure, département | < 0,01 % |
| Accident | type de collision | 0,49 % |
| Accident | vitesse maximale autorisée | 1,70 % |
| Véhicule | manœuvre | 6,4 % |
| Véhicule | motorisation | 7,3 % |
| Victime | gravité | 0,06 % (419 usagers en fuite, 2021-2023) |
| Victime | sexe | 1,43 % |
| Victime | âge | 1,52 % |
| Victime | équipement de sécurité connu | 6,13 % inconnu (« non déterminable » inclus) |
| Victime | motif du trajet | 27,8 % |

Depuis 2021 les usagers en fuite sont ajoutés aux fichiers sans sexe, âge ni toujours gravité (PDF
p.1) : c'est la cause principale des manques de sexe et d'âge.

## 5. Décodage

Chaque variable codée reçoit une colonne `<variable>_label` en français (luminosité, météo, surface,
catégorie de route, intersection, tracé, catégorie d'usager, gravité, catégorie de véhicule,
équipement, manœuvre, obstacle fixe et mobile, point de choc, motorisation, trajet, piéton…).

## 6. Types et coordonnées

* **Date** construite à partir de `jour`, `mois`, `an` (0 date invalide, 0 incohérence entre `an`
  et l'année du fichier). **Heure** et minute extraites de `hrmn` (`HH:MM`) : 0 heure invalide.
* **Coordonnées** : converties en nombres puis contrôlées par rapport au cadre géographique du
  territoire de l'accident (métropole + Corse, ou cadre propre à chaque DROM / COM). Hors cadre →
  nul et `coord_status = "hors zone"` : **48 accidents**. Aucune coordonnée vide ou nulle.
* **Points répétés** : 3 641 accidents partagent exactement le même point qu'au moins 4 autres
  (475 points). Ce sont des artefacts de géocodage (même adresse, centre de commune), pas des
  points noirs réels. Ils sont marqués `coord_repeated` et exclus des cartes de densité et du
  clustering (`coord_precise = False`). Le PDF rappelle que tous les accidents ne sont pas
  géolocalisés précisément : au minimum, seule la commune est connue.

## 7. Colonnes dérivées

| Colonne | Règle |
|---|---|
| `hour`, `day_of_week`, `weekday`, `month`, `is_weekend` | depuis la date et `hrmn` |
| `time_band` | Nuit 21h-6h, Matin 6h-10h, Journée 10h-17h, Soirée 17h-21h |
| `night` | luminosité = nuit (codes 3, 4, 5) |
| `age`, `age_band` | `year - an_nais` ; hors [0, 110] → nul (191 cas) ; tranches 0-13, 14-17, 18-24, 25-34, 35-44, 45-54, 55-64, 65-74, 75+ |
| `dep_code`, `dep_name`, `region_name`, `zone` | code département standardisé ; noms et régions INSEE ; Métropole / DROM / COM |
| `in_town` | `agg = 2` (en agglomération) |
| `vma`, `vma_band` | vitesse autorisée ; valeurs hors [10, 130] km/h jugées impossibles (424 accidents : 1, 2, 3, 5, 300, 500, 900…) → nul et `vma_implausible` ; tranches ≤ 30, 40-50, 60-70, 80-90, 100-110, 130 |
| `vehicle_group` | regroupement des 31 catégories de véhicule (vélo y.c. VAE, EDP motorisé, cyclomoteur, moto 50-125, moto > 125, voiture, utilitaire, poids lourd, bus/car…) |
| `user_mode` | « Piéton » pour les piétons, sinon le groupe du véhicule occupé |
| `seatbelt_worn`, `helmet_worn` | vrai si l'un des 3 équipements déclarés est la ceinture / le casque ; nul si aucun équipement n'est connu ou « non déterminable » |
| `covid_year` | année 2020 (confinements) |

## 8. Indicateurs de gravité

* **Accident** : `fatal` = au moins un tué (à 30 jours) ; `serious` = au moins un tué ou un blessé
  hospitalisé.
* **Victime** : tué / blessé hospitalisé / blessé léger / indemne (`grav`).

L'indicateur « blessé hospitalisé » n'est pas comparable avant 2018 et n'est plus labellisé par
l'autorité de la statistique publique depuis 2019 (avertissement du PDF, p.1). Le **nombre de tués**
reste donc l'indicateur principal ; `serious` sert seulement aux comparaisons internes 2019-2024.

## 9. Règle des petits effectifs

Aucun taux n'est affiché pour un groupe de moins de **100 accidents** (paramètre
`analysis.min_accidents_for_rate` de `config.yaml`, paramètre « Seuil accidents » dans Power BI) :
le taux est vide, en SQL comme en Python ou en DAX.

## 10. Taux pour 100 000 habitants

Population totale INSEE 2023 du département. Mayotte (non couverte par les populations de référence
2023), Wallis-et-Futuna, la Polynésie française et la Nouvelle-Calédonie n'ont pas de population dans
ce fichier : leurs taux par habitant sont vides. Les accidents de ces territoires restent comptés
dans les totaux. La population de 2023 sert de dénominateur pour toutes les années (approximation :
la population varie de moins de 1 % par an).

## 11. Contrôles de cohérence

* Totaux annuels comparés aux bilans officiels ONISR : voir [`findings.md`](../reports/findings.md)
  et le README.
* Résultats SQL et Python croisés sur 2 départements et 2 années : voir `docs/sql_python_crosscheck.md`.

## 12. Méthodes statistiques

Voir [`reports/findings.md`](../reports/findings.md) pour les résultats.

* **Intervalle de Wilson à 95 %** pour chaque taux de mortalité (tués / 100 accidents ou part
  d'accidents mortels) : plus fiable que l'intervalle normal pour des proportions faibles.
* **Khi-deux d'indépendance** entre chaque condition et `fatal`, avec le **V de Cramér** comme taille
  d'effet. Avec 327 628 accidents, presque tout est « significatif » : c'est la taille d'effet qui
  permet de hiérarchiser les facteurs.
* **Régression logistique** (statsmodels) de `fatal` au grain accident ; rapports de cotes (odds
  ratios) avec intervalles de confiance à 95 %.
* **Contrôle prédictif** (scikit-learn) : régression logistique pondérée et gradient boosting,
  entraînement 2019-2023, test 2024 ; ROC AUC, précision-rappel, importance des variables. Le but est
  de comprendre les facteurs de risque, pas de produire un modèle de prédiction.
* **DBSCAN** (distance haversine) sur les accidents précisément géolocalisés de la ville cible pour
  repérer les points noirs.
