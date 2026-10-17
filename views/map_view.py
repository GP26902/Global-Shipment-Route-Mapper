"""Screen 2: map. Layout only; logic lives in modules/."""
import streamlit as st

from modules.data_model import LABEL_SEED, LABEL_USER, visible_frame
from modules.map_figure import build_map_figure
from modules.seed import get_seed_frame


@st.cache_data
def load_seed():
    return get_seed_frame()


ss = st.session_state
submitted = ss.get("submitted", [])

with st.sidebar:
    st.header("Map options")
    show_examples = st.toggle("Show example routes", value=True)
    st.caption(f"Example routes are {LABEL_SEED}, not real shipments, and are excluded from all KPIs.")

data = visible_frame(load_seed(), submitted, show_examples)

st.title("Route map")
parts = []
if show_examples:
    parts.append(f"{LABEL_SEED} example routes")
if submitted:
    parts.append(f"your logged routes ({LABEL_USER})")
if data.empty:
    st.info("No routes to show. Turn on **Show example routes**, or log a shipment first.")
else:
    n = data["shipment_id"].nunique()
    st.caption(f"Showing {n} route{'s' if n != 1 else ''}, {len(data)} stops: " + " and ".join(parts) + ".")

st.plotly_chart(build_map_figure(data, height=700, highlight_id=ss.get("last_id")), width="stretch")
