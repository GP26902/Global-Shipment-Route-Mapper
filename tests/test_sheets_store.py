import pandas as pd
import pytest

from modules.checkpoints import stops_to_frame
from modules.data_model import COLUMNS
from modules.sheets_store import SHEET_COLUMNS, SheetStore, StoreError, frame_to_rows, rows_to_frame
from tests.fakes import FakeWorksheet


def _stops():
    return [
        {"stage_type": "Origin", "facility": "Shenzhen Origin", "city": "Shenzhen", "state": "Guangdong",
         "country": "China", "postal_code": "518000", "lat": 22.5, "lon": 114.0,
         "arrived": None, "departed": pd.Timestamp("2026-09-01 08:00").to_pydatetime()},
        {"stage_type": "Final Destination", "facility": "Houston Final", "city": "Houston", "state": "TX",
         "country": "United States", "postal_code": "", "lat": 29.7, "lon": -95.3,
         "arrived": pd.Timestamp("2026-09-10 17:30").to_pydatetime(), "departed": None},
    ]


def _frame(sid="SHP-AAAA1111", status="approved"):
    return stops_to_frame(_stops(), "UPS", "Electronics", sid, status=status)


def _store(**kw):
    ws = FakeWorksheet(**kw)
    s = SheetStore(ws)
    s.ensure_header()
    return s, ws


def test_header_written_once_and_checked():
    s, ws = _store()
    assert ws.rows[0] == SHEET_COLUMNS
    s.ensure_header()                       # idempotent
    assert len(ws.rows) == 1
    bad = FakeWorksheet()
    bad.rows = [["wrong", "header"]]
    with pytest.raises(StoreError):
        SheetStore(bad).ensure_header()


def test_append_is_a_single_call_with_raw_input():
    s, ws = _store()
    s.append_shipment(_frame(), "salt$hash", "fp123")
    assert ws.append_calls == 1 and ws.last_append_option == "RAW"
    assert len(ws.rows) == 3                # header + 2 checkpoints


def test_hash_and_fingerprint_only_on_first_row_and_no_plain_code():
    rows = frame_to_rows(_frame(), "salt$hash", "fp123")
    h, f = SHEET_COLUMNS.index("delete_code_hash"), SHEET_COLUMNS.index("fingerprint")
    assert rows[0][h] == "salt$hash" and rows[0][f] == "fp123"
    assert rows[1][h] == "" and rows[1][f] == ""
    assert all(len(r) == len(SHEET_COLUMNS) for r in rows)


def test_roundtrip_types():
    s, ws = _store()
    s.append_shipment(_frame(), "salt$hash", "fp123")
    df = s.load_all()
    assert df["lat"].dtype.kind == "f" and df["stop_order"].tolist() == [1, 2]
    assert pd.isna(df["arrived"].iloc[0]) and df["departed"].iloc[0] == pd.Timestamp("2026-09-01 08:00")
    assert df["postal_code"].tolist() == ["518000", ""]


def test_leading_zero_postal_code_survives():
    s, ws = _store()
    stops = _stops()
    stops[0]["postal_code"] = "01234"
    s.append_shipment(stops_to_frame(stops, "UPS", "Apparel", "SHP-ZERO0001", status="approved"), "s$h", "fp")
    assert s.load_all()["postal_code"].iloc[0] == "01234"


def test_load_approved_filters_status_source_and_bad_coords():
    s, ws = _store()
    s.append_shipment(_frame("SHP-APPROVED1", "approved"), "a$a", "f1")
    s.append_shipment(_frame("SHP-PENDING01", "pending"), "b$b", "f2")
    s.append_shipment(_frame("SHP-DELETED01", "deleted"), "c$c", "f3")
    seed_like = _frame("SHP-SEEDLIKE1", "approved")
    seed_like["source"] = "seed"
    s.append_shipment(seed_like, "d$d", "f4")
    s.append_shipment(_frame("SHP-BADCOORD1", "approved"), "e$e", "f5")
    ws.rows[-1][SHEET_COLUMNS.index("lat")] = "not a number"
    out = s.load_approved()
    assert list(out.columns) == COLUMNS
    assert set(out["shipment_id"]) == {"SHP-APPROVED1"}


def test_status_is_normalised_when_owner_edits_by_hand():
    s, ws = _store()
    s.append_shipment(_frame(), "a$a", "f")
    for r in ws.rows[1:]:
        r[SHEET_COLUMNS.index("status")] = " Approved "
    assert len(s.load_approved()) == 2


def test_set_status_changes_only_that_shipment_and_never_removes_rows():
    s, ws = _store()
    s.append_shipment(_frame("SHP-ONE00001"), "a$a", "f1")
    s.append_shipment(_frame("SHP-TWO00002"), "b$b", "f2")
    assert s.set_status("SHP-ONE00001", "deleted") == 2
    df = s.load_all()
    assert len(df) == 4
    assert df.groupby("shipment_id")["status"].first().to_dict() == {"SHP-ONE00001": "deleted",
                                                                      "SHP-TWO00002": "approved"}
    assert s.set_status("SHP-ONE00001", "approved") == 2
    assert s.set_status("SHP-NOPE0000", "deleted") == 0
    with pytest.raises(ValueError):
        s.set_status("SHP-ONE00001", "erased")


def test_summary_one_line_per_shipment():
    s, ws = _store()
    s.append_shipment(_frame("SHP-ONE00001"), "a$a", "f1")
    s.append_shipment(_frame("SHP-TWO00002", "pending"), "b$b", "f2")
    t = s.summary()
    assert len(t) == 2 and set(t["status"]) == {"approved", "pending"}
    assert t["route"].iloc[0] == "Shenzhen → Houston" and t["stops"].tolist() == [2, 2]


def test_empty_sheet_loads_empty():
    s, ws = _store()
    assert s.load_all().empty and s.load_approved().empty and s.summary().empty


def test_failures_become_store_error():
    s, ws = _store()
    ws.fail = True
    for call in (s.load_all, s.load_approved, lambda: s.append_shipment(_frame(), "a$a", "f"),
                 lambda: s.set_status("SHP-X", "deleted")):
        with pytest.raises(StoreError):
            call()


def test_rows_to_frame_rejects_wrong_header():
    with pytest.raises(StoreError):
        rows_to_frame([["a", "b"], ["1", "2"]])


def test_dates_without_a_time_are_written_as_dates_and_older_times_are_kept():
    stops = _stops()
    stops[0]["departed"] = pd.Timestamp("2026-09-01").to_pydatetime()            # date only: midnight
    stops[1]["arrived"] = pd.Timestamp("2026-09-10 17:30").to_pydatetime()       # an older row with a time
    rows = frame_to_rows(stops_to_frame(stops, "UPS", "Electronics", "SHP-DATES001", status="approved"), "s$h", "fp")
    dep, arr = SHEET_COLUMNS.index("departed"), SHEET_COLUMNS.index("arrived")
    assert rows[0][dep] == "2026-09-01" and rows[1][arr] == "2026-09-10 17:30"
    s, ws = _store()
    s.append_shipment(stops_to_frame(stops, "UPS", "Electronics", "SHP-DATES001", status="approved"), "s$h", "fp")
    df = s.load_all()
    assert df["departed"].iloc[0] == pd.Timestamp("2026-09-01") and df["arrived"].iloc[1] == pd.Timestamp("2026-09-10 17:30")
