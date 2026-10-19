"""Parsing and checking of one stop-entry row. No Streamlit dependency.

A row has: stage, country, state, a "City or ZIP" box, and arrival and departure dates.
Dates only: the time of day is not collected, so each date is stored as midnight.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Dict, List, Optional, Tuple

from modules.checkpoints import validate_stop_input

_DIGIT = re.compile(r"\d")


def split_city_zip(text: Optional[str]) -> Tuple[str, str]:
    """'Stafford 77477' or 'Stafford, 77477' -> ('Stafford', '77477'). 'Washington, DC' stays a city."""
    t = " ".join((text or "").split())
    if not t:
        return "", ""
    if _DIGIT.search(t) and not re.search(r"[A-Za-z]", t):
        return "", t                                                             # a code on its own
    if "," in t:
        head, _, tail = t.rpartition(",")
        tail = tail.strip()
        if tail and _DIGIT.search(tail) and len(tail) <= 12:
            return head.strip(" ,"), tail
        return t, ""
    parts = t.split(" ")
    if len(parts) >= 2:
        last, prev = parts[-1], parts[-2]
        if _DIGIT.search(last):
            if len(parts) >= 3 and len(prev) <= 4 and _DIGIT.search(prev):      # SW1A 1AA, K1A 0B1
                return " ".join(parts[:-2]), f"{prev} {last}"
            return " ".join(parts[:-1]), last
        if len(parts) >= 3 and prev.isdigit() and 3 <= len(prev) <= 4 and last.isalpha() and len(last) <= 3:
            return " ".join(parts[:-2]), f"{prev} {last}"                        # 1012 AB
    return t, ""


def row_is_blank(country: str, state: str, city_zip: str,
                 arrival: Optional[date], departure: Optional[date]) -> bool:
    """The stage box always has a value, so it is ignored when deciding if a row is empty."""
    return (arrival is None and departure is None
            and not any((x or "").strip() for x in (country, state, city_zip)))


@dataclass
class RowResult:
    errors: List[str] = field(default_factory=list)
    values: Optional[Dict[str, object]] = None   # stage, city, state, country, postal, arrived, departed


def _midnight(d: Optional[date]) -> Optional[datetime]:
    return datetime.combine(d, time.min) if d else None


def read_row(stage: str, country: str, state: str, city_zip: str,
             arrival: Optional[date], departure: Optional[date]) -> RowResult:
    """Parse and validate one row. Does not geocode."""
    errors: List[str] = []
    city, postal = split_city_zip(city_zip)
    if not city and postal:
        errors.append("Type the city as well as the ZIP / postal code. A code on its own is not enough.")
    arrived, departed = _midnight(arrival), _midnight(departure)
    errors += [e for e in validate_stop_input(stage or "", "", city, state or "", country or "", postal,
                                              arrived, departed)
               if not (not city and postal and e == "City is required.")]
    if errors:
        return RowResult(errors=errors)
    return RowResult(values={"stage": stage, "city": city, "state": state or "", "country": country,
                             "postal": postal, "arrived": arrived, "departed": departed})
