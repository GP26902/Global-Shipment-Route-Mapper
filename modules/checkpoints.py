"""Checkpoint builder logic: build, validate and convert stops. No Streamlit dependency."""
import re
import uuid
from datetime import date, datetime, time
from typing import Dict, List, Optional

import pandas as pd

from modules.data_model import (
    CARRIERS, COLUMNS, PRODUCT_CLASSES, SOURCE_USER, STAGE_TYPES, STATUSES,
)
from modules.geocoding import CITY_LEVEL_STAGES, GeoResult

Stop = Dict[str, object]

MAX_STOPS = 15
MAX_LEN = {"facility": 80, "city": 60, "state": 60, "country": 60, "postal_code": 12}

_STREET_RE = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9.' -]{0,40}?\b"
    r"(street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|court|ct|highway|hwy|way|place|pl)\b",
    re.IGNORECASE,
)
_POSTAL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 \-]{0,10}[A-Za-z0-9]$")


def generate_shipment_id() -> str:
    return "SHP-" + uuid.uuid4().hex[:8].upper()


def combine_dt(d: Optional[date], t: Optional[time]) -> Optional[datetime]:
    """Both given -> datetime; neither -> None; only one -> ValueError."""
    if d is None and t is None:
        return None
    if d is None or t is None:
        raise ValueError("Enter both a date and a time, or leave both empty.")
    return datetime.combine(d, t)


def validate_stop_input(stage: str, facility: str, city: str, state: str, country: str,
                        postal: str, arrived: Optional[datetime],
                        departed: Optional[datetime]) -> List[str]:
    errors: List[str] = []
    if stage not in STAGE_TYPES:
        errors.append("Choose a valid stage type.")
    if not city.strip():
        errors.append("City is required.")
    if not country.strip():
        errors.append("Country is required.")
    for name, value in (("facility", facility), ("city", city), ("state", state),
                        ("country", country), ("postal_code", postal)):
        if len(value.strip()) > MAX_LEN[name]:
            errors.append(f"{name.replace('_', ' ').capitalize()} must be at most {MAX_LEN[name]} characters.")
    for label, value in (("Facility name", facility), ("City", city)):
        if _STREET_RE.search(value):
            errors.append(f"{label} looks like a street address. Street addresses are not collected: "
                          "use a facility name or city only.")
    if postal.strip() and not _POSTAL_RE.match(postal.strip()):
        errors.append("Postal / PIN code may only contain letters, digits, spaces and hyphens.")
    if arrived and departed and departed < arrived:
        errors.append("Departed time must not be before arrived time.")
    return errors


def make_stop(stage: str, facility: str, city: str, state: str, country: str,
              postal: str, arrived: Optional[datetime], departed: Optional[datetime],
              geo: GeoResult) -> Stop:
    city, state, country = city.strip(), state.strip(), country.strip()
    return {
        "stage_type": stage,
        "facility": facility.strip() or f"{city} {stage}",
        "city": city, "state": state, "country": country,
        # Last-mile and destination stops never keep a postal code (city level only).
        "postal_code": "" if stage in CITY_LEVEL_STAGES else postal.strip(),
        "lat": geo.lat, "lon": geo.lon,
        "arrived": arrived, "departed": departed,
        "geo_source": geo.source, "precision": geo.precision,
    }


def delete_stop(stops: List[Stop], index: int) -> List[Stop]:
    if not 0 <= index < len(stops):
        return list(stops)
    return stops[:index] + stops[index + 1:]


def validate_route(stops: List[Stop], carrier: str, product_class: str) -> List[str]:
    errors: List[str] = []
    if carrier not in CARRIERS:
        errors.append("Choose a carrier.")
    if product_class not in PRODUCT_CLASSES:
        errors.append("Choose a product class.")
    if len(stops) < 2:
        errors.append("Add at least two stops (an Origin and a Final Destination).")
        return errors
    if len(stops) > MAX_STOPS:
        errors.append(f"A route can have at most {MAX_STOPS} stops.")
    if stops[0]["stage_type"] != "Origin":
        errors.append("The first stop must be the Origin.")
    if stops[-1]["stage_type"] != "Final Destination":
        errors.append("The last stop must be the Final Destination.")
    for i, s in enumerate(stops[1:-1], start=2):
        if s["stage_type"] in ("Origin", "Final Destination"):
            errors.append(f"Stop {i} is a {s['stage_type']}: only the first and last stop can be.")
    if any(s.get("lat") is None or s.get("lon") is None for s in stops):
        errors.append("Every stop needs a resolved location.")

    last_time, last_label = None, ""
    for i, s in enumerate(stops, start=1):
        for field in ("arrived", "departed"):
            t = s.get(field)
            if t is None:
                continue
            label = f"stop {i} {field}"
            if last_time is not None and t < last_time:
                errors.append(f"Times are out of order: {label} is before {last_label}.")
            last_time, last_label = t, label
    return errors


def stops_to_frame(stops: List[Stop], carrier: str, product_class: str,
                   shipment_id: str, status: str, source: str = SOURCE_USER) -> pd.DataFrame:
    """One row per checkpoint, ready for a single append."""
    assert status in STATUSES, status
    created = pd.Timestamp.now(tz="UTC").tz_localize(None)
    rows = []
    for order, s in enumerate(stops, start=1):
        rows.append({
            "shipment_id": shipment_id, "stop_order": order,
            "stage_type": s["stage_type"], "facility": s["facility"],
            "city": s["city"], "state": s["state"], "country": s["country"],
            "postal_code": s["postal_code"], "lat": s["lat"], "lon": s["lon"],
            "arrived": pd.Timestamp(s["arrived"]) if s["arrived"] else pd.NaT,
            "departed": pd.Timestamp(s["departed"]) if s["departed"] else pd.NaT,
            "carrier": carrier, "product_class": product_class,
            "status": status, "source": source, "created_at": created,
        })
    return pd.DataFrame(rows, columns=COLUMNS)
