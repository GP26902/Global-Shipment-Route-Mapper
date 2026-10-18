"""Screen 3: delete a shipment with its code, plus password-gated owner admin."""
import streamlit as st

from modules import security
from modules.data_model import STATUSES
from modules.shipments import admin_set_status, delete_with_code
from modules.sheets_store import StoreError
from views.common import DB_DOWN_MESSAGE, get_store, read_config, refresh_data

ss = st.session_state
ss.setdefault("failed_attempts", 0)
ss.setdefault("admin_ok", False)

st.title("Manage shipments")
store, err = get_store()
cfg = read_config()
if store is None:
    st.warning(f"{DB_DOWN_MESSAGE} ({err})")
    st.stop()

st.subheader("Delete my shipment")
st.caption("Enter the shipment ID and the one-time delete code you were shown when you logged it. "
           "The shipment is hidden from the map and statistics. Rows are kept, not erased.")
with st.form("delete_form"):
    sid = st.text_input("Shipment ID", placeholder="SHP-1A2B3C4D", max_chars=20)
    code = st.text_input("Delete code", placeholder="XXXX-XXXX-XXXX", max_chars=20)
    go = st.form_submit_button("Delete shipment")
if go:
    if security.attempts_exhausted(ss.failed_attempts):
        st.error("Too many failed attempts in this session. Reload the page to try again.")
    else:
        try:
            result = delete_with_code(store, sid, code)
        except StoreError as exc:
            st.error(f"Could not reach the database: {exc}")
        else:
            if result == "deleted":
                refresh_data()
                st.success("Shipment deleted. It no longer appears on the map.")
            elif result == "already_deleted":
                st.info("This shipment was already deleted.")
            else:
                ss.failed_attempts += 1
                st.error("Shipment ID or delete code not recognised.")

st.divider()
st.subheader("Owner admin")
if not cfg or not cfg["admin_password"]:
    st.caption("Admin is disabled: no admin password is set in the app secrets.")
    st.stop()

if not ss.admin_ok:
    with st.form("admin_form"):
        pw = st.text_input("Admin password", type="password")
        enter = st.form_submit_button("Unlock")
    if enter:
        if security.attempts_exhausted(ss.failed_attempts):
            st.error("Too many failed attempts in this session. Reload the page to try again.")
        elif security.check_admin_password(pw, cfg["admin_password"]):
            ss.admin_ok = True
            st.rerun()
        else:
            ss.failed_attempts += 1
            st.error("Incorrect password.")
    st.stop()

if ss.get("admin_flash"):
    st.success(ss.pop("admin_flash"))
st.caption(f"New submissions are set to **{'approved immediately' if cfg['approval_mode'] == 'immediate' else 'pending until you approve'}** "
           "(change `approval_mode` in the app secrets).")
if st.button("Lock admin"):
    ss.admin_ok = False
    st.rerun()
try:
    table = store.summary()
except StoreError as exc:
    st.error(f"Could not read the sheet: {exc}")
    st.stop()
if table.empty:
    st.caption("No shipments in the database yet.")
    st.stop()
counts = table["status"].value_counts()
st.caption(" · ".join(f"{s}: {int(counts.get(s, 0))}" for s in STATUSES))
st.dataframe(table, hide_index=True, width="stretch")
target = st.selectbox("Shipment", table["shipment_id"].tolist())
current = table.loc[table["shipment_id"] == target, "status"].iloc[0]
a, b, c, _ = st.columns([1, 1, 1, 4])
action = None
if current == "pending" and a.button("Approve", type="primary"):
    action = "approved"
if current != "deleted" and b.button("Delete"):
    action = "deleted"
if current == "deleted" and c.button("Restore"):
    action = "approved"
if action:
    try:
        admin_set_status(store, target, action)
        refresh_data()
        ss.admin_flash = f"{target} is now {action}."
        st.rerun()
    except StoreError as exc:
        st.error(str(exc))
