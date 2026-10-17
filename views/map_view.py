"""Screen 2: map. Layout only; logic lives in modules/."""
import streamlit as st

from modules.data_model import LABEL_SEED, LABEL_USER, visible_frame
from modules.map_figure import build_map_figure
from modules.regions import apply_drilldown, city_options, country_options, state_options
from modules.seed import get_seed_frame


@st.cache_data
def load_seed():
    return get_seed_frame()


ss = st.session_state
submitted = ss.get("submitted", [])

st.markdown("<style>.block-container{padding-top:2.5rem;padding-bottom:0.5rem}</style>",
            unsafe_allow_html=True)

with st.sidebar:
    st.header("Map options")
    show_examples = st.toggle("Show example routes", value=True)
    st.caption(f"Example routes are {LABEL_SEED}, not real shipments, and are excluded from all KPIs.")

data = visible_frame(load_seed(), submitted, show_examples)

with st.sidebar:
    st.header("Drill down")
    sel = st.selectbox("Country", ["All countries"] + country_options(data), key="dd_country")
    country = None if sel == "All countries" else sel
    states = state_options(data, country) if country else []
    sel = st.selectbox("State / region", ["All states"] + states, disabled=not states,
                       key=f"dd_state_{country}")
    state = None if sel == "All states" else sel
    cities = city_options(data, country, state) if country else []
    sel = st.selectbox("City", ["All cities"] + cities, disabled=not cities,
                       key=f"dd_city_{country}_{state}")
    city = None if sel == "All cities" else sel

view = apply_drilldown(data, country, state, city)

parts = []
if show_examples:
    parts.append(f"{LABEL_SEED} examples")
if submitted:
    parts.append(f"your routes ({LABEL_USER})")
n = view.routes["shipment_id"].nunique() if len(view.routes) else 0
if data.empty:
    st.info("No routes to show. Turn on **Show example routes**, or log a shipment first.")
else:
    where = "World" if view.level == "World" else f"{view.level}: {view.label}"
    st.caption(f"**{where}** · {n} route{'s' if n != 1 else ''} · "
               f"{len(view.hotspots)} hotspot{'s' if len(view.hotspots) != 1 else ''} · "
               + " + ".join(parts))

fig = build_map_figure(view.routes, view.hotspots, height=780, highlight_id=ss.get("last_id"),
                       lon_range=view.lon_range, lat_range=view.lat_range)
st.plotly_chart(fig, width="stretch")
