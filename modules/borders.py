"""State and province border lines for the drill-down map. No Streamlit dependency.

Data: data/admin1_borders.json, built by tools/build_admin1_borders.py from Natural Earth
(public domain). Borders are drawn for the chosen country only.
"""
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from modules.locations import country_code

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "admin1_borders.json"
Lines = Tuple[List[Optional[float]], List[Optional[float]]]


@lru_cache(maxsize=1)
def _load() -> Dict[str, list]:
    try:
        with open(DATA_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}          # missing or unreadable file: the map simply has no state borders


def border_lines(country: Optional[str]) -> Optional[Lines]:
    """(lons, lats) for one Plotly line trace, with None between outlines. None if unavailable."""
    code = country_code(country)
    rings = _load().get(code or "")
    if not rings:
        return None
    lons: List[Optional[float]] = []
    lats: List[Optional[float]] = []
    for ring in rings:
        lons.extend(pt[0] for pt in ring)
        lats.extend(pt[1] for pt in ring)
        lons.append(None)
        lats.append(None)
    return lons, lats


_JOIN_GAP_DEG = 1.5      # outlines closer than this belong to the same landmass
_PAD_FRACTION = 0.06


@lru_cache(maxsize=None)
def country_extent(country: Optional[str]):
    """Map frame ((lon_min, lon_max), (lat_min, lat_max)) for the country's main landmass.

    Far-away outlying parts (US Alaska and Hawaii, French overseas regions) are left out, so the
    frame shows the country itself. None if there is no border data.
    """
    rings = _load().get(country_code(country) or "")
    if not rings:
        return None
    boxes = [(min(p[0] for p in r), min(p[1] for p in r), max(p[0] for p in r), max(p[1] for p in r))
             for r in rings]
    parent = list(range(len(boxes)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    g = _JOIN_GAP_DEG
    for i, a in enumerate(boxes):
        for j in range(i + 1, len(boxes)):
            b = boxes[j]
            if a[0] - g <= b[2] and b[0] - g <= a[2] and a[1] - g <= b[3] and b[1] - g <= a[3]:
                parent[find(i)] = find(j)
    weight: Dict[int, float] = {}
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        area = (x1 - x0) * (y1 - y0) * max(math.cos(math.radians((y0 + y1) / 2)), 0.1)
        weight[find(i)] = weight.get(find(i), 0.0) + area
    core = max(weight, key=weight.get)
    sel = [b for i, b in enumerate(boxes) if find(i) == core]
    x0, y0 = min(b[0] for b in sel), min(b[1] for b in sel)
    x1, y1 = max(b[2] for b in sel), max(b[3] for b in sel)
    px, py = max((x1 - x0) * _PAD_FRACTION, 0.5), max((y1 - y0) * _PAD_FRACTION, 0.5)
    return ((max(x0 - px, -180.0), min(x1 + px, 180.0)), (max(y0 - py, -90.0), min(y1 + py, 90.0)))
