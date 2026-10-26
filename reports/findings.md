# Résultats et recommandations

Périmètre : 327 628 accidents corporels, 19 877 personnes tuées, France métropolitaine et
outre-mer, 2019 à 2024 (fichiers BAAC de l'ONISR sur data.gouv.fr). Tous les chiffres viennent des
tables de [`reports/tables/`](tables/) et de [`reports/key_numbers.json`](key_numbers.json),
régénérées par `python run.py analyze`. Les taux ne sont pas affichés pour les groupes de moins de
100 accidents.

Deux indicateurs de gravité sont utilisés :

* **tués pour 100 accidents** (un accident peut faire plusieurs morts) ;
* **% d'accidents mortels** (au moins un tué), une proportion, donnée avec un intervalle de
  confiance de Wilson à 95 %.

## Contrôle des totaux

Les tués comptés dans les fichiers sont identiques aux bilans définitifs publiés par l'ONISR :

| Année | Tués (données) | Bilan ONISR (France entière) | Dont métropole (données / ONISR) |
|---|---:|---:|---|
| 2019 | 3 498 | 3 498 | 3 244 / - |
| 2020 | 2 780 | 2 780 | 2 541 / 2 541 |
| 2021 | 3 219 | 3 219 (3 550 / 1,103) | 2 944 / - |
| 2022 | 3 550 | 3 550 | 3 267 / 3 267 |
| 2023 | 3 398 | 3 398 | 3 167 / 3 167 |
| 2024 | 3 432 | 3 432 | 3 193 / 3 193 |

Sources : bilans annuels ONISR 2020, 2022 et 2024 (pages « Bilan 20xx de la sécurité routière »
sur onisr.securite-routiere.gouv.fr). Le chiffre 2021 est déduit de l'évolution publiée (+10,3 %
en 2022). Seules les cases marquées « - » n'ont pas été vérifiées. Les nombres d'accidents
publiés par l'ONISR portent sur la métropole (51 058 en 2024 dans les données) ; le total de
54 402 inclut l'outre-mer.

## Six constats

### 1. Hors agglomération : un tiers des accidents, deux tiers des morts

Les accidents hors agglomération ne représentent que **36,4 %** des accidents mais **67,3 %** des
tués. On y compte **11,2 tués pour 100 accidents**, contre **3,1** en agglomération (×3,6). Sur
les routes à 80-90 km/h, 11,9 % des accidents sont mortels (IC 95 % : 11,7-12,2), contre 3,2 % à
40-50 km/h. Les routes départementales concentrent 11 558 des 19 877 tués.
Le modèle multivarié confirme : à autres facteurs égaux, être hors agglomération multiplie la cote
d'un accident mortel par **1,9** (IC 95 % : 1,8-2,0).

### 2. La nuit, moins d'accidents mais beaucoup plus graves

La tranche 21h-6h regroupe **16,5 %** des accidents mais **26,1 %** des tués : **9,6 tués pour 100
accidents**, contre 5,5 en journée. Les nuits sans éclairage public sont les plus meurtrières :
**13,5 %** d'accidents mortels (IC 95 % : 13,1-13,9), presque trois fois le plein jour (4,9 %). Le
week-end est aussi plus grave que la semaine (7,7 contre 5,5 tués pour 100 accidents).
À l'inverse, la nuit **avec** éclairage public allumé n'a que 3,6 % d'accidents mortels : ces
accidents ont lieu surtout en ville, à vitesse réduite. Une fois la localisation et la vitesse
prises en compte, la nuit reste un facteur aggravant (cote ×1,4 sans éclairage, ×1,2 pour la
tranche 21h-6h).

### 3. La vitesse autorisée est le premier facteur de gravité

Avec le khi-deux, tous les facteurs sont « significatifs » (p < 0,001), du fait des 327 628
accidents. La taille d'effet (V de Cramér) permet de les classer : vitesse maximale autorisée
(0,163), localisation (0,154), type de collision (0,134), catégorie de route (0,123) et luminosité
(0,117) arrivent en tête ; la météo (0,036) et l'état de la chaussée (0,018) pèsent peu.
Dans la régression logistique (322 020 accidents), par rapport à une route limitée à 40-50 km/h,
la cote d'un accident mortel est multipliée par **1,9 à 80-90 km/h** et **6,3 à 130 km/h**, à
catégorie de route égale. Sur autoroute, l'effet « 130 km/h » est en grande partie compensé par
l'effet « autoroute » (×0,35) : les deux variables se lisent ensemble. Les passages à niveau sont
rares (640 accidents) mais très graves (cote ×4,7). Un accident à un seul véhicule (sortie de
route, piéton heurté) a une cote ×1,7 par rapport à un accident à deux véhicules.

### 4. Usagers vulnérables : motards, piétons, cyclistes et seniors

Les occupants de voiture représentent **47,4 %** des tués. Les deux-roues motorisés (cyclomoteurs
et motos) en représentent **23,4 %** et les piétons **14,7 %**. Les motos de plus de 125 cm³
comptent 3 173 tués. Parmi les conducteurs et passagers de motos de plus de 125 cm³ impliqués, **5,4 %** sont tués, contre **2,2 %** pour les
occupants de voiture. **78,1 %** des tués sont des hommes. Le risque d'être tué quand on est
impliqué augmente fortement avec l'âge : 2,0 % chez les 25-34 ans, **8,5 %** chez les 75 ans et
plus (IC 95 % : 8,2-8,8). Les 18-24 ans comptent le plus de tués (3 305).

### 5. Ceinture et casque : un écart très net, mais pas une preuve de causalité

Parmi les conducteurs de voiture dont l'équipement est connu, **6,9 %** de ceux qui ne portaient pas
la ceinture ont été tués, contre **1,7 %** de ceux qui la portaient (risque ×4,1). Chez les
passagers : 5,7 % contre 1,5 % (×3,8). Chez les conducteurs de moto 50-125 cm³ sans casque, 5,9 %
sont tués contre 2,5 % (×2,3).
À lire avec prudence : ne pas porter d'équipement va souvent avec d'autres comportements à risque
(vitesse, alcool), et l'équipement est déclaré par les forces de l'ordre après l'accident. Chez les
cyclistes, ceux qui portent un casque sont même un peu plus souvent tués (4,3 % contre 3,9 %) :
casqués plus souvent sur route, hors agglomération, à vitesse élevée. C'est un biais de
confusion, pas un effet du casque.

### 6. Pas de baisse depuis 2019, et les trottinettes en hausse

Après le creux de **2020** (2 780 tués, -20,5 %, confinements), la mortalité est revenue au niveau
d'avant la crise : **3 432 tués en 2024**, soit -1,9 % par rapport à 2019, alors que le nombre
d'accidents a baissé de 7,5 % (54 402 contre 58 840). La gravité moyenne monte : 6,31 tués pour
100 accidents en 2024, contre 5,94 en 2019. Les tués en EDP motorisé (trottinettes électriques…)
passent de **10 en 2019 à 46 en 2024**. Les cyclistes tués passent de 201 à 233.

## Recommandations

**Où**

* Prioriser le **réseau secondaire hors agglomération** : routes départementales à 80-90 km/h,
  qui concentrent la majorité des tués (contrôle des vitesses, aménagement des sorties de route,
  glissières et dégagement des obstacles latéraux).
* Cibler les départements ruraux au taux de mortalité par habitant le plus élevé en métropole
  (Haute-Corse 9,5 ; Haute-Marne 9,3 ; Nièvre 9,3 ; Yonne 9,1 ; Jura 8,8 tués pour 100 000 habitants
  par an), et en outre-mer la Guadeloupe (13,1) et la Guyane (11,5). Les départements de métropole
  en tête ont un taux cinq à sept fois plus élevé que la petite couronne parisienne (1,4 à 1,6).
* Sécuriser les passages à niveau, rares mais les plus graves.

**Quand**

* Les nuits, surtout de 0h à 6h et le week-end : contrôles d'alcoolémie et de vitesse, éclairage
  des zones accidentogènes non éclairées, offre de transport de nuit.

**Pour qui**

* Les **motards** (gros cubes) : équipement, formation post-permis, vigilance aux intersections.
* Les **seniors** (75 ans et plus), comme piétons et conducteurs : aménagement des traversées,
  éclairage, temps de traversée aux feux.
* Les **jeunes hommes de 18 à 24 ans**, première tranche d'âge en nombre de tués.
* Les **EDP motorisés et les cyclistes**, dont la mortalité augmente : continuité des pistes
  cyclables, port du casque sur EDP.
* Rappel du port de la ceinture **à l'arrière** et pour les passagers.

## Limites

Corrélation n'est pas causalité. Il n'y a pas de données de trafic : les taux sont rapportés au
nombre d'habitants, pas aux kilomètres parcourus. La catégorie « blessé hospitalisé » n'est plus
labellisée et n'est pas comparable avant 2018. Certaines données personnelles sont occultées dans
les fichiers publics. Le contrôle prédictif (ROC AUC 0,78 pour le gradient boosting en 2024)
montre que les conditions de l'accident n'expliquent qu'une partie de la gravité : la vitesse
réelle, l'alcool et l'état du véhicule ne sont pas dans les données ouvertes.
