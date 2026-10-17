import pandas as pd

from modules.checkpoints import make_stop, stops_to_frame
from modules.geocoding import GeoResult
from modules.hotspots import compute_hotspots
from modules.data_model import empty_frame


def frame(sid, carrier, cities, source="user"):
    stops = []
    for i, (city, state, country) in enumerate(cities):
        stage = "Origin" if i == 0 else "Final Destination" if i == len(cities) - 1 else "Sorting Hub"
        stops.append(make_stop(stage, "", city, state, country, "", None, None,
                               GeoResult(True, 10.0 + i, 20.0 + i, city, "nominatim", "city")))
    df = stops_to_frame(stops, carrier, "Apparel", sid, "approved")
    df["source"] = source
    return df


def test_counts_incoming_and_outgoing_per_city():
    df = pd.concat([
        frame("A", "FedEx", [("Dallas", "TX", "US"), ("Memphis", "TN", "US"), ("Boston", "MA", "US")]),
        frame("B", "UPS", [("Austin", "TX", "US"), ("Memphis", "TN", "US"), ("Miami", "FL", "US")]),
    ])
    h = compute_hotspots(df).set_index("city")
    assert (h.loc["Memphis", "incoming"], h.loc["Memphis", "outgoing"]) == (2, 2)
    assert (h.loc["Dallas", "incoming"], h.loc["Dallas", "outgoing"]) == (0, 1)
    assert (h.loc["Boston", "incoming"], h.loc["Boston", "outgoing"]) == (1, 0)
    assert h.loc["Memphis", "n_shipments"] == 2 and h.loc["Memphis", "carriers"] == "FedEx, UPS"


def test_variants_of_same_place_group_together():
    df = pd.concat([
        frame("A", "DHL", [("Dallas", "tx", "USA"), ("houston", "TX", "United States")]),
        frame("B", "DHL", [("Austin", "Texas", "US"), ("Houston", "Texas", "united states")]),
    ])
    h = compute_hotspots(df)
    assert len(h[h["city"] == "Houston"]) == 1
    assert h.loc[h["city"] == "Houston", "incoming"].iloc[0] == 2
    assert (h["state"].isin(["Texas"])).all() and (h["country"] == "United States").all()


def test_hop_inside_same_city_is_ignored():
    df = frame("A", "UPS", [("Houston", "TX", "US"), ("Houston", "TX", "US"), ("Dallas", "TX", "US")])
    h = compute_hotspots(df).set_index("city")
    assert (h.loc["Houston", "incoming"], h.loc["Houston", "outgoing"]) == (0, 1)


def test_labels_reflect_data_source_and_empty_input():
    mixed = pd.concat([
        frame("A", "FedEx", [("Dallas", "TX", "US"), ("Memphis", "TN", "US")], source="seed"),
        frame("B", "FedEx", [("Austin", "TX", "US"), ("Memphis", "TN", "US")], source="user"),
    ])
    h = compute_hotspots(mixed).set_index("city")
    assert h.loc["Dallas", "labels"] == "illustrative"
    assert h.loc["Memphis", "labels"] == "illustrative + user-reported, unverified"
    assert compute_hotspots(empty_frame()).empty
