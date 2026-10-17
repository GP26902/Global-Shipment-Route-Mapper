from modules.data_model import CARRIER_COLORS, empty_frame
from modules.map_figure import build_map_figure
from modules.routes import great_circle_points
from modules.seed import get_seed_frame


def test_one_line_and_one_marker_trace_per_route():
    fig = build_map_figure(get_seed_frame())
    lines = [t for t in fig.data if t.mode == "lines"]
    markers = [t for t in fig.data if t.mode == "markers"]
    assert len(lines) == 15 and len(markers) == 15


def test_carrier_colours_applied_and_legend_once_per_carrier():
    fig = build_map_figure(get_seed_frame())
    for t in fig.data:
        if t.mode == "lines":
            assert t.line.color == CARRIER_COLORS[t.name]
    legend = [t.name for t in fig.data if t.showlegend]
    assert sorted(legend) == sorted(CARRIER_COLORS) and len(legend) == len(set(legend))


def test_hover_labels_stops_as_illustrative():
    fig = build_map_figure(get_seed_frame())
    marker = [t for t in fig.data if t.mode == "markers"][0]
    assert "illustrative" in marker.text[0] and "Stop 1 of" in marker.text[0]


def test_arcs_are_curved_not_straight_segments():
    fig = build_map_figure(get_seed_frame())
    line = [t for t in fig.data if t.mode == "lines"][0]
    assert len(line.lat) > 5 * 5  # far more vertices than the 5 stops


def test_empty_frame_gives_empty_map():
    assert len(build_map_figure(empty_frame()).data) == 0


def test_no_dateline_wrap_in_any_seed_route():
    fig = build_map_figure(get_seed_frame())
    for t in fig.data:
        if t.mode == "lines":
            lons = list(t.lon)
            for a, b in zip(lons[:-1], lons[1:]):
                if a is not None and b is not None:
                    assert abs(a - b) <= 180
