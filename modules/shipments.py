"""Submit, delete-by-code and admin actions. No Streamlit dependency.

Ties validation, security and the sheet store together.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence

import pandas as pd

from modules import security, validation
from modules.checkpoints import generate_shipment_id, stops_to_frame, validate_route
from modules.sheets_store import SheetStore, StoreError

APPROVAL_MODES = ("immediate", "manual")


class SubmissionError(Exception):
    def __init__(self, errors: List[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass
class SubmitResult:
    shipment_id: str
    delete_code: str
    status: str
    frame: pd.DataFrame


def parse_approval_mode(value) -> str:
    """Anything unrecognised becomes 'manual', so a typo can never publish unreviewed data."""
    v = str(value or "").strip().lower()
    return v if v in APPROVAL_MODES else "manual"


def status_for_new(mode: str) -> str:
    return "approved" if parse_approval_mode(mode) == "immediate" else "pending"


def validate_submission(stops: Sequence[dict], carrier: str, product_class: str, honeypot: str,
                        recent_submissions: Sequence[float], now_ts: float,
                        now_dt: Optional[datetime] = None) -> None:
    """Honeypot, rate limit, route rules and plausible durations. Raises SubmissionError."""
    if validation.honeypot_tripped(honeypot):
        raise SubmissionError(["Submission rejected."])
    limited = validation.rate_limit_error(recent_submissions, now_ts)
    if limited:
        raise SubmissionError([limited])
    errors = validate_route(list(stops), carrier, product_class) + validation.validate_durations(stops, now_dt)
    if errors:
        raise SubmissionError(errors)


def submit_shipment(store: SheetStore, stops: Sequence[dict], carrier: str, product_class: str,
                    approval_mode: str, honeypot: str, recent_submissions: Sequence[float],
                    now_ts: float, now_dt: Optional[datetime] = None) -> SubmitResult:
    """Validate everything, then write one shipment in a single append. Raises SubmissionError."""
    validate_submission(stops, carrier, product_class, honeypot, recent_submissions, now_ts, now_dt)

    fp = validation.fingerprint(carrier, product_class, stops)
    existing = store.load_all()   # fresh read, so a double click is caught
    live = existing[existing["status"] != "deleted"]
    if validation.is_duplicate(fp, live["fingerprint"].astype(str)):
        raise SubmissionError(["This exact route has already been submitted."])

    taken = set(existing["shipment_id"])
    sid = generate_shipment_id()
    while sid in taken:
        sid = generate_shipment_id()
    code = security.new_delete_code()
    status = status_for_new(approval_mode)
    frame = stops_to_frame(list(stops), carrier, product_class, sid, status=status)
    store.append_shipment(frame, security.hash_code(code), fp)
    return SubmitResult(sid, code, status, frame)


def delete_with_code(store: SheetStore, shipment_id: str, code: str) -> str:
    """Return 'deleted', 'already_deleted' or 'invalid'. The same 'invalid' covers an unknown ID."""
    sid = (shipment_id or "").strip().upper()
    df = store.load_all()
    rows = df[df["shipment_id"] == sid]
    if rows.empty or rows["source"].iloc[0] != "user":
        return "invalid"
    stored = next((h for h in rows["delete_code_hash"] if h), "")
    if not security.verify_code(code, stored):
        return "invalid"
    if (rows["status"] == "deleted").all():
        return "already_deleted"
    store.set_status(sid, "deleted")
    return "deleted"


def admin_set_status(store: SheetStore, shipment_id: str, status: str) -> int:
    """Owner action: approve, delete or restore (restore = approved). Rows are never erased."""
    return store.set_status(shipment_id, status)
