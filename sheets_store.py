"""Google Sheets persistence. No Streamlit dependency.

SheetStore wraps one worksheet. It is given a gspread-like worksheet object, so tests can
pass a fake. Rows are never physically deleted: status changes only.
Values are written with RAW input so Sheets never turns text into formulas, dates or numbers.
"""
from typing import Dict, List, Optional

import pandas as pd

from modules.data_model import COLUMNS, SOURCE_USER, STATUSES

SHEET_COLUMNS = COLUMNS + ["delete_code_hash", "fingerprint"]
_TIME_FMT = "%Y-%m-%d %H:%M"
_STAMP_FMT = "%Y-%m-%d %H:%M:%S"


class StoreError(Exception):
    """Any problem reaching or reading the database. The app falls back to seed data."""


def _col_letter(index_1based: int) -> str:
    letters = ""
    n = index_1based
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _fmt_time(value, fmt: str) -> str:
    return "" if pd.isna(value) else pd.Timestamp(value).strftime(fmt)


def _fmt_when(value) -> str:
    """Date only when no time of day was recorded (the entry form collects dates); older rows keep their time."""
    if pd.isna(value):
        return ""
    t = pd.Timestamp(value)
    return t.strftime("%Y-%m-%d" if (t.hour, t.minute, t.second) == (0, 0, 0) else _TIME_FMT)


def frame_to_rows(frame: pd.DataFrame, delete_hash: str, fp: str) -> List[list]:
    """Sheet rows for one shipment. The hash and fingerprint sit on the first row only."""
    rows = []
    for i, r in enumerate(frame.itertuples(index=False)):
        d = r._asdict()
        out = {
            "shipment_id": d["shipment_id"], "stop_order": int(d["stop_order"]),
            "stage_type": d["stage_type"], "facility": d["facility"],
            "city": d["city"], "state": d["state"], "country": d["country"],
            "postal_code": d["postal_code"], "lat": float(d["lat"]), "lon": float(d["lon"]),
            "arrived": _fmt_when(d["arrived"]), "departed": _fmt_when(d["departed"]),
            "carrier": d["carrier"], "product_class": d["product_class"],
            "status": d["status"], "source": d["source"],
            "created_at": _fmt_time(d["created_at"], _STAMP_FMT),
            "delete_code_hash": delete_hash if i == 0 else "",
            "fingerprint": fp if i == 0 else "",
        }
        rows.append([out[c] for c in SHEET_COLUMNS])
    return rows


def rows_to_frame(values: List[List[str]]) -> pd.DataFrame:
    """Parse get_all_values() output back into a typed frame with SHEET_COLUMNS."""
    if not values:
        return pd.DataFrame(columns=SHEET_COLUMNS)
    header, body = [h.strip() for h in values[0]], values[1:]
    if header != SHEET_COLUMNS:
        raise StoreError("The sheet's header row does not match the expected columns.")
    width = len(SHEET_COLUMNS)
    padded = [(list(r) + [""] * width)[:width] for r in body if any(str(c).strip() for c in r)]
    df = pd.DataFrame(padded, columns=SHEET_COLUMNS, dtype=object)
    df["stop_order"] = pd.to_numeric(df["stop_order"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    for col in ("arrived", "departed", "created_at"):
        df[col] = pd.to_datetime(df[col].where(df[col] != ""), errors="coerce")
    for col in ("shipment_id", "status", "source"):
        df[col] = df[col].astype(str).str.strip()
    df["status"] = df["status"].str.lower()
    return df


class SheetStore:
    def __init__(self, worksheet):
        self.ws = worksheet

    def ensure_header(self) -> None:
        """Write the header row if the sheet is empty; refuse to touch a sheet with other headers."""
        try:
            first = self.ws.row_values(1)
            if not first:
                end = _col_letter(len(SHEET_COLUMNS))
                self.ws.batch_update([{"range": f"A1:{end}1", "values": [SHEET_COLUMNS]}],
                                     value_input_option="RAW")
            elif [h.strip() for h in first] != SHEET_COLUMNS:
                raise StoreError("The sheet's header row does not match the expected columns.")
        except StoreError:
            raise
        except Exception as exc:  # gspread / network errors
            raise StoreError(f"Could not prepare the sheet: {exc}") from exc

    def load_all(self) -> pd.DataFrame:
        try:
            return rows_to_frame(self.ws.get_all_values())
        except StoreError:
            raise
        except Exception as exc:
            raise StoreError(f"Could not read the sheet: {exc}") from exc

    def load_approved(self) -> pd.DataFrame:
        """Approved user shipments in the map schema (COLUMNS).

        A shipment with any unusable row (for example a hand-edited bad coordinate) is skipped
        whole, so the map never shows a partial route.
        """
        df = self.load_all()
        bad_ids = set(df.loc[df["lat"].isna() | df["lon"].isna(), "shipment_id"])
        ok = (df["status"] == "approved") & (df["source"] == SOURCE_USER) & ~df["shipment_id"].isin(bad_ids)
        return df.loc[ok, COLUMNS].reset_index(drop=True)

    def append_shipment(self, frame: pd.DataFrame, delete_hash: str, fp: str) -> None:
        """One shipment = one append call, so it is all written or not at all."""
        try:
            self.ws.append_rows(frame_to_rows(frame, delete_hash, fp), value_input_option="RAW")
        except Exception as exc:
            raise StoreError(f"Could not save the shipment: {exc}") from exc

    def set_status(self, shipment_id: str, status: str) -> int:
        """Set status on every row of a shipment. Returns rows changed (0 if the ID is unknown)."""
        if status not in STATUSES:
            raise ValueError(f"Unknown status: {status}")
        try:
            ids = self.ws.col_values(1)
            col = _col_letter(SHEET_COLUMNS.index("status") + 1)
            data = [{"range": f"{col}{n}", "values": [[status]]}
                    for n, v in enumerate(ids, start=1) if n > 1 and v.strip() == shipment_id]
            if data:
                self.ws.batch_update(data, value_input_option="RAW")
            return len(data)
        except Exception as exc:
            raise StoreError(f"Could not update the shipment: {exc}") from exc

    def summary(self) -> pd.DataFrame:
        """One line per shipment for the admin screen (includes pending and deleted)."""
        df = self.load_all()
        if df.empty:
            return pd.DataFrame(columns=["shipment_id", "status", "carrier", "product_class",
                                         "route", "stops", "created_at"])
        df = df.sort_values(["shipment_id", "stop_order"])
        rows = []
        for sid, g in df.groupby("shipment_id", sort=False):
            rows.append({"shipment_id": sid, "status": g["status"].iloc[0], "carrier": g["carrier"].iloc[0],
                         "product_class": g["product_class"].iloc[0],
                         "route": f"{g['city'].iloc[0]} → {g['city'].iloc[-1]}",
                         "stops": len(g), "created_at": g["created_at"].iloc[0]})
        out = pd.DataFrame(rows)
        return out.sort_values("created_at", ascending=False).reset_index(drop=True)


def open_worksheet(credentials: Dict[str, str], sheet_id: str, worksheet_name: str):
    """Open the worksheet with a service account. Imported lazily so tests need no credentials."""
    try:
        import gspread
        client = gspread.service_account_from_dict(dict(credentials))
        return client.open_by_key(sheet_id).worksheet(worksheet_name)
    except Exception as exc:
        raise StoreError(f"Could not open the Google Sheet: {exc}") from exc


def get_store(credentials: Optional[Dict[str, str]], sheet_id: str, worksheet_name: str) -> SheetStore:
    store = SheetStore(open_worksheet(credentials or {}, sheet_id, worksheet_name))
    store.ensure_header()
    return store
