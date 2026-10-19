"""Build data/admin1_borders.json (state and province borders) from Natural Earth.

Run once by hand when the border data needs refreshing. The app itself never runs this:
it only reads the finished JSON file.

    pip install shapely
    curl -L -o ne_10m_admin_1_states_provinces.geojson \
      https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_1_states_provinces.geojson
    python tools/build_admin1_borders.py ne_10m_admin_1_states_provinces.geojson data/admin1_borders.json

Source: Natural Earth (naturalearthdata.com), public domain.
Output: {"US": [[[lon, lat], ...], ...], ...}, one ring per state outline part, keyed by ISO alpha-2,
simplified to about 2 km and rounded to 2 decimals so the file stays small.
"""
import json
import sys

from shapely.geometry import shape

TOLERANCE_DEG = 0.02


def build(src: str, dst: str) -> None:
    with open(src, encoding="utf-8") as fh:
        features = json.load(fh)["features"]
    out = {}
    for f in features:
        p = f["properties"]
        code = p.get("iso_a2")
        if code in (None, "", "-99"):                     # Natural Earth leaves a few (e.g. France) unset
            code = (p.get("iso_3166_2") or "")[:2]
        if len(code) != 2:
            continue
        geom = shape(f["geometry"]).simplify(TOLERANCE_DEG, preserve_topology=True)
        if geom.is_empty:
            continue
        parts = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        for poly in parts:
            ring = [[round(x, 2), round(y, 2)] for x, y in poly.exterior.coords]
            if len(ring) >= 4:
                out.setdefault(code, []).append(ring)
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print(f"{len(out)} countries, {sum(len(v) for v in out.values())} rings -> {dst}")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
