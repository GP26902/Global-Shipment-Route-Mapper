import math

from modules.data_model import (
    CARRIER_COLORS_DARK, INCOMING_COLOR, OUTGOING_COLOR, empty_frame, visible_frame,
)
from modules.hotspots import compute_hotspots
from modules.map_figure import build_map_figure, incoming_size, outgoing_size
from modules.seed import get_seed_frame


def fig_for(df=None, **kw):
    df = get_seed_frame() if df is None else df
    return build_map_figure(df, compute_hotspots(df), **kw)


def test_one_line_trace_per_route_in_dark_carrier_colours():
    fig = fig_for()
    lines = [t for t in fig.data if t.mode == "lines"]
    assert len(lines) == 20
    for t in lines:
        assert t.line.color == CARRIER_COLORS_DARK[t.name]


def test_legend_one_entry_per_carrier_plus_hotspot_keys():
    fig = fig_for()
    legend = [t.name for t in fig.data if t.showlegend]
    assert sorted(n for n in legend if n in CARRIER_COLORS_DARK) == sorted(CARRIER_COLORS_DARK)
    assert "Incoming (red)" in legend and "Outgoing (blue ring)" in legend
    assert len(legend) == len(set(legend))


def test_legend_is_horizontal_and_sits_above_the_map():
    fig = fig_for()
    assert fig.layout.legend.orientation == "h" and fig.layout.legend.yanchor == "bottom"
    assert fig.layout.margin.t >= 30


def test_hotspots_red_circles_and_blue_rings():
    fig = fig_for()
    red = [t for t in fig.data if t.name == "Incoming (red)"][0]
    ring = [t for t in fig.data if t.name == "Outgoing (blue ring)"][0]
    assert red.marker.color == INCOMING_COLOR
    assert ring.marker.line.color == OUTGOING_COLOR and ring.marker.color == "rgba(0,0,0,0)"
    assert "Incoming:" in red.text[0] and "illustrative" in red.text[0]


def test_origins_have_only_a_ring_and_final_destinations_only_red():
    df = get_seed_frame()
    hs = compute_hotspots(df)
    fig = build_map_figure(df, hs)
    red = [t for t in fig.data if t.name == "Incoming (red)"][0]
    ring = [t for t in fig.data if t.name == "Outgoing (blue ring)"][0]
    assert len(red.lat) == (hs["incoming"] > 0).sum()
    assert len(ring.lat) == (hs["outgoing"] > 0).sum()
    assert len(red.lat) < len(hs) or len(ring.lat) < len(hs)


def test_marker_sizes_grow_with_count_and_ring_clears_circle():
    assert incoming_size(1) < incoming_size(4) < incoming_size(9)
    assert outgoing_size(1) < outgoing_size(9)
    for i in range(0, 30):
        assert outgoing_size(1, i) >= incoming_size(i) + 6 or outgoing_size(1, i) == 50


def test_black_background_white_coastlines():
    fig = fig_for()
    assert fig.layout.paper_bgcolor == "#000000"
    g = fig.layout.geo
    assert g.bgcolor == "#000000" and g.coastlinecolor == "#FFFFFF" and g.landcolor == "#000000"


def test_view_ranges_default_to_world_and_follow_arguments():
    g = fig_for().layout.geo
    assert g.fitbounds is False and tuple(g.lonaxis.range) == (-180, 180)
    g2 = fig_for(lon_range=(-100, -90), lat_range=(26, 34)).layout.geo
    assert tuple(g2.lonaxis.range) == (-100, -90) and tuple(g2.lataxis.range) == (26, 34)


def test_highlight_thickens_one_route_and_fades_others():
    lines = [t for t in fig_for(highlight_id="SEED-004").data if t.mode == "lines"]
    assert sum(1 for t in lines if t.line.width == 4) == 1
    assert all(t.opacity == 0.3 for t in lines if t.line.width != 4)


def test_no_dateline_wrap_in_any_route():
    for t in fig_for().data:
        if t.mode == "lines":
            lons = list(t.lon)
            for a, b in zip(lons[:-1], lons[1:]):
                if a is not None and b is not None:
                    assert abs(a - b) <= 180


def test_empty_frames_give_empty_dark_map():
    fig = build_map_figure(empty_frame(), compute_hotspots(empty_frame()))
    assert len(fig.data) == 0 and fig.layout.paper_bgcolor == "#000000"


def test_visible_frame_excludes_deleted_and_respects_toggle():
    seed = get_seed_frame()
    user = seed.head(3).copy()
    user["shipment_id"], user["source"], user["status"] = "SHP-X", "user", "approved"
    assert visible_frame(seed, [user], True)["shipment_id"].nunique() == 21
    assert visible_frame(seed, [user], False)["shipment_id"].nunique() == 1
    user["status"] = "deleted"
    assert visible_frame(seed, [user], False).empty
    assert visible_frame(seed, [], False).empty
