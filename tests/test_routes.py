import math

from modules.routes import (
    build_route_path, great_circle_km, great_circle_points, split_antimeridian,
)


def test_endpoints_are_exact():
    pts = great_circle_points(29.76, -95.37, 51.51, -0.13)
    assert pts[0] == (29.76, -95.37)
    assert pts[-1] == (51.51, -0.13)


def test_arc_length_matches_haversine():
    pts = great_circle_points(29.76, -95.37, 51.51, -0.13)
    total = sum(great_circle_km(*a, *b) for a, b in zip(pts[:-1], pts[1:]))
    direct = great_circle_km(29.76, -95.37, 51.51, -0.13)
    assert math.isclose(total, direct, rel_tol=1e-3)


def test_equator_midpoint():
    pts = great_circle_points(0, 0, 0, 90, step_deg=90)
    assert any(math.isclose(lat, 0, abs_tol=1e-6) and math.isclose(lon, 45, abs_tol=1e-6)
               for lat, lon in pts)


def test_same_point_returns_single_point():
    assert great_circle_points(10, 20, 10, 20) == [(10, 20)]


def test_arc_curves_poleward():
    # Houston -> London great circle bows north of the straight lat/lon line.
    pts = great_circle_points(29.76, -95.37, 51.51, -0.13)
    mid_lat = pts[len(pts) // 2][0]
    assert mid_lat > (29.76 + 51.51) / 2


def test_antimeridian_split_inserts_break():
    lats, lons = split_antimeridian([(35.0, 175.0), (36.0, -175.0)])
    assert None in lons and None in lats
    assert lons[1] == 180.0 and lons[3] == -180.0


def test_no_wrap_jumps_in_path_across_pacific():
    # Osaka -> Seattle crosses the antimeridian.
    lats, lons = build_route_path([(34.69, 135.50), (47.61, -122.33)])
    assert None in lons
    vals = [v for v in lons]
    for a, b in zip(vals[:-1], vals[1:]):
        if a is not None and b is not None:
            assert abs(a - b) <= 180


def test_multi_stop_path_visits_every_stop_in_order():
    stops = [(29.76, -95.37), (35.15, -90.05), (40.71, -74.0)]
    lats, lons = build_route_path(stops)
    for s in stops:
        assert any(la is not None and math.isclose(la, s[0], abs_tol=1e-9)
                   and math.isclose(lo, s[1], abs_tol=1e-9) for la, lo in zip(lats, lons))
    assert lats.index(stops[1][0]) < lats.index(stops[2][0])


def test_empty_and_single_stop():
    assert build_route_path([]) == ([], [])
    assert build_route_path([(1.0, 2.0)]) == ([1.0], [2.0])
