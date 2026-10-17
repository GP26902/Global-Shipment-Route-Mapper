from datetime import date, datetime, time

import pytest

from modules.checkpoints import (
    combine_dt, delete_stop, generate_shipment_id, make_stop, stops_to_frame,
    validate_route, validate_stop_input,
)
from modules.data_model import COLUMNS, SOURCE_USER
from modules.geocoding import GeoResult

GEO = GeoResult(True, 29.76, -95.37, "Houston", "nominatim", "city")


def stop(stage, city="Houston", arrived=None, departed=None, postal=""):
    return make_stop(stage, "", city, "TX", "United States", postal, arrived, departed, GEO)


def route(*stages):
    return [stop(s) for s in stages]


def test_combine_dt():
    assert combine_dt(None, None) is None
    assert combine_dt(date(2026, 1, 2), time(3, 4)) == datetime(2026, 1, 2, 3, 4)
    with pytest.raises(ValueError):
        combine_dt(date(2026, 1, 2), None)


def test_stop_input_required_and_length_limits():
    errs = validate_stop_input("Origin", "", "", "", "", "", None, None)
    assert any("City is required" in e for e in errs) and any("Country is required" in e for e in errs)
    errs = validate_stop_input("Origin", "x" * 81, "Houston", "", "US", "", None, None)
    assert any("at most 80" in e for e in errs)


def test_street_addresses_rejected():
    for bad in ("123 Main Street", "4500 Oak Ave", "10 Downing St"):
        errs = validate_stop_input("Origin", bad, "Houston", "", "US", "", None, None)
        assert any("street address" in e for e in errs), bad
    ok = validate_stop_input("Sorting Hub", "Hub 5 North Terminal", "Houston", "", "US", "", None, None)
    assert ok == []


def test_postal_format_and_time_order():
    assert validate_stop_input("Origin", "", "Houston", "", "US", "77<script>", None, None)
    assert validate_stop_input("Origin", "", "Houston", "", "US", "SW1A 1AA", None, None) == []
    a, d = datetime(2026, 5, 2, 9), datetime(2026, 5, 2, 8)
    assert any("before arrived" in e for e in validate_stop_input("Origin", "", "Houston", "", "US", "", a, d))


def test_city_level_stops_drop_postal_code():
    assert stop("Final Destination", postal="77002")["postal_code"] == ""
    assert stop("Last-Mile Facility", postal="77002")["postal_code"] == ""
    assert stop("Sorting Hub", postal="77002")["postal_code"] == "77002"


def test_facility_defaults_to_city_and_stage():
    assert stop("Sorting Hub")["facility"] == "Houston Sorting Hub"


def test_delete_stop_returns_new_list_and_ignores_bad_index():
    stops = route("Origin", "Sorting Hub", "Final Destination")
    out = delete_stop(stops, 1)
    assert [s["stage_type"] for s in out] == ["Origin", "Final Destination"] and len(stops) == 3
    assert delete_stop(stops, 9) == stops and delete_stop(stops, -1) == stops


def test_valid_route_passes():
    assert validate_route(route("Origin", "Sorting Hub", "Final Destination"), "FedEx", "Apparel") == []


def test_route_structure_errors():
    assert validate_route(route("Origin"), "FedEx", "Apparel")
    assert any("first stop" in e for e in validate_route(route("Sorting Hub", "Final Destination"), "FedEx", "Apparel"))
    assert any("last stop" in e for e in validate_route(route("Origin", "Sorting Hub"), "FedEx", "Apparel"))
    assert any("only the first and last" in e for e in
               validate_route(route("Origin", "Origin", "Final Destination"), "FedEx", "Apparel"))
    assert validate_route(route("Origin", "Final Destination"), "Nope", "Apparel")
    assert validate_route(route("Origin", "Final Destination"), "FedEx", "Nope")


def test_unresolved_location_is_rejected():
    stops = route("Origin", "Final Destination")
    stops[0]["lat"] = None
    assert any("resolved location" in e for e in validate_route(stops, "FedEx", "Apparel"))


def test_chronological_order_across_stops():
    t = lambda h: datetime(2026, 5, 1, h)
    good = [stop("Origin", departed=t(8)), stop("Sorting Hub", arrived=t(10), departed=t(12)),
            stop("Final Destination", arrived=t(15))]
    assert validate_route(good, "UPS", "Apparel") == []
    bad = [stop("Origin", departed=t(8)), stop("Sorting Hub", arrived=t(7)),
           stop("Final Destination", arrived=t(15))]
    assert any("out of order" in e for e in validate_route(bad, "UPS", "Apparel"))


def test_frame_one_row_per_checkpoint_in_one_shipment():
    stops = route("Origin", "Sorting Hub", "Final Destination")
    df = stops_to_frame(stops, "DHL", "Electronics", "SHP-ABC12345", status="approved")
    assert list(df.columns) == COLUMNS and len(df) == 3
    assert (df["shipment_id"] == "SHP-ABC12345").all() and list(df["stop_order"]) == [1, 2, 3]
    assert (df["source"] == SOURCE_USER).all() and (df["status"] == "approved").all()
    assert df["created_at"].notna().all()


def test_shipment_ids_unique_and_formatted():
    ids = {generate_shipment_id() for _ in range(200)}
    assert len(ids) == 200 and all(i.startswith("SHP-") and len(i) == 12 for i in ids)
