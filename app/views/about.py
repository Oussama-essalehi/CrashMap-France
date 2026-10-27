"""Méthode et sources."""

import streamlit as st

import helpers as h


def render() -> None:
    st.title("Méthode et sources")
    st.markdown(f"""
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
  décodés en français d'après la documentation officielle de l'ONISR.
* **Tués** (décès dans les 30 jours) comme indicateur principal : la catégorie « blessé hospitalisé »
  n'est plus labellisée depuis 2019.
* **Taux masqués** sous un seuil d'accidents (100 par défaut, réglable dans la barre latérale).
* **Intervalles de confiance de Wilson** à 95 % pour les parts d'accidents mortels.
* **Régression logistique** pour mesurer chaque facteur à autres facteurs égaux ; **DBSCAN** pour les
  points noirs.
* Contrôles : 58 tests automatisés ; tués par an identiques aux bilans officiels de l'ONISR ; résultats
  SQL et Python identiques.

### Limites
* Pas de données de trafic : les taux sont rapportés aux habitants, pas aux kilomètres parcourus.
* Tous les accidents ne sont pas géolocalisés précisément ; certaines données personnelles sont occultées.
* Les écarts liés à l'équipement de sécurité ou aux conditions décrivent des **associations**, pas des
  causes.

### Le projet
Pipeline complet (Python, PostgreSQL, tableau de bord Power BI) : [{h.REPO_URL}]({h.REPO_URL})

**Oussama Essalehi** · [LinkedIn](https://www.linkedin.com/in/oussama-essalehi) ·
[oussama-essalehi.dev](https://oussama-essalehi.dev)
""")
