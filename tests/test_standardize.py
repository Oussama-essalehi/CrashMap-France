"""Tests for the year-to-year standardization (src/crashmap/standardize.py)."""

import pandas as pd
import pytest

from crashmap import standardize as st


def test_all_years_share_one_schema(raw_tables):
    for table, schema in st.SCHEMA.items():
        assert list(raw_tables[table].columns) == ["year", *schema]
    assert sorted(raw_tables["caracteristiques"]["year"].unique()) == [2019, 2022]


def test_accident_id_column_renamed_in_2022(raw_tables):
    caract = raw_tables["caracteristiques"]
    assert 202200000001 in set(caract["num_acc"])
    assert caract["num_acc"].dtype == "int64"


def test_missing_id_usager_column_is_added_as_null(raw_tables):
    users = raw_tables["usagers"]
    assert users.loc[users["year"] == 2019, "id_usager"].isna().all()
    assert users.loc[users["year"] == 2022, "id_usager"].tolist() == ["1099700", "1099701", "1099702"]


def test_crlf_file_is_read(raw_tables):
    caract = raw_tables["caracteristiques"]
    row = caract[caract["num_acc"] == 202200000001].iloc[0]
    assert row["long"] == pytest.approx(8.7386)


@pytest.mark.parametrize("raw, expected", [
    ("48,8962100", 48.89621),
    ("44,0389580000", 44.038958),
    ("-21,1234", -21.1234),
    ("2.3522", 2.3522),
])
def test_coordinates_with_comma_decimal(raw, expected):
    assert st.parse_coordinate(pd.Series([raw]))[0] == pytest.approx(expected)


def test_empty_coordinate_is_null():
    assert pd.isna(st.parse_coordinate(pd.Series([""]))[0])


def test_codes_with_leading_space_and_artefacts():
    parsed = st.parse_int(pd.Series([" -1", "4", "", "#VALEURMULTI", "#ERREUR", "(1)"]))
    assert parsed.tolist()[:2] == [-1, 4]
    assert parsed[2:].isna().all()


def test_ids_lose_thousands_separator():
    assert st.parse_id(pd.Series(["138 306 524", "201 764"])).tolist() == ["138306524", "201764"]


@pytest.mark.parametrize("raw, expected", [("1", "01"), ("01", "01"), ("2A", "2A"), ("2b", "2B"),
                                           ("971", "971"), ("75", "75")])
def test_department_codes(raw, expected):
    assert st.normalize_department(pd.Series([raw]))[0] == expected


def test_department_is_padded_in_fixture(raw_tables):
    deps = set(raw_tables["caracteristiques"]["dep"])
    assert deps == {"01", "31", "971", "2A"}


def test_commune_codes_are_padded():
    assert st.normalize_commune(pd.Series(["1053", "2A004", "75101"])).tolist() == ["01053", "2A004", "75101"]


def test_available_years(tmp_path):
    for table in st.TABLES:
        (tmp_path / f"{table}-2021.csv").write_text("x")
    (tmp_path / "caracteristiques-2020.csv").write_text("x")  # incomplete year
    assert st.available_years(tmp_path) == [2021]
