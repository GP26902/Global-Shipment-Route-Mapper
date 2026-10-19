"""Builds the dark Plotly route map. Plotly only, no Streamlit."""
import math

import pandas as pd
import plotly.graph_objects as go

from modules.data_model import (
    INCOMING_COLOR, OUTGOING_COLOR, carrier_color_dark, data_label,
)
from modules.regions import WORLD_LAT, WORLD_LON
from modules.routes import build_route_path

BG = "#000000"
STATE_BORDER_COLOR = "#7A7A7A"   # dimmer than country borders (#9A9A9A), so countries still read first


def _stop_hover(row, n_stops: int) -> str:
    return (f"<b>Stop {int(row.stop_order)} of {n_stops} · {row.stage_type}</b><br>"
            f"{row.city}, {row.state}, {row.country}<br>"
            f"{row.carrier} · {row.product_class}<br>"
            f"{row.shipment_id} · {data_label(row.source)}")


def _hotspot_hover(h) -> str:
    return (f"<b>{h.city}, {h.state}, {h.country}</b><br>"
            f"Incoming: {int(h.incoming)} · Outgoing: {int(h.outgoing)}<br>"
            f"{int(h.n_shipments)} shipment(s) · {h.carriers}<br>{h.labels}")


def incoming_size(n: int) -> float:
    return min(6 + 5 * math.sqrt(n), 44)


def outgoing_size(n: int, incoming: int = 0) -> float:
    """Ring size; always clearly larger than the red circle it surrounds."""
    return max(min(12 + 5 * math.sqrt(n), 50), incoming_size(incoming) + 6)


def build_map_figure(routes: pd.DataFrame, hotspots: pd.DataFrame, height: int = 780,
                     highlight_id=None, lon_range=WORLD_LON, lat_range=WORLD_LAT,
                     borders=None) -> go.Figure:
    """borders: optional (lons, lats) of state/province outlines, drawn first so routes sit on top."""
    fig = go.Figure()
    if borders:
        fig.add_trace(go.Scattergeo(
            lon=borders[0], lat=borders[1], mode="lines",
            line=dict(width=0.6, color=STATE_BORDER_COLOR), name="State borders",
            showlegend=False, hoverinfo="skip",
        ))
    seen = set()
    if len(routes):
        for sid, grp in routes.sort_values(["shipment_id", "stop_order"]).groupby("shipment_id", sort=True):
            carrier = grp["carrier"].iloc[0]
            color = carrier_color_dark(carrier)
            lats, lons = build_route_path(list(zip(grp["lat"], grp["lon"])))
            is_hl = highlight_id is not None and sid == highlight_id
            dim = highlight_id is not None and not is_hl
            fig.add_trace(go.Scattergeo(
                lat=lats, lon=lons, mode="lines",
                line=dict(width=4 if is_hl else 1.6, color=color),
                opacity=0.3 if dim else 0.9,
                name=carrier, legendgroup=carrier,
                showlegend=carrier not in seen, hoverinfo="skip",
            ))
            seen.add(carrier)

    if len(hotspots):
        out = hotspots[hotspots["outgoing"] > 0]
        inc = hotspots[hotspots["incoming"] > 0]
        fig.add_trace(go.Scattergeo(
            lat=out["lat"], lon=out["lon"], mode="markers",
            marker=dict(size=[outgoing_size(o, i) for o, i in zip(out["outgoing"], out["incoming"])],
                        color="rgba(0,0,0,0)", line=dict(width=2, color=OUTGOING_COLOR)),
            text=[_hotspot_hover(h) for h in out.itertuples()],
            hovertemplate="%{text}<extra></extra>",
            name="Outgoing (blue ring)", showlegend=True,
        ))
        fig.add_trace(go.Scattergeo(
            lat=inc["lat"], lon=inc["lon"], mode="markers",
            marker=dict(size=[incoming_size(i) for i in inc["incoming"]],
                        color=INCOMING_COLOR, opacity=0.85, line=dict(width=0)),
            text=[_hotspot_hover(h) for h in inc.itertuples()],
            hovertemplate="%{text}<extra></extra>",
            name="Incoming (red)", showlegend=True,
        ))

    fig.update_geos(
        projection_type="natural earth", bgcolor=BG,
        showland=True, landcolor=BG, showocean=True, oceancolor=BG, showlakes=False,
        showcoastlines=True, coastlinecolor="#FFFFFF", coastlinewidth=0.8,
        showcountries=True, countrycolor="#9A9A9A", countrywidth=0.6,
        showframe=False, fitbounds=False, projection_scale=1,
        lonaxis_range=list(lon_range), lataxis_range=list(lat_range),
    )
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=44, b=0),
        paper_bgcolor=BG, plot_bgcolor=BG,
        # Horizontal legend in its own strip above the map, so it never covers the routes.
        legend=dict(orientation="h", x=0.0, y=1.0, xanchor="left", yanchor="bottom",
                    bgcolor="rgba(0,0,0,0)", font=dict(color="#FFFFFF", size=12),
                    itemsizing="constant"),
        hoverlabel=dict(bgcolor="#111111", font=dict(color="#FFFFFF")),
    )
    return fig
