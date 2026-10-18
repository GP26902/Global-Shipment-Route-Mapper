"""Submission-level validation beyond the per-stop checks in checkpoints.py.

Plausible durations, duplicate fingerprint, honeypot and rate limit. No Streamlit dependency.
"""
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Sequence

MAX_TOTAL_DAYS = 120
MAX_LEG_DAYS = 60
FUTURE_TOLERANCE_DAYS = 2      # times are local to each facility, so allow a little slack
RATE_LIMIT_COUNT = 3
RATE_WINDOW_SECONDS = 3600


def _timeline(stops: Sequence[dict]) -> List[tuple]:
    """(label, datetime) for every filled-in time, in route order."""
    out = []
    for i, s in enumerate(stops, start=1):
        for field in ("arrived", "departed"):
            if s.get(field) is not None:
                out.append((f"stop {i} {field}", s[field]))
    return out


def validate_durations(stops: Sequence[dict], now: Optional[datetime] = None) -> List[str]:
    """Plausibility checks on the times given. Chronological order is checked in checkpoints.py."""
    errors: List[str] = []
    points = _timeline(stops)
    if not points:
        return errors
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    limit = now + timedelta(days=FUTURE_TOLERANCE_DAYS)
    for label, t in points:
        if t > limit:
            errors.append(f"The {label} time is in the future.")
    for (la, ta), (lb, tb) in zip(points, points[1:]):
        if tb >= ta and tb - ta > timedelta(days=MAX_LEG_DAYS):
            errors.append(f"{lb} is more than {MAX_LEG_DAYS} days after {la}. Please check the dates.")
    if len(points) >= 2:
        span = points[-1][1] - points[0][1]
        if span > timedelta(days=MAX_TOTAL_DAYS):
            errors.append(f"Total transit time is over {MAX_TOTAL_DAYS} days. Please check the dates.")
    return errors


def fingerprint(carrier: str, product_class: str, stops: Sequence[dict]) -> str:
    """Stable hash of the route content, used to spot an accidental double submission."""
    parts = [carrier, product_class]
    for s in stops:
        parts.append("|".join([
            str(s["stage_type"]), str(s["city"]).lower(), str(s["country"]).lower(),
            s["arrived"].isoformat() if s.get("arrived") else "",
            s["departed"].isoformat() if s.get("departed") else "",
        ]))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:20]


def is_duplicate(fp: str, existing_fingerprints: Iterable[str]) -> bool:
    return fp in set(existing_fingerprints)


def honeypot_tripped(value: str) -> bool:
    """The honeypot field is hidden from people. Anything typed into it means a bot."""
    return bool((value or "").strip())


def rate_limit_error(timestamps: Sequence[float], now: float,
                     limit: int = RATE_LIMIT_COUNT, window: int = RATE_WINDOW_SECONDS) -> Optional[str]:
    recent = [t for t in timestamps if now - t < window]
    if len(recent) >= limit:
        wait_min = max(1, int((window - (now - min(recent))) // 60) + 1)
        return (f"Limit of {limit} submissions per hour reached for this session. "
                f"Please try again in about {wait_min} minutes.")
    return None


def prune_timestamps(timestamps: Sequence[float], now: float, window: int = RATE_WINDOW_SECONDS) -> List[float]:
    return [t for t in timestamps if now - t < window]
