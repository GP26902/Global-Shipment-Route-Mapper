import json

from modules.borders import DATA_FILE, _load, border_lines, country_extent
from modules.locations import country_code
from modules.map_figure import build_map_figure
import pandas as pd


def test_country_codes():
    for name, code in {"United States": "US", "India": "IN", "Germany": "DE", "Turkey": "TR", "Türkiye": "TR",
                       "Russia": "RU", "South Korea": "KR", "United Kingdom": "GB", "UAE": "AE",
                       "Bangladesh": "BD", "China": "CN", "Vietnam": "VN"}.items():
        assert country_code(name) == code, name
    assert country_code("Atlantis") is None and country_code(None) is None and country_code("") is None


def test_data_file_is_present_and_sane():
    assert DATA_FILE.exists() and DATA_FILE.stat().st_size < 8_000_000
    data = _load()
    assert len(data) >= 230
    for code in ("US", "IN", "CN", "DE", "FR", "NO", "GB", "BD", "AE", "CA", "AU"):
        assert code in data, code
    for rings in data.values():
        for ring in rings:
            assert len(ring) >= 4
            assert all(-180 <= x <= 180 and -90 <= y <= 90 for x, y in ring)


def test_border_lines_shape():
    lons, lats = border_lines("United States")
    assert len(lons) == len(lats)
    assert lons.count(None) == lats.count(None) == len(_load()["US"])
    assert all((a is None) == (b is None) for a, b in zip(lons, lats))


def test_us_borders_cover_texas_and_india_has_its_states():
    lons, lats = border_lines("United States")
    pts = [(x, y) for x, y in zip(lons, lats) if x is not None]
    assert any(-104 < x < -94 and 27 < y < 35 for x, y in pts)          # inside Texas
    assert len(_load()["IN"]) >= 36 and len(_load()["DE"]) >= 16


def test_unknown_or_missing_country_has_no_borders():
    assert border_lines("Atlantis") is None and border_lines(None) is None and border_lines("") is None


def test_missing_data_file_does_not_break_the_map(monkeypatch, tmp_path):
    from modules import borders
    monkeypatch.setattr(borders, "DATA_FILE", tmp_path / "nope.json")
    borders._load.cache_clear()
    try:
        assert border_lines("United States") is None
    finally:
        monkeypatch.undo()
        borders._load.cache_clear()
    assert border_lines("United States") is not None


def test_figure_draws_borders_first_and_keeps_routes():
    routes = pd.DataFrame({"shipment_id": ["A", "A"], "stop_order": [1, 2], "carrier": ["UPS", "UPS"],
                           "lat": [29.7, 32.7], "lon": [-95.3, -96.8]})
    empty = pd.DataFrame(columns=["lat", "lon", "outgoing", "incoming"])
    plain = build_map_figure(routes, empty)
    with_b = build_map_figure(routes, empty, borders=border_lines("United States"))
    assert len(with_b.data) == len(plain.data) + 1
    first = with_b.data[0]
    assert first.name == "State borders" and first.showlegend is False and first.hoverinfo == "skip"
    assert [t.name for t in with_b.data[1:]] == [t.name for t in plain.data]
    assert all(t.name != "State borders" for t in plain.data)


def _within(frame, lon, lat):
    (x0, x1), (y0, y1) = frame
    return x0 <= lon <= x1 and y0 <= lat <= y1


def test_country_frame_covers_the_country_not_far_outlying_parts():
    us = country_extent("United States")                       # lower 48 only
    assert _within(us, -95.3, 29.7) and _within(us, -73.9, 40.7) and _within(us, -122.4, 37.8)
    assert not _within(us, -157.8, 21.3) and not _within(us, -150.0, 64.0)       # Hawaii, Alaska
    assert us[0][0] > -135 and us[1][1] < 55
    india = country_extent("India")
    assert _within(india, 72.8, 19.1) and _within(india, 77.2, 28.6) and _within(india, 88.4, 22.6)   # Mumbai, Delhi, Kolkata
    assert _within(india, 77.6, 13.0)                                                                  # Bengaluru
    fr = country_extent("France")                              # not French Guiana or Reunion
    assert _within(fr, 2.35, 48.86) and fr[0][0] > -10 and fr[1][0] > 35


def test_country_frame_is_ordered_and_inside_the_globe():
    for name in ("United States", "India", "Germany", "Russia", "Canada", "China", "Bangladesh",
                 "Singapore", "Indonesia", "Japan", "Australia"):
        (x0, x1), (y0, y1) = country_extent(name)
        assert -180 <= x0 < x1 <= 180 and -90 <= y0 < y1 <= 90, name


def test_country_frame_unknown_country_is_none():
    assert country_extent("Atlantis") is None and country_extent(None) is None
