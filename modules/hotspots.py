"""Hub hotspots: incoming and outgoing segment counts per city. No Streamlit dependency."""
import pandas as pd

from modules.data_model import LABEL_SEED, LABEL_USER, SOURCE_SEED
from modules.places import canon_columns

HOTSPOT_COLUMNS = ["city", "state", "country", "lat", "lon", "incoming", "outgoing",
                   "n_shipments", "carriers", "labels"]


def compute_hotspots(df: pd.DataFrame) -> pd.DataFrame:
    """One row per city. A segment is one hop between consecutive stops of a shipment:
    it counts as outgoing for the city it leaves and incoming for the city it reaches.
    Hops between stops in the same city are ignored."""
    if df.empty:
        return pd.DataFrame(columns=HOTSPOT_COLUMNS)
    d = canon_columns(df).sort_values(["shipment_id", "stop_order"])
    acc = {}
    for sid, g in d.groupby("shipment_id", sort=False):
        rows = list(g.itertuples())
        for r in rows:
            key = (r.r_city.casefold(), r.r_state.casefold(), r.r_country.casefold())
            h = acc.setdefault(key, {
                "city": r.r_city, "state": r.r_state, "country": r.r_country,
                "lat": r.lat, "lon": r.lon, "incoming": 0, "outgoing": 0,
                "ships": set(), "carriers": set(), "sources": set()})
            h["ships"].add(sid)
            h["carriers"].add(r.carrier)
            h["sources"].add(r.source)
        for a, b in zip(rows[:-1], rows[1:]):
            ka = (a.r_city.casefold(), a.r_state.casefold(), a.r_country.casefold())
            kb = (b.r_city.casefold(), b.r_state.casefold(), b.r_country.casefold())
            if ka != kb:
                acc[ka]["outgoing"] += 1
                acc[kb]["incoming"] += 1
    out = []
    for h in acc.values():
        labels = sorted({LABEL_SEED if s == SOURCE_SEED else LABEL_USER for s in h["sources"]})
        out.append({
            "city": h["city"], "state": h["state"], "country": h["country"],
            "lat": h["lat"], "lon": h["lon"],
            "incoming": h["incoming"], "outgoing": h["outgoing"],
            "n_shipments": len(h["ships"]),
            "carriers": ", ".join(sorted(h["carriers"])),
            "labels": " + ".join(labels),
        })
    res = pd.DataFrame(out, columns=HOTSPOT_COLUMNS)
    return res.sort_values(["incoming", "outgoing"], ascending=False).reset_index(drop=True)
