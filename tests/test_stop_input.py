from datetime import datetime

import pytest

from modules.stop_input import parse_datetime_text as p, read_row, row_is_blank, split_city_zip as sp


@pytest.mark.parametrize("text,expected", [
    ("09/12/2026 3:01 AM", datetime(2026, 9, 12, 3, 1)),
    ("09/12/2026 03:01", datetime(2026, 9, 12, 3, 1)),
    ("09/12/2026 15:10", datetime(2026, 9, 12, 15, 10)),
    ("09/16/2026 6:13 A.M.", datetime(2026, 9, 16, 6, 13)),            # pasted from a UPS page
    ("09/16/2026 6:28 p.m.", datetime(2026, 9, 16, 18, 28)),
    ("09/16/2026 12:00 AM", datetime(2026, 9, 16, 0, 0)),
    ("09/16/2026 12:30 PM", datetime(2026, 9, 16, 12, 30)),
    ("09/16/2026 12:00 pm", datetime(2026, 9, 16, 12, 0)),
    ("2026-09-12 15:10", datetime(2026, 9, 12, 15, 10)),
    ("2026-09-12T03:01", datetime(2026, 9, 12, 3, 1)),
    ("9/2/26 7:05 PM", datetime(2026, 9, 2, 19, 5)),
    ("  09/12/2026    3:01   AM ", datetime(2026, 9, 12, 3, 1)),
    ("09/12/2026, 3:01 AM", datetime(2026, 9, 12, 3, 1)),
])
def test_valid_datetimes(text, expected):
    assert p(text) == expected


def test_blank_is_none():
    assert p("") is None and p("   ") is None and p(None) is None


@pytest.mark.parametrize("text", [
    "09/12/2026",             # date only
    "2026-09-12",
    "3:01 AM",                # time only
    "13/12/2026 3:01 AM",     # month 13 (slashes are month/day)
    "02/30/2026 10:00",       # not a real date
    "09/12/2026 25:00",
    "09/12/2026 13:00 PM",    # 24-hour hour with PM
    "09/12/2026 0:30 AM",
    "09/12/2026 10:75",
    "yesterday noon",
    "09.12.2026 10:00",
])
def test_invalid_datetimes(text):
    with pytest.raises(ValueError):
        p(text)


def test_error_message_gives_an_example():
    with pytest.raises(ValueError) as e:
        p("nonsense")
    assert "MM/DD/YYYY" in str(e.value)


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
    assert row_is_blank("", "", "", "", "")
    assert row_is_blank(None, None, "  ", "", "")
    assert not row_is_blank("India", "", "", "", "")
    assert not row_is_blank("", "", "x", "", "")
    assert not row_is_blank("", "", "", "09/12/2026 3:01 AM", "")


def test_read_row_ok():
    r = read_row("Origin", "India", "Maharashtra", "Mumbai 400001", "", "09/12/2026 5:30 AM")
    assert not r.errors
    assert r.values == {"stage": "Origin", "city": "Mumbai", "state": "Maharashtra", "country": "India",
                        "postal": "400001", "arrived": None, "departed": datetime(2026, 9, 12, 5, 30)}


def test_read_row_blank_state_and_times_are_fine():
    r = read_row("Sorting Hub", "Germany", None, "Cologne", "", "")
    assert not r.errors and r.values["state"] == "" and r.values["arrived"] is None


def test_read_row_requires_country_and_city():
    errs = read_row("Origin", None, None, "", "", "").errors
    assert "City is required." in errs and "Country is required." in errs


def test_zip_alone_gets_one_clear_message():
    errs = read_row("Origin", "United States", "Texas", "77477", "", "").errors
    assert len(errs) == 1 and "Type the city" in errs[0]


def test_bad_times_name_the_box():
    errs = read_row("Origin", "India", None, "Mumbai", "nonsense", "09/12/2026").errors
    assert any(e.startswith("Arrival:") for e in errs) and any(e.startswith("Departure:") for e in errs)


def test_departure_before_arrival_in_one_row():
    errs = read_row("Sorting Hub", "India", None, "Mumbai", "09/12/2026 5:00 PM", "09/12/2026 3:00 PM").errors
    assert any("before arrived" in e for e in errs)


def test_street_address_in_city_box_is_refused():
    errs = read_row("Origin", "United States", "Texas", "123 Main Street", "", "").errors
    assert any("street address" in e for e in errs)


def test_bad_postal_characters_refused():
    assert read_row("Sorting Hub", "United States", None, "Stafford, 77#77", "", "").errors
