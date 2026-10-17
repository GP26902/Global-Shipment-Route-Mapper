"""Global Shipment Route Mapper: layout only. Logic lives in modules/."""
import streamlit as st

from modules.data_model import APP_TITLE, LABEL_SEED, empty_frame
from modules.map_figure import build_map_figure
from modules.seed import get_seed_frame

st.set_page_config(page_title=APP_TITLE, page_icon="🌍", layout="wide")


@st.cache_data
def load_seed():
    return get_seed_frame()


st.title(APP_TITLE)
st.caption(
    "Multi-stop shipment routes and hub hotspots for parcels and freight of any size. "
    "No street addresses or names are collected: city, regional or postal level only."
)

with st.sidebar:
    st.header("Map options")
    show_examples = st.toggle("Show example routes", value=True)
    st.caption(f"Example routes are {LABEL_SEED}, not real shipments, and are excluded from all KPIs.")

data = load_seed() if show_examples else empty_frame()

if data.empty:
    st.info("No routes to show yet. Turn on **Show example routes** in the sidebar.")
else:
    st.warning(f"Showing {data['shipment_id'].nunique()} {LABEL_SEED} routes "
               f"({len(data)} stops). These are made-up examples.")

st.plotly_chart(build_map_figure(data), width="stretch")
