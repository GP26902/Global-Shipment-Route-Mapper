from modules.data_model import (
    CARRIERS, COLUMNS, LABEL_SEED, PRODUCT_CLASSES, SOURCE_SEED, STAGE_TYPES,
    data_label, empty_frame,
)
from modules.seed import get_seed_frame


def test_twenty_routes():
    assert get_seed_frame()["shipment_id"].nunique() == 20


def test_schema_and_no_missing_coordinates():
    df = get_seed_frame()
    assert list(df.columns) == COLUMNS
    assert df[["lat", "lon"]].notna().all().all()
    assert df["lat"].between(-90, 90).all() and df["lon"].between(-180, 180).all()


def test_all_rows_are_seed_and_illustrative():
    df = get_seed_frame()
    assert (df["source"] == SOURCE_SEED).all()
    assert {data_label(s) for s in df["source"]} == {LABEL_SEED}


def test_categories_are_valid():
    df = get_seed_frame()
    assert set(df["carrier"]) <= set(CARRIERS)
    assert set(df["product_class"]) <= set(PRODUCT_CLASSES)
    assert set(df["stage_type"]) <= set(STAGE_TYPES)


def test_every_route_has_origin_first_and_destination_last():
    for sid, g in get_seed_frame().groupby("shipment_id"):
        g = g.sort_values("stop_order")
        assert list(g["stop_order"]) == list(range(1, len(g) + 1)), sid
        assert g["stage_type"].iloc[0] == "Origin", sid
        assert g["stage_type"].iloc[-1] == "Final Destination", sid
        assert g["carrier"].nunique() == 1 and g["product_class"].nunique() == 1


def test_seed_covers_all_carriers_and_classes():
    df = get_seed_frame()
    assert set(df["carrier"]) == set(CARRIERS)
    assert set(df["product_class"]) == set(PRODUCT_CLASSES)


def test_no_street_level_or_postal_data():
    assert (get_seed_frame()["postal_code"] == "").all()


def test_empty_frame_has_schema():
    assert list(empty_frame().columns) == COLUMNS and len(empty_frame()) == 0
