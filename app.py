"""Global Shipment Route Mapper: router only. Screens live in views/, logic in modules/."""
import streamlit as st

from modules.data_model import APP_TITLE

st.set_page_config(page_title=APP_TITLE, page_icon="🌍", layout="wide")

pages = st.navigation([
    st.Page("views/log_shipment.py", title="Log a shipment", icon="📝", default=True),
    st.Page("views/map_view.py", title="Map", icon="🗺️"),
    st.Page("views/manage.py", title="Manage", icon="🔧"),
])
pages.run()
