from modules.places import canon_country, canon_state
from modules.regions import (
    WORLD_LAT, WORLD_LON, apply_drilldown, city_options, country_options, state_options,
)
from modules.seed import get_seed_frame

DF = get_seed_frame()


def test_canonical_names():
    assert canon_country("usa") == canon_country("U.S.A.") == "United States"
    assert canon_state("USA", "tx") == canon_state("United States", "Texas") == "Texas"
    assert canon_state("India", "maharashtra") == "Maharashtra"


def test_cascading_options():
    assert "United States" in country_options(DF) and "Germany" in country_options(DF)
    assert "Texas" in state_options(DF, "United States") and "Bayern" not in state_options(DF, "United States")
    assert "Houston" in city_options(DF, "United States", "Texas")
    assert "Seattle" not in city_options(DF, "United States", "Texas")
    assert state_options(DF, "") == [] and city_options(DF, "") == []


def test_world_shows_everything_with_fixed_frame():
    d = apply_drilldown(DF)
    assert d.level == "World" and d.routes["shipment_id"].nunique() == 20
    assert d.lon_range == WORLD_LON and d.lat_range == WORLD_LAT


def test_country_keeps_whole_routes_but_only_local_hotspots():
    d = apply_drilldown(DF, "United States")
    assert d.level == "Country"
    ids = set(d.routes["shipment_id"])
    assert "SEED-001" in ids and "SEED-007" not in ids       # Shenzhen->US route kept, UK-only dropped
    assert (d.routes[d.routes.shipment_id == "SEED-001"]["city"] == "Shenzhen").any()  # full route retained
    assert set(d.hotspots["country"]) == {"United States"}


def test_state_and_city_levels_narrow_down():
    state = apply_drilldown(DF, "United States", "Texas")
    city = apply_drilldown(DF, "United States", "Texas", "Houston")
    assert state.level == "State" and city.level == "City"
    assert len(city.routes["shipment_id"].unique()) <= len(state.routes["shipment_id"].unique()) < 16
    assert list(city.hotspots["city"]) == ["Houston"]
    assert set(state.hotspots["state"]) == {"Texas"}
    hou = city.hotspots.iloc[0]
    assert hou.incoming >= 3 and hou.outgoing >= 3


def test_frame_contains_region_points_and_is_valid():
    for args in [("United States",), ("United States", "Texas"), ("United States", "Texas", "Houston")]:
        d = apply_drilldown(DF, *args)
        (lo0, lo1), (la0, la1) = d.lon_range, d.lat_range
        assert -180 <= lo0 < lo1 <= 180 and -90 <= la0 < la1 <= 90
        assert lo1 - lo0 >= 4 and la1 - la0 >= 4
        for h in d.hotspots.itertuples():
            assert lo0 <= h.lon <= lo1 and la0 <= h.lat <= la1


def test_city_view_frames_nearby_neighbours_but_not_far_ones():
    d = apply_drilldown(DF, "United States", "Texas", "Houston")
    (lo0, lo1), _ = d.lon_range, d.lat_range
    assert lo0 < -97 and lo1 > -94         # San Antonio / Port Arthur area neighbours in frame
    assert lo1 < -60                       # Shenzhen-Anchorage legs not in frame


def test_unknown_region_and_empty_data_fall_back_to_world():
    d = apply_drilldown(DF, "Atlantis")
    assert d.routes.empty and d.lon_range == WORLD_LON
    assert apply_drilldown(DF.iloc[0:0]).routes.empty
