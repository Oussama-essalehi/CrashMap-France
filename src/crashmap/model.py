"""Severity model: which factors raise the probability that an accident is fatal?

1. Logistic regression (statsmodels) of ``fatal`` at the accident grain, categorical predictors
   with explicit reference levels -> odds ratios with 95 % confidence intervals, translated into
   plain French sentences.
2. Predictive check (scikit-learn): class-weighted logistic regression and gradient boosting,
   trained on 2019 to N-1 and tested on the latest year (temporal split), ROC AUC, average
   precision and permutation importance. The goal is to understand risk factors, not to deploy a
   prediction model.

Outputs: ``reports/tables/odds_ratios.csv``, ``reports/tables/model_metrics.json``,
``reports/tables/feature_importance.csv``, figures fig07 and fig12.
"""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import statsmodels.formula.api as smf
from plotly.subplots import make_subplots
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score, roc_curve
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder

from crashmap import viz
from crashmap.analyze import SOURCE, TABLES_DIR
from crashmap.config import get_paths, load_config

log = logging.getLogger(__name__)

# Predictor -> (French label, reference level)
PREDICTORS: dict[str, tuple[str, str]] = {
    "time_band": ("Tranche horaire", "Journée (10h-17h)"),
    "day_type": ("Type de jour", "Semaine"),
    "light": ("Luminosité", "Plein jour"),
    "weather": ("Météo", "Normale"),
    "surface": ("Surface", "Normale"),
    "road": ("Catégorie de route", "Voie communale"),
    "speed": ("Vitesse maximale autorisée", "40-50 km/h"),
    "location": ("Localisation", "En agglomération"),
    "intersection": ("Intersection", "Hors intersection"),
    "two_wheeler": ("Deux-roues ou EDP impliqué", "Non"),
    "pedestrian": ("Piéton impliqué", "Non"),
    "vehicles": ("Nombre de véhicules", "2 véhicules"),
}

WEATHER_GROUPS = {"Normale": "Normale", "Pluie légère": "Pluie", "Pluie forte": "Pluie",
                  "Temps couvert": "Temps couvert", "Brouillard - fumée": "Brouillard - fumée",
                  "Neige - grêle": "Neige - grêle", "Vent fort - tempête": "Vent fort - tempête",
                  "Temps éblouissant": "Temps éblouissant", "Autre": "Autre"}
SURFACE_GROUPS = {"Normale": "Normale", "Mouillée": "Mouillée", "Flaques": "Mouillée", "Inondée": "Mouillée",
                  "Enneigée": "Neige / verglas", "Verglacée": "Neige / verglas", "Boue": "Autre",
                  "Corps gras - huile": "Autre", "Autre": "Autre"}
ROAD_GROUPS = {"Autoroute": "Autoroute", "Route nationale": "Route nationale",
               "Route départementale": "Route départementale", "Voie communale": "Voie communale",
               "Route de métropole urbaine": "Route de métropole urbaine",
               "Hors réseau public": "Autre / parking", "Parc de stationnement ouvert à la circulation publique": "Autre / parking",
               "Autre": "Autre / parking"}
INTERSECTION_GROUPS = {"Hors intersection": "Hors intersection", "Intersection en X": "Intersection X/T/Y",
                       "Intersection en T": "Intersection X/T/Y", "Intersection en Y": "Intersection X/T/Y",
                       "Intersection à plus de 4 branches": "Autre intersection", "Giratoire": "Giratoire",
                       "Place": "Autre intersection", "Passage à niveau": "Passage à niveau",
                       "Autre intersection": "Autre intersection"}


def model_frame(acc: pd.DataFrame) -> pd.DataFrame:
    """Accident-level design frame with grouped categorical predictors (rows with a missing predictor dropped)."""
    df = pd.DataFrame({
        "accident_id": acc["accident_id"],
        "year": acc["year"],
        "fatal": acc["fatal"].astype(int),
        "time_band": acc["time_band"],
        "day_type": acc["is_weekend"].map({True: "Week-end", False: "Semaine"}),
        "light": acc["lum_label"],
        "weather": acc["atm_label"].map(WEATHER_GROUPS),
        "surface": acc["surf_label"].map(SURFACE_GROUPS),
        "road": acc["catr_label"].map(ROAD_GROUPS),
        "speed": acc["vma_band"],
        "location": acc["in_town"].map({True: "En agglomération", False: "Hors agglomération"}),
        "intersection": acc["int_label"].map(INTERSECTION_GROUPS),
        "two_wheeler": acc["two_wheeler_involved"].map({True: "Oui", False: "Non"}),
        "pedestrian": acc["pedestrian_involved"].map({True: "Oui", False: "Non"}),
        "vehicles": pd.cut(acc["n_vehicles"], bins=[0, 1, 2, np.inf],
                           labels=["1 véhicule", "2 véhicules", "3 véhicules et +"]).astype("string"),
    })
    before = len(df)
    df = df.dropna().reset_index(drop=True)
    for col in PREDICTORS:
        df[col] = df[col].astype(str)
    log.info("Model frame: %d accidents (%d dropped for missing predictors)", len(df), before - len(df))
    return df


def fit_logit(df: pd.DataFrame):
    """Fit the logistic regression with treatment coding and the reference levels of PREDICTORS."""
    terms = [f"C({col}, Treatment(reference={ref!r}))" for col, (_, ref) in PREDICTORS.items()]
    formula = "fatal ~ " + " + ".join(terms)
    result = smf.logit(formula, data=df).fit(disp=False, maxiter=200)
    log.info("Logit fitted: pseudo R2 = %.3f, n = %d", result.prsquared, int(result.nobs))
    return result


def odds_ratio_table(result, df: pd.DataFrame) -> pd.DataFrame:
    """Odds ratios with 95 % CI, one row per non-reference level."""
    params = result.params
    ci = result.conf_int()
    rows = []
    for name in params.index:
        if name == "Intercept":
            continue
        col = name.split("(")[1].split(",")[0]
        level = name.split("[T.")[1].rstrip("]")
        n_level = int((df[col] == level).sum())
        rows.append({
            "variable": col, "variable_label": PREDICTORS[col][0], "level": level,
            "reference": PREDICTORS[col][1], "n_accidents": n_level,
            "odds_ratio": float(np.exp(params[name])),
            "ci_low": float(np.exp(ci.loc[name, 0])), "ci_high": float(np.exp(ci.loc[name, 1])),
            "p_value": float(result.pvalues[name]),
        })
    out = pd.DataFrame(rows)
    out[["odds_ratio", "ci_low", "ci_high"]] = out[["odds_ratio", "ci_low", "ci_high"]].round(3)
    return out.sort_values("odds_ratio", ascending=False).reset_index(drop=True)


def fr(value: float, digits: int = 1) -> str:
    """French decimal formatting (comma separator)."""
    return f"{value:.{digits}f}".replace(".", ",")


def plain_sentences(or_table: pd.DataFrame, top: int = 8) -> list[str]:
    """Translate the strongest significant risk factors into French sentences."""
    sig = or_table[(or_table["p_value"] < 0.001) & (or_table["ci_low"] > 1) & (or_table["n_accidents"] >= 500)]
    return [
        f"{r.variable_label} « {r.level} » (au lieu de « {r.reference} ») : à autres facteurs égaux, la cote "
        f"d'un accident mortel est multipliée par {fr(r.odds_ratio)} (IC 95 % : {fr(r.ci_low)} à {fr(r.ci_high)})."
        for r in sig.head(top).itertuples()
    ]


def predictive_check(df: pd.DataFrame) -> dict:
    """Temporal split: train on years < last, test on the last year."""
    last = int(df["year"].max())
    train, test = df[df["year"] < last], df[df["year"] == last]
    features = list(PREDICTORS)
    X_train, y_train, X_test, y_test = train[features], train["fatal"], test[features], test["fatal"]
    seed = int(load_config()["analysis"]["random_state"])

    logit = Pipeline([
        ("prep", ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore", drop="first"), features)])),
        ("clf", LogisticRegression(class_weight="balanced", max_iter=2000)),
    ])
    gbm = Pipeline([
        ("prep", ColumnTransformer([("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), features)])),
        ("clf", HistGradientBoostingClassifier(categorical_features=list(range(len(features))),
                                               class_weight="balanced", max_iter=300, learning_rate=0.05,
                                               max_leaf_nodes=31, random_state=seed)),
    ])
    models = {"Régression logistique (pondérée)": logit, "Gradient boosting": gbm}
    metrics, curves, importances = {}, {}, {}
    for name, model in models.items():
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_test)[:, 1]
        pred = (proba >= 0.5).astype(int)
        tp = int(((pred == 1) & (y_test == 1)).sum())
        metrics[name] = {
            "roc_auc": round(float(roc_auc_score(y_test, proba)), 4),
            "average_precision": round(float(average_precision_score(y_test, proba)), 4),
            "precision_at_0_5": round(tp / max(int(pred.sum()), 1), 4),
            "recall_at_0_5": round(tp / max(int(y_test.sum()), 1), 4),
        }
        fpr, tpr, _ = roc_curve(y_test, proba)
        prec, rec, _ = precision_recall_curve(y_test, proba)
        curves[name] = {"fpr": fpr, "tpr": tpr, "precision": prec, "recall": rec}
        perm = permutation_importance(model, X_test, y_test, scoring="roc_auc", n_repeats=5,
                                      random_state=seed, n_jobs=1)
        importances[name] = pd.Series(perm.importances_mean, index=features)
        log.info("%s: ROC AUC %.3f, AP %.3f", name, metrics[name]["roc_auc"], metrics[name]["average_precision"])
    summary = {
        "train_years": [int(train["year"].min()), int(train["year"].max())], "test_year": last,
        "n_train": int(len(train)), "n_test": int(len(test)),
        "fatal_rate_train_pct": round(float(y_train.mean() * 100), 2),
        "fatal_rate_test_pct": round(float(y_test.mean() * 100), 2),
        "models": metrics,
    }
    imp = pd.DataFrame(importances)
    imp.index.name = "feature"
    imp["label"] = [PREDICTORS[f][0] for f in imp.index]
    return {"summary": summary, "curves": curves, "importance": imp.sort_values("Gradient boosting", ascending=False)}


def fig_odds_ratios(or_table: pd.DataFrame, path) -> None:
    tbl = or_table[or_table["n_accidents"] >= 500].copy()
    tbl["label"] = tbl["variable_label"] + " : " + viz.short(tbl["level"])
    tbl = tbl.sort_values("odds_ratio")
    colors = [viz.ORANGE if lo > 1 else (viz.BLUE if hi < 1 else viz.GREY) for lo, hi in zip(tbl["ci_low"], tbl["ci_high"])]
    fig = go.Figure(go.Scatter(
        x=tbl["odds_ratio"], y=tbl["label"], mode="markers", marker=dict(size=9, color=colors),
        error_x=dict(type="data", symmetric=False, array=tbl["ci_high"] - tbl["odds_ratio"],
                     arrayminus=tbl["odds_ratio"] - tbl["ci_low"], color=viz.TEXT_SECONDARY, thickness=1.5),
        showlegend=False))
    fig.add_vline(x=1, line=dict(color=viz.TEXT_SECONDARY, width=1))
    ticks = [0.3, 0.5, 0.7, 1, 1.5, 2, 3, 5, 7]
    fig.update_xaxes(type="log", tickvals=ticks, ticktext=[fr(t, 1).replace(",0", "") for t in ticks],
                     title_text="Odds ratio (échelle log) : > 1 = risque d'accident mortel accru")
    fig.update_layout(height=1100, margin=dict(l=420),
                      title=viz.subtitle("Facteurs de mortalité, à autres facteurs égaux (régression logistique)",
                                         "Orange : facteur aggravant, bleu : protecteur, gris : non significatif. "
                                         "Modalités de plus de 500 accidents."))
    viz.save(fig, path, width=1300, height=1100)


def fig_roc_pr(check: dict, path) -> None:
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Courbe ROC", "Précision-rappel"), horizontal_spacing=0.1)
    for color, (name, c) in zip((viz.BLUE, viz.ORANGE), check["curves"].items()):
        m = check["summary"]["models"][name]
        label = f"{name} : ROC AUC {fr(m['roc_auc'], 3)}, AP {fr(m['average_precision'], 3)}"
        fig.add_scatter(x=c["fpr"], y=c["tpr"], mode="lines", line=dict(color=color, width=2),
                        name=label, legendgroup=name, row=1, col=1)
        fig.add_scatter(x=c["recall"], y=c["precision"], mode="lines", line=dict(color=color, width=2),
                        name=label, legendgroup=name, showlegend=False, row=1, col=2)
    fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=viz.GREY, width=1), showlegend=False, row=1, col=1)
    base = check["summary"]["fatal_rate_test_pct"] / 100
    fig.add_scatter(x=[0, 1], y=[base, base], mode="lines", line=dict(color=viz.GREY, width=1), showlegend=False, row=1, col=2)
    fig.update_xaxes(title_text="Taux de faux positifs", row=1, col=1)
    fig.update_yaxes(title_text="Taux de vrais positifs", row=1, col=1)
    fig.update_xaxes(title_text="Rappel", row=1, col=2)
    fig.update_yaxes(title_text="Précision", row=1, col=2)
    s = check["summary"]
    fig.update_layout(margin=dict(t=150), legend=dict(y=1.12),
                      title=viz.subtitle("Contrôle prédictif : entraînement 2019-2023, test 2024",
                                         f"{fr(s['fatal_rate_test_pct'])} % d'accidents mortels en {s['test_year']} "
                                         "(ligne grise = modèle aléatoire). Objectif : comprendre, pas prédire."))
    viz.save(fig, path, width=1400, height=640)


def main() -> None:
    paths = get_paths()
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    acc = pd.read_parquet(paths.processed / "accidents.parquet")
    df = model_frame(acc)

    result = fit_logit(df)
    or_table = odds_ratio_table(result, df)
    or_table.to_csv(TABLES_DIR / "odds_ratios.csv", index=False)
    sentences = plain_sentences(or_table)

    check = predictive_check(df)
    check["importance"].round(5).to_csv(TABLES_DIR / "feature_importance.csv")
    metrics = {
        "logit": {"n": int(result.nobs), "pseudo_r2": round(float(result.prsquared), 4),
                  "aic": round(float(result.aic), 1), "fatal_rate_pct": round(float(df["fatal"].mean() * 100), 2)},
        "predictive_check": check["summary"],
        "top_factors_sentences": sentences,
    }
    (TABLES_DIR / "model_metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    for sentence in sentences:
        log.info(sentence)

    fig_odds_ratios(or_table, paths.figures / "fig07_odds_ratios.png")
    fig_roc_pr(check, paths.figures / "fig12_roc_pr.png")


if __name__ == "__main__":
    from crashmap.config import setup_logging

    setup_logging()
    main()
