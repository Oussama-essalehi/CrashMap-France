"""Hotspot clustering on synthetic coordinates (no network, no raw data)."""

import numpy as np
import pandas as pd

from crashmap.maps import find_hotspots


def _accidents(points: list[tuple[float, float]]) -> pd.DataFrame:
    n = len(points)
    return pd.DataFrame({
        "accident_id": np.arange(n), "lat": [p[0] for p in points], "lon": [p[1] for p in points],
        "n_killed": [1] + [0] * (n - 1), "n_hospitalized": [0] * n, "fatal": [True] + [False] * (n - 1),
        "year": [2024] * n, "adr": ["RUE A"] * n, "in_town": [True] * n,
    })


def test_dbscan_finds_dense_cluster_and_ignores_isolated_points():
    rng = np.random.default_rng(0)
    dense = [(43.6045 + d1, 1.4440 + d2) for d1, d2 in rng.normal(0, 0.0002, size=(12, 2))]  # ~20 m spread
    isolated = [(43.62, 1.40), (43.58, 1.50), (43.65, 1.46)]
    acc = _accidents(dense + isolated)
    victims = pd.DataFrame({"accident_id": acc["accident_id"], "user_mode": "Piéton", "killed": False})
    hotspots, labels = find_hotspots(acc, victims, radius_m=100, min_samples=8, top=10)
    assert len(hotspots) == 1
    assert hotspots.loc[0, "n_accidents"] == 12
    assert hotspots.loc[0, "n_killed"] == 1
    assert (labels[-3:] == -1).all()
