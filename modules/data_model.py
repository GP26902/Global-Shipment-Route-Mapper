"""Data model: schema, constants and labels. No Streamlit dependency.

One shipment = many rows (one per checkpoint) sharing a shipment_id.
"""
import pandas as pd

APP_TITLE = "Global Shipment Route Mapper"

CARRIERS = ["Amazon Logistics", "FedEx", "UPS", "DHL", "USPS", "Other"]

# Brand-inspired colours, tuned to stay readable on a light map.
CARRIER_COLORS = {
    "Amazon Logistics": "#FF9900",
    "FedEx": "#4D148C",
    "UPS": "#5A3A22",
    "DHL": "#E0A800",
    "USPS": "#1F4E9C",
    "Other": "#6B7280",
}

PRODUCT_CLASSES = [
    "Apparel",
    "Food & Perishables",
    "Machinery & Industrial",
    "Electronics",
    "General Merchandise",
]

STAGE_TYPES = [
    "Origin",
    "Sorting Hub",
    "Customs Facility",
    "Regional Distribution",
    "Last-Mile Facility",
    "Final Destination",
]

STATUSES = ["pending", "approved", "deleted"]

SOURCE_SEED = "seed"
SOURCE_USER = "user"

LABEL_SEED = "illustrative"
LABEL_USER = "user-reported, unverified"

COLUMNS = [
    "shipment_id", "stop_order", "stage_type", "facility",
    "city", "state", "country", "postal_code", "lat", "lon",
    "arrived", "departed",
    "carrier", "product_class",
    "status", "source", "created_at",
]


def empty_frame() -> pd.DataFrame:
    """An empty checkpoint table with the full schema."""
    return pd.DataFrame(columns=COLUMNS)


def data_label(source: str) -> str:
    """Human-readable provenance label for a row's source."""
    return LABEL_SEED if source == SOURCE_SEED else LABEL_USER


def carrier_color(carrier: str) -> str:
    return CARRIER_COLORS.get(carrier, CARRIER_COLORS["Other"])


def visible_frame(seed: pd.DataFrame, user_frames, show_examples: bool) -> pd.DataFrame:
    """Rows to plot: optional seed routes plus user routes, never deleted ones."""
    parts = ([seed] if show_examples else []) + list(user_frames)
    if not parts:
        return empty_frame()
    df = pd.concat(parts, ignore_index=True)
    return df[df["status"] != "deleted"].reset_index(drop=True)
