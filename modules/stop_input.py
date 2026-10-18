"""Parsing and checking of one stop-entry row. No Streamlit dependency.

A row has: stage, country, state, a "City or ZIP" box, and two single date-and-time boxes.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from modules.checkpoints import validate_stop_input

_AMPM = r"(?:\s*([AaPp])\.?\s*[Mm]\.?)?"
_ISO = re.compile(rf"^(\d{{4}})-(\d{{1,2}})-(\d{{1,2}})[ T]\s*(\d{{1,2}}):(\d{{2}})(?::\d{{2}})?{_AMPM}$")
_US = re.compile(rf"^(\d{{1,2}})/(\d{{1,2}})/(\d{{2}}|\d{{4}})[ ,]+\s*(\d{{1,2}}):(\d{{2}})(?::\d{{2}})?{_AMPM}$")
_DATE_ONLY = re.compile(r"^(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4})$")
_HELP = "Use MM/DD/YYYY HH:MM, for example 09/12/2026 3:01 AM or 09/12/2026 15:10."
_DIGIT = re.compile(r"\d")


def parse_datetime_text(text: Optional[str]) -> Optional[datetime]:
    """Blank -> None. Accepts MM/DD/YYYY (US order) or YYYY-MM-DD, 12 or 24-hour time, A.M./P.M."""
    t = " ".join((text or "").split())
    if not t:
        return None
    if _DATE_ONLY.match(t):
        raise ValueError(f"'{t}' has a date but no time. Add a time, or leave the box empty. {_HELP}")
    m = _ISO.match(t)
    if m:
        y, mo, d, h, mi, ap = int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), m[6]
    else:
        m = _US.match(t)
        if not m:
            raise ValueError(f"Could not read '{t}'. {_HELP}")
        mo, d, y, h, mi, ap = int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), m[6]
        if y < 100:
            y += 2000
    if ap:
        if not 1 <= h <= 12:
            raise ValueError(f"'{t}': with AM/PM the hour must be 1 to 12.")
        h = h % 12 + (12 if ap.lower() == "p" else 0)
    elif h > 23:
        raise ValueError(f"'{t}': the hour must be 0 to 23. {_HELP}")
    if mi > 59:
        raise ValueError(f"'{t}': minutes must be 0 to 59.")
    try:
        return datetime(y, mo, d, h, mi)
    except ValueError:
        raise ValueError(f"'{t}' is not a real date. {_HELP}") from None


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


def row_is_blank(country: str, state: str, city_zip: str, arrival: str, departure: str) -> bool:
    """The stage box always has a value, so it is ignored when deciding if a row is empty."""
    return not any((x or "").strip() for x in (country, state, city_zip, arrival, departure))


@dataclass
class RowResult:
    errors: List[str] = field(default_factory=list)
    values: Optional[Dict[str, object]] = None   # stage, city, state, country, postal, arrived, departed


def read_row(stage: str, country: str, state: str, city_zip: str,
             arrival_text: str, departure_text: str) -> RowResult:
    """Parse and validate one row. Does not geocode."""
    errors: List[str] = []
    city, postal = split_city_zip(city_zip)
    if not city and postal:
        errors.append("Type the city as well as the ZIP / postal code. A code on its own is not enough.")
    arrived = departed = None
    try:
        arrived = parse_datetime_text(arrival_text)
    except ValueError as exc:
        errors.append(f"Arrival: {exc}")
    try:
        departed = parse_datetime_text(departure_text)
    except ValueError as exc:
        errors.append(f"Departure: {exc}")
    errors += [e for e in validate_stop_input(stage or "", "", city, state or "", country or "", postal,
                                              arrived, departed)
               if not (not city and postal and e == "City is required.")]
    if errors:
        return RowResult(errors=errors)
    return RowResult(values={"stage": stage, "city": city, "state": state or "", "country": country,
                             "postal": postal, "arrived": arrived, "departed": departed})
