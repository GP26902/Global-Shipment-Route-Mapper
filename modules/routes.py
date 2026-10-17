"""Great-circle arc maths. No Streamlit or Plotly dependency."""
import math
from typing import List, Optional, Sequence, Tuple

Point = Tuple[float, float]  # (lat, lon)


def _to_unit(lat: float, lon: float) -> Tuple[float, float, float]:
    la, lo = math.radians(lat), math.radians(lon)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def great_circle_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def great_circle_points(lat1: float, lon1: float, lat2: float, lon2: float,
                        step_deg: float = 2.0) -> List[Point]:
    """Points along the great circle from A to B (inclusive), about step_deg apart."""
    a, b = _to_unit(lat1, lon1), _to_unit(lat2, lon2)
    dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))
    omega = math.acos(dot)
    if omega < 1e-9:
        return [(lat1, lon1)]
    n = max(2, int(math.degrees(omega) / step_deg) + 1)
    s = math.sin(omega)
    pts: List[Point] = []
    for i in range(n + 1):
        t = i / n
        if s < 1e-9:  # antipodal: no unique great circle, fall back to linear
            pts.append((lat1 + t * (lat2 - lat1), lon1 + t * (lon2 - lon1)))
            continue
        ka, kb = math.sin((1 - t) * omega) / s, math.sin(t * omega) / s
        x, y, z = (ka * a[j] + kb * b[j] for j in range(3))
        pts.append((math.degrees(math.asin(max(-1.0, min(1.0, z)))),
                    math.degrees(math.atan2(y, x))))
    pts[0], pts[-1] = (lat1, lon1), (lat2, lon2)  # exact endpoints
    return pts


def split_antimeridian(points: Sequence[Point]) -> Tuple[List[Optional[float]], List[Optional[float]]]:
    """Return (lats, lons) with None breaks so lines never wrap across the map."""
    lats: List[Optional[float]] = []
    lons: List[Optional[float]] = []
    prev: Optional[Point] = None
    for lat, lon in points:
        if prev is not None and abs(lon - prev[1]) > 180:
            plat, plon = prev
            lon_u = lon + 360 if lon < plon else lon - 360
            edge = 180.0 if lon_u > plon else -180.0
            clat = plat + (edge - plon) / (lon_u - plon) * (lat - plat)
            lats += [clat, None, clat]
            lons += [edge, None, -edge]
        lats.append(lat)
        lons.append(lon)
        prev = (lat, lon)
    return lats, lons


BOW_BELOW_KM = 1500.0


def bowed_points(lat1: float, lon1: float, lat2: float, lon2: float,
                 bow: float = 0.3, n: int = 24) -> List[Point]:
    """Quadratic curve that bows to the LEFT of travel, so A->B and B->A separate.
    Used for short hops, where a true great circle looks like a straight line."""
    k = max(math.cos(math.radians((lat1 + lat2) / 2)), 0.1)
    x1, y1, x2, y2 = lon1 * k, lat1, lon2 * k, lat2
    dx, dy = x2 - x1, y2 - y1
    cx, cy = (x1 + x2) / 2 - bow * dy, (y1 + y2) / 2 + bow * dx
    pts: List[Point] = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * cx + t ** 2 * x2
        y = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * cy + t ** 2 * y2
        pts.append((y, x / k))
    pts[0], pts[-1] = (lat1, lon1), (lat2, lon2)
    return pts


def build_route_path(stops: Sequence[Point], step_deg: float = 2.0):
    """Curved multi-stop path through stops in order -> (lats, lons) with None breaks.
    Long hops follow the great circle; short hops (< 1500 km) get a visible bow."""
    if not stops:
        return [], []
    pts: List[Point] = [stops[0]]
    for (la1, lo1), (la2, lo2) in zip(stops[:-1], stops[1:]):
        d = great_circle_km(la1, lo1, la2, lo2)
        if 0 < d < BOW_BELOW_KM and abs(lo2 - lo1) <= 180:
            seg = bowed_points(la1, lo1, la2, lo2, n=max(8, min(40, int(d / 25))))
        else:
            seg = great_circle_points(la1, lo1, la2, lo2, step_deg)
        pts.extend(seg[1:])
    return split_antimeridian(pts)
