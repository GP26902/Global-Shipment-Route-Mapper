"""Screen 1: log a shipment. Layout only; logic lives in modules/."""
import streamlit as st

from modules.checkpoints import (
    combine_dt, delete_stop, generate_shipment_id, make_stop, stops_to_frame,
    validate_route, validate_stop_input,
)
from modules.data_model import (
    CARRIER_COLORS, CARRIERS, LABEL_USER, PRODUCT_CLASSES, STAGE_TYPES,
)
from modules.geocoding import CITY_LEVEL_STAGES, Geocoder, build_fallback
from modules.seed import CITIES

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
ss.setdefault("submitted", [])      # confirmed shipments (DataFrames), this browser session only
ss.setdefault("last_id", None)
ss.setdefault("last_summary", None)
ss.setdefault("form_gen", 0)
ss.setdefault("flash", None)

st.title("Log a shipment")
st.info("**Privacy:** never enter street addresses or personal names. City, regional or postal level "
        "only. Postal codes are used for hub stops; last-mile and destination stops are placed at "
        "city level and their postal code is not kept.")

if ss.last_id:
    st.success(f"Shipment **{ss.last_id}** logged ({LABEL_USER}). It is kept for this browser "
               "session only until the database step is added.")
    st.dataframe(ss.last_summary, hide_index=True, width="stretch")
    st.page_link("views/map_view.py", label="View on map", icon="🗺️")
    st.divider()
    st.subheader("Log another shipment")

c1, c2 = st.columns(2)
carrier = c1.selectbox("Carrier", CARRIERS, key="carrier")
c1.markdown(f"<span style='color:{CARRIER_COLORS[carrier]};font-size:1.2em'>■</span> "
            f"<small>{carrier} map colour</small>", unsafe_allow_html=True)
product_class = c2.selectbox("Product class", PRODUCT_CLASSES, key="product_class")

st.subheader(f"Add stop {len(ss.stops) + 1}")
if ss.flash:
    st.success(ss.flash)
    ss.flash = None

g = ss.form_gen
with st.form(f"stop_form_{g}"):
    a, b = st.columns(2)
    stage = a.selectbox("Stage type", STAGE_TYPES, index=0 if not ss.stops else 1, key=f"stage_{g}")
    facility = b.text_input("Facility name (optional)", max_chars=80, key=f"fac_{g}")
    c, d, e = st.columns(3)
    city = c.text_input("City", max_chars=60, key=f"city_{g}")
    state = d.text_input("State / region", max_chars=60, key=f"state_{g}")
    country = e.text_input("Country", max_chars=60, key=f"country_{g}")
    postal = st.text_input("Postal / PIN code (optional)", max_chars=12, key=f"postal_{g}",
                           help="Used for hub stops only. Ignored for last-mile and destination.")
    t1, t2, t3, t4 = st.columns(4)
    arr_d = t1.date_input("Arrived date", value=None, key=f"ad_{g}")
    arr_t = t2.time_input("Arrived time", value=None, key=f"at_{g}")
    dep_d = t3.date_input("Departed date", value=None, key=f"dd_{g}")
    dep_t = t4.time_input("Departed time", value=None, key=f"dt_{g}")
    st.caption("Times are optional and local to each facility.")
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
    b1, b2, _ = st.columns([1.2, 1.2, 5])
    b1.button("Clear route", on_click=_clear)
    if b2.button("Confirm route", type="primary"):
        problems = validate_route(ss.stops, carrier, product_class)
        if problems:
            for msg in problems:
                st.error(msg)
        else:
            sid = generate_shipment_id()
            frame = stops_to_frame(ss.stops, carrier, product_class, sid, status="approved")
            ss.submitted = ss.submitted + [frame]
            ss.last_id = sid
            ss.last_summary = frame[["stop_order", "stage_type", "facility", "city", "state",
                                     "country", "arrived", "departed"]]
            ss.stops = []
            ss.form_gen += 1
            st.rerun()
