"""Tests for the cleaning rules and the three grains (src/crashmap/clean.py)."""

import pandas as pd
import pytest

from crashmap import clean


# ---------------------------------------------------------------- missing values and decoding

def test_minus_one_becomes_null_never_a_category():
    df = pd.DataFrame({"atm": pd.array([-1, 1, 2], dtype="Int64"),
                       "trajet": pd.array([0, -1, 5], dtype="Int64"),
                       "secu1": pd.array([0, -1, 1], dtype="Int64")})
    out, counts = clean.replace_missing_codes(df, ["atm", "trajet", "secu1"])
    assert out["atm"].isna().tolist() == [True, False, False]
    assert out["trajet"].isna().tolist() == [True, True, False]  # 0 = "Non renseigné" for trajet
    assert out["secu1"].tolist()[0] == 0  # 0 = "Aucun équipement" is a real answer
    assert pd.isna(out["secu1"][1])
    assert counts == {"atm": 1, "trajet": 2, "secu1": 1}


def test_minus_one_is_null_after_pipeline(grains):
    acc = grains["accidents"].set_index("accident_id")
    assert pd.isna(acc.loc[201900000002, "atm"])
    assert pd.isna(acc.loc[201900000002, "atm_label"])
    assert "Non renseigné" not in set(acc["atm_label"].dropna())


def test_unknown_codes_are_nulled():
    df = pd.DataFrame({"lum": pd.array([1, 7], dtype="Int64")})
    out, counts = clean.drop_unknown_codes(df, ["lum"])
    assert out["lum"].isna().tolist() == [False, True]
    assert counts["lum"] == 1


def test_decoding_to_french_labels(grains):
    acc = grains["accidents"].set_index("accident_id")
    assert acc.loc[201900000001, "lum_label"] == "Nuit avec éclairage public non allumé"
    assert acc.loc[201900000002, "int_label"] == "Giratoire"
    assert acc.loc[201900000001, "catr_label"] == "Route nationale"
    victims = grains["victims"]
    assert set(victims["grav_label"].dropna()) == {"Indemne", "Tué", "Blessé hospitalisé", "Blessé léger"}
    vehicles = grains["vehicles"].set_index("vehicle_key")
    assert vehicles.loc["202200000001_813952", "catv_label"] == "EDP à moteur"


# ---------------------------------------------------------------- types and derived columns

@pytest.mark.parametrize("hrmn, hour, minute", [("01:30", 1, 30), ("23:59", 23, 59), ("0745", 7, 45),
                                                ("7:05", 7, 5)])
def test_parse_hrmn(hrmn, hour, minute):
    h, m = clean.parse_hrmn(pd.Series([hrmn]))
    assert (h[0], m[0]) == (hour, minute)


@pytest.mark.parametrize("hrmn", ["25:00", "12:75", "", "ab:cd"])
def test_parse_hrmn_invalid(hrmn):
    h, _ = clean.parse_hrmn(pd.Series([hrmn], dtype="string"))
    assert pd.isna(h[0])


def test_date_weekday_and_time_band(grains):
    acc = grains["accidents"].set_index("accident_id")
    row = acc.loc[201900000001]
    assert row["date"] == pd.Timestamp("2019-11-30")
    assert row["weekday"] == "Samedi" and bool(row["is_weekend"])
    assert row["time_band"] == "Nuit (21h-6h)"
    assert acc.loc[201900000002, "time_band"] == "Journée (10h-17h)"


def test_invalid_date_is_nat():
    out = clean.build_date(pd.Series([2019, 2019]), pd.Series([2, 13]), pd.Series([30, 1]))
    assert out.isna().all()


@pytest.mark.parametrize("year, birth, age", [(2019, 1980, 39), (2022, 2022, 0), (2019, 1850, None),
                                              (2019, 2030, None), (2019, None, None)])
def test_age_at_accident(year, birth, age):
    result = clean.age_at_accident(pd.Series([year]), pd.Series([birth], dtype="Int64"))[0]
    assert (pd.isna(result) and age is None) or result == age


def test_age_bands():
    bands = clean.age_band(pd.Series([0, 13, 14, 24, 39, 75, 99, None], dtype="Int64"))
    assert bands.tolist()[:7] == ["0-13 ans", "0-13 ans", "14-17 ans", "18-24 ans", "35-44 ans",
                                  "75 ans et +", "75 ans et +"]
    assert pd.isna(bands[7])


def test_victim_ages_in_pipeline(grains):
    v = grains["victims"].set_index("victim_id")
    assert v.loc["201900000001_001", "age"] == 39
    assert v.loc["201900000001_001", "age_band"] == "35-44 ans"
    assert pd.isna(v.loc["201900000002_001", "age"])  # born in 1850: implausible


def test_coordinates_validated_against_territory():
    out = clean.validate_coordinates(
        lat=pd.Series([48.85, 48.85, 16.25, 0.0]), lon=pd.Series([2.35, 2.35, -61.55, 0.0]),
        dep=pd.Series(["75", "971", "971", "13"]))
    assert out["coord_status"].tolist() == ["valide", "hors zone", "valide", "manquante"]
    assert out["lat"].isna().tolist() == [False, True, False, True]


def test_corsica_inside_mainland_box(grains):
    acc = grains["accidents"].set_index("accident_id")
    assert acc.loc[202200000001, "coord_status"] == "valide"
    assert acc.loc[201900000003, "coord_status"] == "hors zone"
    assert pd.isna(acc.loc[201900000003, "lat"])


def test_speed_limit_rules(grains):
    acc = grains["accidents"].set_index("accident_id")
    assert acc.loc[201900000001, "vma_band"] == "80-90 km/h"
    assert pd.isna(acc.loc[201900000002, "vma"])  # -1
    assert bool(acc.loc[201900000003, "vma_implausible"]) and pd.isna(acc.loc[201900000003, "vma"])


def test_in_town_and_department(grains):
    acc = grains["accidents"].set_index("accident_id")
    assert bool(acc.loc[201900000002, "in_town"]) and not bool(acc.loc[201900000001, "in_town"])
    assert acc.loc[201900000001, "dep_code"] == "01"
    assert acc.loc[202200000001, "dep_name"] == "Corse-du-Sud"
    assert acc.loc[201900000003, "zone"] == "Outre-mer (DROM)"


def test_safety_equipment(grains):
    v = grains["victims"].set_index("victim_id")
    assert bool(v.loc["201900000001_001", "seatbelt_worn"])
    assert bool(v.loc["201900000001_003", "helmet_worn"])
    assert pd.isna(v.loc["201900000002_001", "seatbelt_worn"])  # "Non déterminable"
    assert not bool(v.loc["202200000001_001", "helmet_worn"])  # "Aucun équipement"


# ---------------------------------------------------------------- keys, grains, double counting

def test_main_lieu_is_kept():
    lieux = pd.DataFrame({"num_acc": [1, 1, 2], "catr": pd.array([4, 3, 4], dtype="Int64"),
                          "vma": pd.array([50, 80, 30], dtype="Int64")})
    out, n_rows = clean.select_main_lieu(lieux)
    assert len(out) == 2
    assert out.set_index("num_acc").loc[1, "catr"] == 3
    assert n_rows.to_dict() == {1: 2, 2: 1}


def test_lieux_dedup_in_pipeline(grains):
    acc = grains["accidents"].set_index("accident_id")
    assert acc.loc[202200000001, "lieux_rows"] == 2
    assert acc.loc[202200000001, "catr_label"] == "Route départementale"
    assert acc.loc[202200000001, "vma"] == 80


def test_grain_sizes(grains):
    assert len(grains["accidents"]) == 4
    assert len(grains["vehicles"]) == 7
    assert len(grains["victims"]) == 9
    assert grains["accidents"]["accident_id"].is_unique
    assert grains["vehicles"]["vehicle_key"].is_unique
    assert grains["victims"]["victim_id"].is_unique


def test_accident_counts_identical_across_grains(grains):
    a, v, u = grains["accidents"], grains["vehicles"], grains["victims"]
    assert a["accident_id"].nunique() == v["accident_id"].nunique() == u["accident_id"].nunique() == 4
    for year in (2019, 2022):
        n = (a["year"] == year).sum()
        assert n == v.loc[v["year"] == year, "accident_id"].nunique()
        assert n == u.loc[u["year"] == year, "accident_id"].nunique()
    checks = clean.consistency_checks(grains)
    for year in checks["by_year"].values():
        assert year["accidents_from_accident_grain"] == year["accidents_from_vehicle_grain"] \
            == year["accidents_from_victim_grain"]
        assert year["killed_from_accident_grain"] == year["killed_from_victim_grain"] \
            == year["killed_from_vehicle_grain"]


def test_naive_join_overcounts_accidents(grains):
    a, v, u = grains["accidents"], grains["vehicles"], grains["victims"]
    joined = a.merge(v[["accident_id", "vehicle_key"]], on="accident_id").merge(u[["vehicle_key"]], on="vehicle_key")
    assert len(joined) > len(a)  # the trap: one row per user, not per accident
    assert joined["accident_id"].nunique() == len(a)


def test_killed_and_flags_aggregated(grains):
    acc = grains["accidents"].set_index("accident_id")
    assert acc["n_killed"].sum() == grains["victims"]["killed"].sum() == 2
    assert acc.loc[201900000001, "n_vehicles"] == 2
    assert bool(acc.loc[201900000001, "fatal"]) and bool(acc.loc[201900000001, "two_wheeler_involved"])
    assert bool(acc.loc[201900000002, "pedestrian_involved"])
    assert bool(acc.loc[201900000003, "serious"]) and not bool(acc.loc[201900000003, "fatal"])
    assert bool(acc.loc[202200000001, "personal_mobility_involved"])
    assert acc.loc[202200000001, "n_severity_unknown"] == 1


def test_vehicle_without_users_is_kept(grains):
    veh = grains["vehicles"].set_index("vehicle_key")
    assert veh.loc["201900000003_100005", "n_users"] == 0


def test_pedestrian_travel_mode(grains):
    v = grains["victims"].set_index("victim_id")
    assert v.loc["201900000002_002", "user_mode"] == "Piéton"
    assert v.loc["201900000001_003", "user_mode"] == "Moto > 125 cm3"
