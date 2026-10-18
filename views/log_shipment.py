"""Screen 1: log a shipment. Layout only; logic lives in modules/."""
import re
import time

import streamlit as st

from modules.checkpoints import MAX_STOPS, make_stop, stops_to_frame
from modules.data_model import (
    CARRIER_COLORS, CARRIERS, LABEL_USER, PRODUCT_CLASSES, STAGE_TYPES,
)
from modules.geocoding import CITY_LEVEL_STAGES, Geocoder, build_fallback
from modules.locations import country_names, state_names
from modules.seed import CITIES
from modules.shipments import SubmissionError, submit_shipment, validate_submission
from modules.sheets_store import StoreError
from modules.stop_input import read_row, row_is_blank
from modules.validation import prune_timestamps
from views.common import DB_DOWN_MESSAGE, get_store, read_config, refresh_data

USER_AGENT = "GlobalShipmentRouteMapper/1.0 (portfolio project; https://github.com/gp26902)"


@st.cache_resource
def get_geocoder() -> Geocoder:
    # One shared instance: one cache and one rate limiter for every visitor.
    return Geocoder(USER_AGENT, fallback=build_fallback(CITIES.values()))


COUNTRIES = country_names()
WIDTHS = [0.35, 1.55, 1.6, 1.7, 1.85, 1.95, 1.95, 1.15]
HELP_TIME = ("MM/DD/YYYY HH:MM, local to the facility. 3:01 AM, 03:01 and 15:10 all work, "
             "and A.M./P.M. pasted from a tracking page is fine. Leave empty if unknown.")

ss = st.session_state
ss.setdefault("rows", [])           # ids of the stop rows, in order
ss.setdefault("row_seq", 0)
ss.setdefault("row_defaults", {})   # row id -> default stage / country positions
ss.setdefault("unsaved", [])        # shipments confirmed while the database was down (session only)
ss.setdefault("submit_times", [])   # for the per-session rate limit
ss.setdefault("last_id", None)
ss.setdefault("last_code", None)
ss.setdefault("last_status", None)
ss.setdefault("last_saved", False)
ss.setdefault("last_summary", None)
ss.setdefault("flash", None)
ss.setdefault("geo_cache", {})      # lookups already done in this session, reused when a row is unchanged


def _new_row(stage: str, country_index=None) -> None:
    rid = ss.row_seq
    ss.row_seq += 1
    ss.row_defaults[rid] = {"stage": STAGE_TYPES.index(stage), "country": country_index}
    ss.rows = ss.rows + [rid]


def _drop_row_state(rid: int) -> None:
    for k in [k for k in ss.keys() if k.startswith(f"r{rid}_")]:
        del ss[k]
    ss.row_defaults.pop(rid, None)


def _reset_rows() -> None:
    for rid in list(ss.rows):
        _drop_row_state(rid)
    ss.rows = []
    _new_row("Origin")


def _remove_row(rid: int) -> None:
    _drop_row_state(rid)
    ss.rows = [r for r in ss.rows if r != rid]


def _values(rid: int) -> dict:
    country = ss.get(f"r{rid}_country")
    return {"stage": ss.get(f"r{rid}_stage"), "country": country or "",
            "state": ss.get(f"r{rid}_state_{country}") or "",
            "city_zip": ss.get(f"r{rid}_city") or "",
            "arr": ss.get(f"r{rid}_arr") or "", "dep": ss.get(f"r{rid}_dep") or ""}


def _is_blank(rid: int) -> bool:
    """A new row starts with the previous row's country filled in. That alone is not content."""
    v = _values(rid)
    idx = ss.row_defaults.get(rid, {}).get("country")
    carried = COUNTRIES[idx] if idx is not None else ""
    country = "" if v["country"] == carried else v["country"]
    return row_is_blank(country, v["state"], v["city_zip"], v["arr"], v["dep"])


def _process_row(n: int, rid: int):
    """Read, validate and geocode one row. Returns (stop, errors, note)."""
    v = _values(rid)
    res = read_row(v["stage"], v["country"], v["state"], v["city_zip"], v["arr"], v["dep"])
    if res.errors:
        return None, [f"Stop {n}: {e}" for e in res.errors], ""
    x = res.values
    key = (x["stage"] in CITY_LEVEL_STAGES, x["city"].lower(), x["state"].lower(),
           x["country"].lower(), x["postal"].lower())
    geo = ss.geo_cache.get(key)
    if geo is None:
        geo = get_geocoder().geocode(x["stage"], x["city"], x["state"], x["country"], x["postal"])
        if geo.ok:
            ss.geo_cache[key] = geo
    if not geo.ok:
        return None, [f"Stop {n}: {geo.error}"], ""
    stop = make_stop(x["stage"], "", x["city"], x["state"], x["country"], x["postal"],
                     x["arrived"], x["departed"], geo)
    note = f"Stop {n} located: {geo.display_name}"
    if geo.source == "built-in":
        note += " (matched from the built-in city list)"
    if x["postal"] and x["stage"] in CITY_LEVEL_STAGES:
        note += ". Postal code ignored: this stage is plotted at city level."
    return stop, [], note


if ss.pop("reset_rows", False) or not ss.rows:
    _reset_rows()

st.title("Log a shipment")
st.info("**Privacy:** never enter street addresses or personal names. City, regional or postal level "
        "only. Postal codes are used for hub stops; last-mile and destination stops are placed at "
        "city level and their postal code is not kept.")

if ss.last_id:
    if not ss.last_saved:
        st.warning(f"Shipment **{ss.last_id}** is shown on the map for this session only. It was **not saved**: "
                   "the database is unreachable, so there is no delete code.")
    elif ss.last_status == "pending":
        st.success(f"Shipment **{ss.last_id}** received ({LABEL_USER}). It will appear on the map once the "
                   "owner approves it.")
    else:
        st.success(f"Shipment **{ss.last_id}** logged ({LABEL_USER}).")
    if ss.last_code:
        st.warning("Save this delete code now. It is shown only once and cannot be recovered: only a hash "
                   "is stored. Use it with the shipment ID on the Manage page to remove this shipment.")
        st.code(ss.last_code, language=None)
        if st.button("I have saved my code"):
            ss.last_code = None
            st.rerun()
    st.dataframe(ss.last_summary, hide_index=True, width="stretch")
    st.page_link("views/map_view.py", label="View on map", icon="🗺️")
    st.divider()
    st.subheader("Log another shipment")

_cfg_store, _store_err = get_store()
if _cfg_store is None:
    st.warning(f"{DB_DOWN_MESSAGE} ({_store_err})")

st.markdown(
    "<style>"
    ".st-key-hp_wrap{position:absolute;left:-9999px;height:0;overflow:hidden}"
    ".st-key-add_stop button,.st-key-add_stop button:focus{background:#d62728;border-color:#d62728;color:#fff;width:100%}"
    ".st-key-add_stop button:hover{background:#b71c1c;border-color:#b71c1c;color:#fff}"
    ".st-key-add_stop button p,.st-key-submit_route button p{color:#fff}"
    ".st-key-submit_route button,.st-key-submit_route button:focus{background:#1e9e4a;border-color:#1e9e4a;color:#fff}"
    ".st-key-submit_route button:hover{background:#17803b;border-color:#17803b;color:#fff}"
    "</style>", unsafe_allow_html=True)

c1, c2 = st.columns(2)
carrier = c1.selectbox("Carrier", CARRIERS, index=None, placeholder="Select a carrier", key="carrier")
if carrier:
    c1.markdown(f"<span style='color:{CARRIER_COLORS[carrier]};font-size:1.2em'>■</span> "
                f"<small>{carrier} map colour</small>", unsafe_allow_html=True)
product_class = c2.selectbox("Product class", PRODUCT_CLASSES, index=None,
                             placeholder="Select a product class", key="product_class")

st.subheader("Route stops")
st.caption("One row per stop. Press **Add stop** for the next row. You can edit any row until the route "
           "is complete, then press **Submit route to map**.")
if ss.flash:
    st.success(ss.flash)
    ss.flash = None

add_clicked = False
for i, rid in enumerate(ss.rows):
    first, last = i == 0, i == len(ss.rows) - 1
    vis = "visible" if first else "collapsed"
    d = ss.row_defaults[rid]
    with st.container(key=f"row_{rid}"):
        cols = st.columns(WIDTHS, vertical_alignment="bottom" if first else "center")
        cols[0].markdown(f"**{i + 1}**")
        cols[1].selectbox("Stage", STAGE_TYPES, index=d["stage"], key=f"r{rid}_stage", label_visibility=vis)
        country = cols[2].selectbox("Country", COUNTRIES, index=d["country"], placeholder="Country",
                                    key=f"r{rid}_country", label_visibility=vis)
        regions = state_names(country)
        cols[3].selectbox("State / region", regions, index=None, disabled=not regions,
                          placeholder=("State / region" if regions
                                       else "No regions listed" if country else "Pick a country first"),
                          key=f"r{rid}_state_{country}", label_visibility=vis)
        cols[4].text_input("City or ZIP", placeholder="City, ZIP optional", max_chars=72,
                           key=f"r{rid}_city", label_visibility=vis,
                           help="Type the city. You can add a ZIP / postal code after it, e.g. Stafford 77477.")
        cols[5].text_input("Arrival", placeholder="MM/DD/YYYY HH:MM", max_chars=24,
                           key=f"r{rid}_arr", label_visibility=vis, help=HELP_TIME)
        cols[6].text_input("Departure", placeholder="MM/DD/YYYY HH:MM", max_chars=24,
                           key=f"r{rid}_dep", label_visibility=vis, help=HELP_TIME)
        if last:
            add_clicked = cols[7].button("Add stop", key="add_stop")
        else:
            cols[7].button("Remove", key=f"rm_{rid}", on_click=_remove_row, args=(rid,))

if add_clicked:
    n, rid = len(ss.rows), ss.rows[-1]
    if n >= MAX_STOPS:
        st.error(f"A route can have at most {MAX_STOPS} stops.")
    else:
        with st.spinner("Looking up location..."):
            stop, errs, note = _process_row(n, rid)
        if errs:
            for msg in errs:
                st.error(msg)
        else:
            country_val = _values(rid)["country"]
            ss.flash = note
            _new_row("Sorting Hub", COUNTRIES.index(country_val) if country_val in COUNTRIES else None)
            st.rerun()

with st.container(key="hp_wrap"):
    honeypot = st.text_input("Website (leave this empty)", key="hp_field", autocomplete="off")
b1, b2, _ = st.columns([1.2, 2.2, 4])
b1.button("Clear route", on_click=_reset_rows)
if b2.button("Submit route to map", key="submit_route"):
    now = time.time()
    ss.submit_times = prune_timestamps(ss.submit_times, now)
    mode = (read_config() or {}).get("approval_mode", "manual")
    rows = list(ss.rows)
    if len(rows) > 1 and _is_blank(rows[-1]):
        rows = rows[:-1]            # the empty working row at the end is ignored
    stops, errors = [], []
    with st.spinner("Checking locations..."):
        for n, rid in enumerate(rows, start=1):
            if _is_blank(rid):
                errors.append(f"Stop {n} is empty. Fill it in or remove it.")
                continue
            stop, errs, _note = _process_row(n, rid)
            errors += errs
            if stop:
                stops.append(stop)
    if errors:
        for msg in errors:
            st.error(msg)
    else:
        try:
            if _cfg_store is None:
                # Database down: validate the same way, keep it for this session only.
                validate_submission(stops, carrier, product_class, honeypot, ss.submit_times, now)
                sid = "LOCAL-" + str(int(now))[-6:]
                frame = stops_to_frame(stops, carrier, product_class, sid, status="approved")
                ss.unsaved = ss.unsaved + [frame]
                code, saved = None, False
            else:
                res = submit_shipment(_cfg_store, stops, carrier, product_class, mode, honeypot,
                                      ss.submit_times, now)
                sid, frame, code, saved = res.shipment_id, res.frame, res.delete_code, True
                ss.last_status = res.status
                refresh_data()
        except SubmissionError as exc:
            for msg in exc.errors:
                st.error(msg)
        except StoreError as exc:
            st.error(f"Could not save to the database, nothing was stored. Please try again. ({exc})")
        else:
            ss.submit_times = ss.submit_times + [now]
            ss.last_id, ss.last_code, ss.last_saved = sid, code, saved
            ss.last_summary = frame[["stop_order", "stage_type", "facility", "city", "state",
                                     "country", "arrived", "departed"]]
            ss.reset_rows = True
            st.rerun()
