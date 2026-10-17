import pytest

from modules.geocoding import GeocodingUnavailable, Geocoder, build_fallback
from modules.seed import CITIES

UA = "TestAgent/1.0 (tests)"


class FakeLookup:
    def __init__(self, results=None, raises=False):
        self.results, self.raises, self.queries = results or {}, raises, []

    def __call__(self, q):
        self.queries.append(dict(q))
        if self.raises:
            raise RuntimeError("network down")
        return self.results.get(("postalcode" in q), None)


def make(lookup, fallback=None, **kw):
    t = {"now": 0.0, "slept": []}

    def clock():
        return t["now"]

    def sleep(s):
        t["slept"].append(s)
        t["now"] += s

    g = Geocoder(UA, fallback=fallback, lookup=lookup, clock=clock, sleep=sleep, **kw)
    return g, t


def test_requires_user_agent():
    with pytest.raises(ValueError):
        Geocoder("  ")


def test_hub_with_postal_uses_postal_query_and_precision():
    fake = FakeLookup({True: (35.14912, -90.04898, "38103, Memphis, TN, United States")})
    g, _ = make(fake)
    r = g.geocode("Sorting Hub", "Memphis", "TN", "United States", "38103")
    assert r.ok and r.precision == "postal" and r.source == "nominatim"
    assert fake.queries[0]["postalcode"] == "38103"
    assert (r.lat, r.lon) == (35.149, -90.049)


def test_last_mile_and_destination_never_send_postal_code():
    fake = FakeLookup({False: (35.1495, -90.049, "Memphis, TN, United States")})
    g, _ = make(fake)
    for stage in ("Last-Mile Facility", "Final Destination"):
        r = g.geocode(stage, "Memphis", "TN", "United States", "38103")
        assert r.ok and r.precision == "city"
    assert all("postalcode" not in q for q in fake.queries)


def test_city_level_rounding_is_about_one_km():
    fake = FakeLookup({False: (35.149534, -90.048981, "Memphis")})
    g, _ = make(fake)
    r = g.geocode("Final Destination", "Memphis", "TN", "United States")
    assert (r.lat, r.lon) == (35.15, -90.05)


def test_bad_postal_falls_back_to_city_query():
    fake = FakeLookup({True: None, False: (35.1495, -90.049, "Memphis")})
    g, _ = make(fake)
    r = g.geocode("Sorting Hub", "Memphis", "TN", "United States", "00000")
    assert r.ok and r.precision == "city" and len(fake.queries) == 2


def test_results_are_cached_case_insensitively():
    fake = FakeLookup({False: (1.0, 2.0, "X")})
    g, _ = make(fake)
    g.geocode("Origin", "Memphis", "TN", "United States")
    g.geocode("Origin", "  memphis ", "tn", "UNITED STATES")
    assert g.network_calls == 1


def test_not_found_is_cached_but_errors_are_not():
    fake = FakeLookup({False: None})
    g, _ = make(fake)
    assert not g.geocode("Origin", "Nowhereville", "", "Atlantis").ok
    g.geocode("Origin", "Nowhereville", "", "Atlantis")
    assert g.network_calls == 1

    down = FakeLookup(raises=True)
    g2, _ = make(down)
    r = g2.geocode("Origin", "Memphis", "TN", "United States")
    assert not r.ok and "could not be reached" in r.error
    g2.geocode("Origin", "Memphis", "TN", "United States")
    assert g2.network_calls == 2  # retried, not cached


def test_outage_falls_back_to_builtin_city_list():
    g, _ = make(FakeLookup(raises=True), fallback=build_fallback(CITIES.values()))
    r = g.geocode("Origin", "Houston", "TX", "USA")  # alias for United States
    assert r.ok and r.source == "built-in" and r.precision == "city"
    assert (r.lat, r.lon) == (29.76, -95.37)


def test_fallback_needs_exact_city_and_country_match():
    g, _ = make(FakeLookup(raises=True), fallback=build_fallback(CITIES.values()))
    assert not g.geocode("Origin", "Houston", "", "Germany").ok


def test_accents_and_spacing_normalised_for_fallback():
    g, _ = make(FakeLookup(raises=True), fallback=build_fallback(CITIES.values()))
    assert g.geocode("Origin", "  Ile  ", "", "France").ok is False
    assert g.geocode("Origin", "Paris", "", "france").ok


def test_missing_city_or_country_is_rejected_without_network():
    fake = FakeLookup()
    g, _ = make(fake)
    assert not g.geocode("Origin", "", "TX", "United States").ok
    assert not g.geocode("Origin", "Houston", "TX", " ").ok
    assert fake.queries == []


def test_rate_limit_spaces_network_calls():
    fake = FakeLookup({False: (1.0, 2.0, "X")})
    g, t = make(fake, min_interval=1.1)
    g.geocode("Origin", "A", "", "X")
    g.geocode("Origin", "B", "", "X")
    g.geocode("Origin", "C", "", "X")
    assert len(t["slept"]) == 2 and all(abs(s - 1.1) < 1e-9 for s in t["slept"])


def test_unavailable_exception_type_exists():
    assert issubclass(GeocodingUnavailable, Exception)
