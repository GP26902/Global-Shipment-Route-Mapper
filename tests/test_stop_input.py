from datetime import date, datetime

import pytest

from modules.stop_input import read_row, row_is_blank, split_city_zip as sp


@pytest.mark.parametrize("text,expected", [
    ("Stafford", ("Stafford", "")),
    ("Stafford 77477", ("Stafford", "77477")),
    ("Stafford, 77477", ("Stafford", "77477")),
    ("  St. Louis   63101 ", ("St. Louis", "63101")),
    ("Washington, DC", ("Washington, DC", "")),
    ("Mumbai 400001", ("Mumbai", "400001")),
    ("Louisville 40209-1234", ("Louisville", "40209-1234")),
    ("London SW1A 1AA", ("London", "SW1A 1AA")),
    ("Ottawa K1A 0B1", ("Ottawa", "K1A 0B1")),
    ("Amsterdam 1012 AB", ("Amsterdam", "1012 AB")),
    ("77477", ("", "77477")),
    ("", ("", "")),
    ("Los Angeles", ("Los Angeles", "")),
])
def test_split_city_zip(text, expected):
    assert sp(text) == expected


def test_blank_row_detection_ignores_stage():
    assert row_is_blank("", "", "", None, None)
    assert row_is_blank(None, None, "  ", None, None)
    assert not row_is_blank("India", "", "", None, None)
    assert not row_is_blank("", "", "x", None, None)
    assert not row_is_blank("", "", "", date(2026, 9, 12), None)
    assert not row_is_blank("", "", "", None, date(2026, 9, 12))


def test_read_row_ok_dates_become_midnight():
    r = read_row("Origin", "India", "Maharashtra", "Mumbai 400001", None, date(2026, 9, 12))
    assert not r.errors
    assert r.values == {"stage": "Origin", "city": "Mumbai", "state": "Maharashtra", "country": "India",
                        "postal": "400001", "arrived": None, "departed": datetime(2026, 9, 12, 0, 0)}


def test_read_row_blank_state_and_dates_are_fine():
    r = read_row("Sorting Hub", "Germany", None, "Cologne", None, None)
    assert not r.errors and r.values["state"] == "" and r.values["arrived"] is None


def test_read_row_requires_country_and_city():
    errs = read_row("Origin", None, None, "", None, None).errors
    assert "City is required." in errs and "Country is required." in errs


def test_zip_alone_gets_one_clear_message():
    errs = read_row("Origin", "United States", "Texas", "77477", None, None).errors
    assert len(errs) == 1 and "Type the city" in errs[0]


def test_departure_before_arrival_in_one_row():
    errs = read_row("Sorting Hub", "India", None, "Mumbai", date(2026, 9, 12), date(2026, 9, 10)).errors
    assert any("before arrived" in e for e in errs)


def test_same_day_arrival_and_departure_is_fine():
    assert not read_row("Sorting Hub", "India", None, "Mumbai", date(2026, 9, 12), date(2026, 9, 12)).errors


def test_street_address_in_city_box_is_refused():
    errs = read_row("Origin", "United States", "Texas", "123 Main Street", None, None).errors
    assert any("street address" in e for e in errs)


def test_bad_postal_characters_refused():
    assert read_row("Sorting Hub", "United States", None, "Stafford, 77#77", None, None).errors
