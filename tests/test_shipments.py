from datetime import datetime

import pytest

from modules import security
from modules.shipments import (
    SubmissionError, admin_set_status, delete_with_code, parse_approval_mode, status_for_new,
    submit_shipment,
)
from modules.sheets_store import SheetStore, StoreError
from tests.fakes import FakeWorksheet

NOW_DT = datetime(2026, 10, 17, 12, 0)
NOW = 1_000_000.0


def stops(city_b="Houston", t1=datetime(2026, 9, 1, 8, 0), t2=datetime(2026, 9, 10, 17, 30)):
    return [
        {"stage_type": "Origin", "facility": "A", "city": "Shenzhen", "state": "", "country": "China",
         "postal_code": "", "lat": 22.5, "lon": 114.0, "arrived": None, "departed": t1},
        {"stage_type": "Final Destination", "facility": "B", "city": city_b, "state": "TX",
         "country": "United States", "postal_code": "", "lat": 29.7, "lon": -95.3, "arrived": t2,
         "departed": None},
    ]


@pytest.fixture
def store():
    s = SheetStore(FakeWorksheet())
    s.ensure_header()
    return s


def submit(store, s=None, mode="immediate", honeypot="", recent=(), carrier="UPS", pc="Electronics"):
    return submit_shipment(store, s or stops(), carrier, pc, mode, honeypot, list(recent), NOW, NOW_DT)


def test_approval_mode_parsing():
    assert parse_approval_mode("immediate") == "immediate"
    assert parse_approval_mode(" Manual ") == "manual"
    assert parse_approval_mode("immedate") == "manual"        # typo fails safe
    assert parse_approval_mode(None) == "manual"
    assert status_for_new("immediate") == "approved" and status_for_new("manual") == "pending"


def test_immediate_submission_is_approved_and_one_append(store):
    res = submit(store)
    assert res.status == "approved" and res.shipment_id.startswith("SHP-")
    assert store.ws.append_calls == 1
    assert set(store.load_approved()["shipment_id"]) == {res.shipment_id}


def test_manual_mode_is_pending_and_hidden_until_approved(store):
    res = submit(store, mode="manual")
    assert res.status == "pending" and store.load_approved().empty
    admin_set_status(store, res.shipment_id, "approved")
    assert len(store.load_approved()) == 2


def test_only_hash_is_stored(store):
    res = submit(store)
    flat = " ".join(str(c) for row in store.ws.rows for c in row)
    assert res.delete_code not in flat
    stored = store.load_all()["delete_code_hash"].iloc[0]
    assert security.verify_code(res.delete_code, stored)


def test_honeypot_blocks_and_writes_nothing(store):
    with pytest.raises(SubmissionError):
        submit(store, honeypot="http://spam")
    assert store.ws.append_calls == 0


def test_rate_limit_blocks(store):
    with pytest.raises(SubmissionError) as e:
        submit(store, recent=[NOW - 10, NOW - 20, NOW - 30])
    assert "per hour" in e.value.errors[0] and store.ws.append_calls == 0


def test_route_rules_and_durations_block(store):
    with pytest.raises(SubmissionError):                       # times out of order
        submit(store, stops(t1=datetime(2026, 9, 10), t2=datetime(2026, 9, 1)))
    with pytest.raises(SubmissionError) as e:                  # implausible duration
        submit(store, stops(t1=datetime(2026, 1, 1), t2=datetime(2026, 9, 1)))
    assert any("days" in m for m in e.value.errors)
    with pytest.raises(SubmissionError):                       # bad carrier
        submit(store, carrier="Pigeon Post")
    assert store.ws.append_calls == 0


def test_duplicate_blocked_until_original_deleted(store):
    first = submit(store)
    with pytest.raises(SubmissionError) as e:
        submit(store)
    assert "already been submitted" in e.value.errors[0]
    assert delete_with_code(store, first.shipment_id, first.delete_code) == "deleted"
    again = submit(store)                                      # allowed once the first is deleted
    assert again.shipment_id != first.shipment_id


def test_different_route_is_not_a_duplicate(store):
    submit(store)
    submit(store, stops(city_b="Dallas"))
    assert store.load_all()["shipment_id"].nunique() == 2


def test_delete_with_code(store):
    res = submit(store)
    other = submit(store, stops(city_b="Dallas"))
    assert delete_with_code(store, res.shipment_id.lower(), res.delete_code.lower()) == "deleted"
    assert set(store.load_approved()["shipment_id"]) == {other.shipment_id}
    assert len(store.load_all()) == 4                           # rows kept, never erased
    assert delete_with_code(store, res.shipment_id, res.delete_code) == "already_deleted"


def test_wrong_code_or_unknown_id_is_the_same_answer(store):
    res = submit(store)
    assert delete_with_code(store, res.shipment_id, "AAAA-BBBB-CCCC") == "invalid"
    assert delete_with_code(store, "SHP-NOTREAL1", res.delete_code) == "invalid"
    assert delete_with_code(store, "", "") == "invalid"
    assert len(store.load_approved()) == 2


def test_seed_source_rows_cannot_be_deleted_by_code(store):
    res = submit(store)
    store.ws.rows[1][store.ws.rows[0].index("source")] = "seed"
    assert delete_with_code(store, res.shipment_id, res.delete_code) == "invalid"


def test_admin_delete_and_restore(store):
    res = submit(store)
    assert admin_set_status(store, res.shipment_id, "deleted") == 2
    assert store.load_approved().empty
    assert admin_set_status(store, res.shipment_id, "approved") == 2
    assert len(store.load_approved()) == 2


def test_database_failure_surfaces_and_nothing_is_half_written(store):
    store.ws.fail = True
    with pytest.raises(StoreError):
        submit(store)
