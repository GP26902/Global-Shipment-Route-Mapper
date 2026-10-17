"""Drill-down (World > Country > State > City): options, filtering and map view.
No Streamlit dependency."""
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pandas as pd

from modules.hotspots import compute_hotspots
from modules.places import canon_columns
from modules.routes import great_circle_km

WORLD_LON: Tuple[float, float] = (-180.0, 180.0)
WORLD_LAT: Tuple[float, float] = (-60.0, 85.0)
NEIGHBOUR_KM = 800.0   # city view also frames connected stops this close
MIN_SPAN_DEG = 4.0


@dataclass(frozen=True)
class Drilldown:
    level: str                       # World, Country, State or City
    label: str
    routes: pd.DataFrame
    hotspots: pd.DataFrame
    lon_range: Tuple[float, float]
    lat_range: Tuple[float, float]


def country_options(df: pd.DataFrame) -> List[str]:
    return sorted({c for c in canon_columns(df)["r_country"] if c}) if len(df) else []


def state_options(df: pd.DataFrame, country: str) -> List[str]:
    if df.empty or not country:
        return []
    d = canon_columns(df)
    return sorted({s for s in d.loc[d["r_country"] == country, "r_state"] if s})


def city_options(df: pd.DataFrame, country: str, state: Optional[str] = None) -> List[str]:
    if df.empty or not country:
        return []
    d = canon_columns(df)
    m = d["r_country"] == country
    if state:
        m &= d["r_state"] == state
    return sorted({c for c in d.loc[m, "r_city"] if c})


def _mask(d: pd.DataFrame, country, state, city) -> pd.Series:
    m = pd.Series(True, index=d.index)
    if country:
        m &= d["r_country"] == country
    if state:
        m &= d["r_state"] == state
    if city:
        m &= d["r_city"] == city
    return m


def _view_points(d: pd.DataFrame, in_region: pd.Series, city: Optional[str]) -> List[Tuple[float, float]]:
    pts = [(r.lat, r.lon) for r in d[in_region].itertuples()]
    if not city:
        return pts
    # City view: also frame directly connected stops that are nearby.
    for _, g in d.sort_values(["shipment_id", "stop_order"]).groupby("shipment_id", sort=False):
        rows = list(g.itertuples())
        for i, r in enumerate(rows):
            if not in_region.loc[r.Index]:
                continue
            for j in (i - 1, i + 1):
                if 0 <= j < len(rows):
                    n = rows[j]
                    if great_circle_km(r.lat, r.lon, n.lat, n.lon) <= NEIGHBOUR_KM:
                        pts.append((n.lat, n.lon))
    return pts


def _bounds(pts: List[Tuple[float, float]]):
    lats, lons = [p[0] for p in pts], [p[1] for p in pts]

    def axis(lo, hi, limit):
        span = max(hi - lo, MIN_SPAN_DEG)
        pad = max(span * 0.25, 1.0)
        mid = (lo + hi) / 2
        a, b = mid - span / 2 - pad, mid + span / 2 + pad
        return (max(a, -limit), min(b, limit))

    return axis(min(lons), max(lons), 180.0), axis(min(lats), max(lats), 90.0)


def apply_drilldown(df: pd.DataFrame, country: Optional[str] = None,
                    state: Optional[str] = None, city: Optional[str] = None) -> Drilldown:
    """Routes touching the chosen area, hotspots inside it, and the map frame."""
    level = "City" if city else "State" if state else "Country" if country else "World"
    label = ", ".join(x for x in (city, state, country) if x) or "World"
    if df.empty:
        return Drilldown(level, label, df, compute_hotspots(df), WORLD_LON, WORLD_LAT)
    d = canon_columns(df).reset_index(drop=True)
    in_region = _mask(d, country, state, city)
    ids = set(d.loc[in_region, "shipment_id"])
    routes = df.reset_index(drop=True)[d["shipment_id"].isin(ids)].reset_index(drop=True)

    hs = compute_hotspots(routes)
    if level != "World":
        keep = [(not country or c == country) and (not state or s == state) and (not city or ci == city)
                for ci, s, c in zip(hs["city"], hs["state"], hs["country"])]
        hs = hs[keep].reset_index(drop=True)

    if level == "World" or not ids:
        return Drilldown(level, label, routes, hs, WORLD_LON, WORLD_LAT)
    sub = d[d["shipment_id"].isin(ids)].reset_index(drop=True)
    lon, lat = _bounds(_view_points(sub, _mask(sub, country, state, city), city))
    return Drilldown(level, label, routes, hs, lon, lat)
