"""Canonical place names so 'TX', 'tx' and 'Texas' (or 'USA' and 'United States')
group together in drill-down and hotspots. No Streamlit dependency."""
from modules.geocoding import _norm_country

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
_US_BY_NAME = {v.casefold(): v for v in US_STATES.values()}


def _tidy(text: str) -> str:
    t = (text or "").strip()
    return t.title() if t and (t == t.lower() or t == t.upper()) else t


def canon_country(text: str) -> str:
    n = _norm_country(text)
    return n.title() if n else ""


def canon_state(country: str, state: str) -> str:
    s = (state or "").strip()
    if canon_country(country) == "United States":
        key = s.upper().replace(".", "")
        if key in US_STATES:
            return US_STATES[key]
        if s.casefold() in _US_BY_NAME:
            return _US_BY_NAME[s.casefold()]
    return _tidy(s)


def canon_city(text: str) -> str:
    return _tidy(text)


def canon_columns(df):
    """Return a copy of df with canonical r_country / r_state / r_city columns."""
    out = df.copy()
    out["r_country"] = [canon_country(c) for c in out["country"]]
    out["r_state"] = [canon_state(c, s) for c, s in zip(out["country"], out["state"])]
    out["r_city"] = [canon_city(c) for c in out["city"]]
    return out
