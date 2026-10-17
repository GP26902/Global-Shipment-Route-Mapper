"""Nominatim geocoding with cache, rate limit and offline fallback.

No Streamlit dependency. Network access is injected (lookup=) so tests never
touch the network. Nominatim policy: custom user agent, max ~1 request/second.
"""
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional, Tuple

# Last-mile and destination stops are always resolved and plotted at city level.
CITY_LEVEL_STAGES = ("Last-Mile Facility", "Final Destination")

_COUNTRY_ALIASES = {
    "usa": "united states", "us": "united states", "america": "united states",
    "united states of america": "united states",
    "uk": "united kingdom", "great britain": "united kingdom", "britain": "united kingdom",
    "uae": "united arab emirates", "turkiye": "turkey",
}

Lookup = Callable[[Dict[str, str]], Optional[Tuple[float, float, str]]]


class GeocodingUnavailable(Exception):
    """The lookup service could not be reached (network error, timeout, blocked)."""


@dataclass(frozen=True)
class GeoResult:
    ok: bool
    lat: Optional[float] = None
    lon: Optional[float] = None
    display_name: str = ""
    source: str = ""      # "nominatim" or "built-in"
    precision: str = ""   # "postal" or "city"
    error: str = ""


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().casefold()


def _norm_country(text: str) -> str:
    n = _norm(text).replace(".", "")
    return _COUNTRY_ALIASES.get(n, n)


def build_fallback(cities: Iterable[tuple]) -> Dict[tuple, Tuple[float, float, str]]:
    """Offline lookup table from (city, state, country, lat, lon) tuples."""
    return {
        (_norm(c), _norm_country(co)): (lat, lon, f"{c}, {s}, {co}")
        for c, s, co, lat, lon in cities
    }


def _structured(city: str, state: str, country: str, postal: str = "") -> Dict[str, str]:
    q = {"city": city, "country": country}
    if state:
        q["state"] = state
    if postal:
        q["postalcode"] = postal
    return q


class Geocoder:
    def __init__(self, user_agent: str, fallback: Optional[dict] = None,
                 lookup: Optional[Lookup] = None, min_interval: float = 1.1,
                 timeout: float = 5.0, clock=time.monotonic, sleep=time.sleep):
        if not user_agent or not user_agent.strip():
            raise ValueError("Nominatim requires a custom user agent.")
        self.user_agent = user_agent
        self.fallback = fallback or {}
        self.min_interval = min_interval
        self.timeout = timeout
        self.cache: Dict[tuple, Optional[Tuple[float, float, str]]] = {}
        self.network_calls = 0
        self._lookup = lookup
        self._clock, self._sleep = clock, sleep
        self._last_call: Optional[float] = None
        self._lock = threading.Lock()

    def _default_lookup(self) -> Lookup:
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent=self.user_agent, timeout=self.timeout)

        def lookup(query):
            loc = geolocator.geocode(query, exactly_one=True)
            return None if loc is None else (loc.latitude, loc.longitude, loc.address)
        return lookup

    def _query(self, q: Dict[str, str]):
        """One rate-limited network call. Raises GeocodingUnavailable on any failure."""
        with self._lock:
            if self._lookup is None:
                self._lookup = self._default_lookup()
            if self._last_call is not None:
                wait = self.min_interval - (self._clock() - self._last_call)
                if wait > 0:
                    self._sleep(wait)
            try:
                self.network_calls += 1
                return self._lookup(q)
            except Exception as exc:  # network, timeout, blocked, bad response
                raise GeocodingUnavailable(str(exc)) from exc
            finally:
                self._last_call = self._clock()

    def _fallback(self, city: str, country: str) -> Optional[GeoResult]:
        hit = self.fallback.get((_norm(city), _norm_country(country)))
        if not hit:
            return None
        return GeoResult(True, round(hit[0], 2), round(hit[1], 2), hit[2], "built-in", "city")

    def geocode(self, stage: str, city: str, state: str, country: str,
                postal: str = "") -> GeoResult:
        city, state, country, postal = (s.strip() for s in (city, state, country, postal))
        if not city or not country:
            return GeoResult(False, error="City and country are required.")
        city_level = stage in CITY_LEVEL_STAGES
        attempts = []
        if postal and not city_level:  # postal codes never used below hub level
            attempts.append(_structured(city, state, country, postal))
        attempts.append(_structured(city, state, country))

        unavailable = False
        for q in attempts:
            key = tuple(sorted((k, _norm(v)) for k, v in q.items()))
            if key in self.cache:
                hit = self.cache[key]
            else:
                try:
                    hit = self._query(q)
                except GeocodingUnavailable:
                    unavailable = True  # not cached, so a retry can succeed
                    break
                self.cache[key] = hit
            if hit:
                precise = "postalcode" in q
                nd = 3 if precise else 2  # city-level points are rounded to ~1 km
                return GeoResult(True, round(hit[0], nd), round(hit[1], nd), hit[2],
                                 "nominatim", "postal" if precise else "city")

        fb = self._fallback(city, country)
        if fb:
            return fb
        if unavailable:
            return GeoResult(False, error="The location lookup service could not be reached. "
                                          "Please try again in a moment.")
        return GeoResult(False, error=f"No match found for {city}, {country}. "
                                      "Check the spelling or try without the postal code.")
