"""Screen 1: log a shipment. Layout only; logic lives in modules/."""
import time

import streamlit as st

from modules.checkpoints import (
    combine_dt, delete_stop, make_stop, stops_to_frame, validate_stop_input,
)
from modules.data_model import (
    CARRIER_COLORS, CARRIERS, LABEL_USER, PRODUCT_CLASSES, STAGE_TYPES,
)
from modules.geocoding import CITY_LEVEL_STAGES, Geocoder, build_fallback
from modules.locations import country_names, state_names
from modules.seed import CITIES
from modules.shipments import SubmissionError, submit_shipment, validate_submission
from modules.sheets_store import StoreError
from modules.validation import prune_timestamps
from views.common import DB_DOWN_MESSAGE, get_store, read_config, refresh_data

USER_AGENT = "GlobalShipmentRouteMapper/1.0 (portfolio project; https://github.com/gp26902)"


@st.cache_resource
def get_geocoder() -> Geocoder:
    # One shared instance: one cache and one rate limiter for every visitor.
    return Geocoder(USER_AGENT, fallback=build_fallback(CITIES.values()))


def _fmt(t) -> str:
    return t.strftime("%Y-%m-%d %H:%M") if t else "n/a"


def _delete(i: int) -> None:
    st.session_state.stops = delete_stop(st.session_state.stops, i)


def _clear() -> None:
    st.session_state.stops = []


ss = st.session_state
ss.setdefault("stops", [])
ss.setdefault("unsaved", [])        # shipments confirmed while the database was down (session only)
ss.setdefault("submit_times", [])   # for the per-session rate limit
ss.setdefault("last_id", None)
ss.setdefault("last_code", None)
ss.setdefault("last_status", None)
ss.setdefault("last_saved", False)
ss.setdefault("last_summary", None)
ss.setdefault("form_gen", 0)
ss.setdefault("flash", None)

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

c1, c2 = st.columns(2)
carrier = c1.selectbox("Carrier", CARRIERS, index=None, placeholder="Select a carrier", key="carrier")
if carrier:
    c1.markdown(f"<span style='color:{CARRIER_COLORS[carrier]};font-size:1.2em'>■</span> "
                f"<small>{carrier} map colour</small>", unsafe_allow_html=True)
product_class = c2.selectbox("Product class", PRODUCT_CLASSES, index=None,
                             placeholder="Select a product class", key="product_class")

st.subheader(f"Add stop {len(ss.stops) + 1}")
if ss.flash:
    st.success(ss.flash)
    ss.flash = None

g = ss.form_gen
# Country and region sit outside the form so the region list can follow the country.
# The country stays selected between stops; the region resets for each new stop.
l1, l2 = st.columns(2)
country = l1.selectbox("Country", country_names(), index=None, placeholder="Select a country",
                       key="loc_country")
regions = state_names(country)
state = l2.selectbox("State / region (optional)", regions, index=None,
                     placeholder=("Select a state / region" if regions
                                  else "No regions listed" if country else "Select a country first"),
                     disabled=not regions, key=f"loc_state_{g}_{country}")
country, state = country or "", state or ""

with st.form(f"stop_form_{g}"):
    a, b = st.columns(2)
    stage = a.selectbox("Stage type", STAGE_TYPES, index=0 if not ss.stops else 1, key=f"stage_{g}")
    facility = b.text_input("Facility name (optional)", max_chars=80, key=f"fac_{g}")
    c, d = st.columns(2)
    city = c.text_input("City", max_chars=60, key=f"city_{g}")
    postal = d.text_input("Postal / PIN code (optional)", max_chars=12, key=f"postal_{g}",
                          help="Used for hub stops only. Ignored for last-mile and destination.")
    t1, t2, t3, t4 = st.columns(4)
    arr_d = t1.date_input("Arrived date", value=None, key=f"ad_{g}")
    arr_t = t2.time_input("Arrived time", value=None, key=f"at_{g}")
    dep_d = t3.date_input("Departed date", value=None, key=f"dd_{g}")
    dep_t = t4.time_input("Departed time", value=None, key=f"dt_{g}")
    st.caption("Times are optional, local to each facility, and in 24-hour format (13:00 = 1 PM).")
    add = st.form_submit_button("Add stop", type="primary")

if add:
    errors = []
    arrived = departed = None
    try:
        arrived = combine_dt(arr_d, arr_t)
        departed = combine_dt(dep_d, dep_t)
    except ValueError as exc:
        errors.append(str(exc))
    errors += validate_stop_input(stage, facility, city, state, country, postal, arrived, departed)
    if len(ss.stops) >= 15:
        errors.append("A route can have at most 15 stops.")
    if errors:
        for msg in errors:
            st.error(msg)
    else:
        with st.spinner("Looking up location..."):
            geo = get_geocoder().geocode(stage, city, state, country, postal)
        if not geo.ok:
            st.error(geo.error)
        else:
            ss.stops = ss.stops + [make_stop(stage, facility, city, state, country, postal,
                                             arrived, departed, geo)]
            note = f"Stop added: {geo.display_name}"
            if geo.source == "built-in":
                note += " (matched from the built-in city list)"
            if postal.strip() and stage in CITY_LEVEL_STAGES:
                note += ". Postal code ignored: this stage is plotted at city level."
            ss.flash = note
            ss.form_gen += 1
            st.rerun()

st.subheader("Route preview")
if not ss.stops:
    st.caption("No stops yet. Add an Origin first.")
else:
    widths = [0.5, 2, 2.4, 3, 1.3, 3, 1.3]
    for col, label in zip(st.columns(widths), ["#", "Stage", "Facility", "Location", "Postal",
                                               "Arrived / Departed", ""]):
        col.markdown(f"**{label}**")
    for i, s in enumerate(ss.stops):
        cols = st.columns(widths)
        cols[0].write(i + 1)
        cols[1].write(s["stage_type"])
        cols[2].write(s["facility"])
        cols[3].write(", ".join(p for p in (s["city"], s["state"], s["country"]) if p))
        cols[4].write(s["postal_code"] or "n/a")
        cols[5].write(f"{_fmt(s['arrived'])} / {_fmt(s['departed'])}")
        cols[6].button("Delete", key=f"del_{i}", on_click=_delete, args=(i,))
    st.markdown("<style>.st-key-hp_wrap{position:absolute;left:-9999px;height:0;overflow:hidden}</style>",
                unsafe_allow_html=True)
    with st.container(key="hp_wrap"):
        honeypot = st.text_input("Website (leave this empty)", key="hp_field", autocomplete="off")
    b1, b2, _ = st.columns([1.2, 1.2, 5])
    b1.button("Clear route", on_click=_clear)
    if b2.button("Confirm route", type="primary"):
        now = time.time()
        ss.submit_times = prune_timestamps(ss.submit_times, now)
        mode = (read_config() or {}).get("approval_mode", "manual")
        try:
            if _cfg_store is None:
                # Database down: validate the same way, keep it for this session only.
                validate_submission(ss.stops, carrier, product_class, honeypot, ss.submit_times, now)
                sid = "LOCAL-" + str(int(now))[-6:]
                frame = stops_to_frame(ss.stops, carrier, product_class, sid, status="approved")
                ss.unsaved = ss.unsaved + [frame]
                code, saved = None, False
            else:
                res = submit_shipment(_cfg_store, ss.stops, carrier, product_class, mode, honeypot,
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
            ss.stops = []
            ss.form_gen += 1
            st.rerun()
