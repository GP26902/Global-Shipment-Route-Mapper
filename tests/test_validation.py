from datetime import datetime, timedelta

from modules import validation as v

NOW = datetime(2026, 10, 17, 12, 0)


def stop(arrived=None, departed=None, city="Memphis", stage="Sorting Hub"):
    return {"stage_type": stage, "city": city, "country": "United States",
            "arrived": arrived, "departed": departed}


def test_no_times_is_fine():
    assert v.validate_durations([stop(), stop()], NOW) == []


def test_normal_route_passes():
    t = NOW - timedelta(days=10)
    stops = [stop(departed=t), stop(arrived=t + timedelta(days=3), departed=t + timedelta(days=4)),
             stop(arrived=t + timedelta(days=7))]
    assert v.validate_durations(stops, NOW) == []


def test_future_time_rejected_but_small_slack_allowed():
    assert v.validate_durations([stop(departed=NOW + timedelta(days=1))], NOW) == []
    assert any("future" in e for e in v.validate_durations([stop(departed=NOW + timedelta(days=5))], NOW))


def test_leg_cap():
    t = NOW - timedelta(days=100)
    errs = v.validate_durations([stop(departed=t), stop(arrived=t + timedelta(days=61))], NOW)
    assert any("60 days" in e for e in errs)
    assert v.validate_durations([stop(departed=t), stop(arrived=t + timedelta(days=60))], NOW) == []


def test_total_cap():
    t = NOW - timedelta(days=200)
    stops = [stop(departed=t), stop(arrived=t + timedelta(days=50)), stop(arrived=t + timedelta(days=100)),
             stop(arrived=t + timedelta(days=121))]
    assert any("120 days" in e for e in v.validate_durations(stops, NOW))


def test_fingerprint_stable_and_sensitive():
    a = [stop(city="Memphis"), stop(city="Denver")]
    assert v.fingerprint("UPS", "Apparel", a) == v.fingerprint("UPS", "Apparel", [dict(s) for s in a])
    assert v.fingerprint("UPS", "Apparel", a) != v.fingerprint("FedEx", "Apparel", a)
    assert v.fingerprint("UPS", "Apparel", a) != v.fingerprint("UPS", "Apparel", [stop(city="Dallas"), stop(city="Denver")])
    assert v.is_duplicate("x", ["y", "x"]) and not v.is_duplicate("z", ["y", "x"])


def test_honeypot():
    assert not v.honeypot_tripped("") and not v.honeypot_tripped("   ")
    assert v.honeypot_tripped("http://spam")


def test_rate_limit():
    now = 10_000.0
    assert v.rate_limit_error([], now) is None
    assert v.rate_limit_error([now - 10, now - 20], now) is None
    assert "3 submissions per hour" in v.rate_limit_error([now - 10, now - 20, now - 30], now)
    assert v.rate_limit_error([now - 4000, now - 4001, now - 4002], now) is None   # old ones expired
    assert v.prune_timestamps([now - 10, now - 4000], now) == [now - 10]
