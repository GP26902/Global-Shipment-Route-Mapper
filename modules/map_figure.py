"""Builds the Plotly route map. Plotly only, no Streamlit."""
import pandas as pd
import plotly.graph_objects as go

from modules.data_model import carrier_color, data_label
from modules.routes import build_route_path


def _hover(row, n_stops: int) -> str:
    return (
        f"<b>Stop {int(row.stop_order)} of {n_stops} · {row.stage_type}</b><br>"
        f"{row.city}, {row.state}, {row.country}<br>"
        f"{row.carrier} · {row.product_class}<br>"
        f"{row.shipment_id} · {data_label(row.source)}"
    )


def build_map_figure(df: pd.DataFrame, height: int = 620, highlight_id=None) -> go.Figure:
    """One curved arc trace plus one marker trace per shipment, coloured by carrier.

    highlight_id draws that shipment thicker and fades the others.
    """
    fig = go.Figure()
    seen_carriers = set()
    if len(df):
        for sid, grp in df.sort_values(["shipment_id", "stop_order"]).groupby("shipment_id", sort=True):
            carrier = grp["carrier"].iloc[0]
            color = carrier_color(carrier)
            lats, lons = build_route_path(list(zip(grp["lat"], grp["lon"])))
            is_hl = highlight_id is not None and sid == highlight_id
            dim = highlight_id is not None and not is_hl
            first_of_carrier = carrier not in seen_carriers
            seen_carriers.add(carrier)
            fig.add_trace(go.Scattergeo(
                lat=lats, lon=lons, mode="lines",
                line=dict(width=5 if is_hl else 2, color=color),
                opacity=0.35 if dim else 1.0,
                name=carrier, legendgroup=carrier,
                showlegend=first_of_carrier, hoverinfo="skip",
            ))
            n = len(grp)
            fig.add_trace(go.Scattergeo(
                lat=grp["lat"], lon=grp["lon"], mode="markers",
                marker=dict(
                    size=[(10 if s in ("Origin", "Final Destination") else 6) + (4 if is_hl else 0)
                          for s in grp["stage_type"]],
                    symbol=["diamond" if s == "Final Destination" else "circle" for s in grp["stage_type"]],
                    color=color, line=dict(width=1, color="white"),
                ),
                text=[_hover(r, n) for r in grp.itertuples()],
                hovertemplate="%{text}<extra></extra>",
                name=carrier, legendgroup=carrier, showlegend=False,
            ))
    fig.update_geos(
        projection_type="natural earth",
        showland=True, landcolor="#EEF1F4",
        showocean=True, oceancolor="#DCE9F5",
        showcountries=True, countrycolor="#B8C0CC",
        coastlinecolor="#9AA5B5", showframe=False,
        # Fixed world view: never auto-zoom to the data extent.
        fitbounds=False, projection_scale=1,
        lonaxis_range=[-180, 180], lataxis_range=[-60, 85],
    )
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=0.0, xanchor="left", x=0.0,
                    bgcolor="rgba(255,255,255,0.7)"),
        template="plotly_white",
    )
    return fig
