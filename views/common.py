"""Streamlit glue shared by the screens: secrets, cached store connection, cached loads.

Everything that can fail (secrets missing, Sheets unreachable) is turned into
store=None plus a message, so the app keeps running on seed data.
"""
from typing import Optional, Tuple

import pandas as pd
import streamlit as st

from modules import sheets_store
from modules.shipments import parse_approval_mode
from modules.sheets_store import SheetStore, StoreError

DB_DOWN_MESSAGE = ("Database unreachable. Showing illustrative example routes only. "
                   "Shipments you log in this session are not saved.")


def read_config() -> Optional[dict]:
    """Settings from Streamlit secrets, or None if they are missing or incomplete."""
    try:
        creds = dict(st.secrets["gcp_service_account"])
        sheets = st.secrets["sheets"]
        app = st.secrets["app"] if "app" in st.secrets else {}
        return {
            "credentials": creds,
            "sheet_id": str(sheets["sheet_id"]),
            "worksheet": str(sheets.get("worksheet", "shipments")),
            "approval_mode": parse_approval_mode(app.get("approval_mode", "immediate")),
            "admin_password": str(app.get("admin_password", "")),
        }
    except Exception:
        return None


@st.cache_resource(ttl=300, show_spinner=False)
def _connect(_cfg_key: str) -> Tuple[Optional[SheetStore], str]:
    """Cached for 5 minutes, so a failed connection is retried without hammering the API."""
    cfg = read_config()
    if cfg is None:
        return None, "Database settings are missing from the app secrets."
    try:
        return sheets_store.get_store(cfg["credentials"], cfg["sheet_id"], cfg["worksheet"]), ""
    except StoreError as exc:
        return None, str(exc)


def get_store() -> Tuple[Optional[SheetStore], str]:
    cfg = read_config()
    key = "" if cfg is None else cfg["sheet_id"] + cfg["worksheet"]
    return _connect(key)


@st.cache_data(ttl=60, show_spinner=False)
def _load_approved(_store: SheetStore) -> Tuple[Optional[pd.DataFrame], str]:
    try:
        return _store.load_approved(), ""
    except StoreError as exc:
        return None, str(exc)


def load_user_rows() -> Tuple[pd.DataFrame, bool, str]:
    """Approved rows from the sheet. Returns (frame, database_ok, error_message)."""
    store, err = get_store()
    if store is None:
        return pd.DataFrame(), False, err
    df, err = _load_approved(store)
    if df is None:
        return pd.DataFrame(), False, err
    return df, True, ""


def refresh_data() -> None:
    """Call after any write so the next load re-reads the sheet."""
    _load_approved.clear()
