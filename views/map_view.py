"""Screen 2: map. Layout only; logic lives in modules/."""
import streamlit as st

from modules.borders import border_lines, country_extent
from modules.data_model import LABEL_SEED, LABEL_USER, visible_frame
from modules.map_figure import build_map_figure
from modules.regions import apply_drilldown, city_options, country_options, state_options
from modules.seed import get_seed_frame
from views.common import DB_DOWN_MESSAGE, load_user_rows


@st.cache_data
def load_seed():
    return get_seed_frame()


ss = st.session_state
saved, db_ok, db_err = load_user_rows()
submitted = ([saved] if len(saved) else []) + list(ss.get("unsaved", []))
if not db_ok:
    st.warning(f"{DB_DOWN_MESSAGE} ({db_err})")

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

parts = []
if show_examples:
    parts.append(f"{LABEL_SEED} examples")
if submitted:
    parts.append(f"submitted routes ({LABEL_USER})")
sources = " + ".join(parts)
highlight = ss.get("last_id")

# Fixed world map: always the full picture, whatever the filters say.
world = apply_drilldown(data)
n = world.routes["shipment_id"].nunique() if len(world.routes) else 0
if data.empty:
    st.info("No routes to show. Turn on **Show example routes**, or log a shipment first.")
else:
    st.caption(f"**World** · {n} route{'s' if n != 1 else ''} · {len(world.hotspots)} hotspots · {sources}")
st.plotly_chart(build_map_figure(world.routes, world.hotspots, height=640, highlight_id=highlight),
                width="stretch", key="world_map")

# Drill-down map: appears below the world map once a country, state or city is chosen.
if country:
    view = apply_drilldown(data, country, state, city)
    k = view.routes["shipment_id"].nunique() if len(view.routes) else 0
    st.caption(f"**{view.level}: {view.label}** · {k} route{'s' if k != 1 else ''} · "
               f"{len(view.hotspots)} hotspot{'s' if len(view.hotspots) != 1 else ''} · {sources}")
    lon_range, lat_range = view.lon_range, view.lat_range
    if not state and not city:                  # whole country chosen: frame the country, borders included
        frame = country_extent(country)
        if frame:
            lon_range, lat_range = frame
    st.plotly_chart(build_map_figure(view.routes, view.hotspots, height=640, highlight_id=highlight,
                                     lon_range=lon_range, lat_range=lat_range,
                                     borders=border_lines(country)),
                    width="stretch", key="drill_map")
    st.caption("State and province borders: Natural Earth (public domain), simplified.")
