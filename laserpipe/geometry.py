"""Turn Onshape face edges into clean shapely polygons (outline + holes) in mm."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from shapely import affinity
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

CHORD_TOL = 0.002  # mm, max gap between a true arc and its polyline (laser resolution is 0.025 mm)


@dataclass
class Part:
    name: str
    poly: Polygon  # outline with holes, mm, placed so min corner is (0, 0)
    thickness: float
    qty: int = 1
    warnings: list = field(default_factory=list)

    @property
    def size(self):
        x0, y0, x1, y1 = self.poly.bounds
        return x1 - x0, y1 - y0


def _arc_points(e: dict) -> list:
    (cx, cy), r = e["c"], e["r"]
    p = e["p"]
    a0 = math.atan2(p[0][1] - cy, p[0][0] - cx)
    # direction from the first quarter sample (always < 180 deg away)
    v0 = (p[0][0] - cx, p[0][1] - cy)
    v1 = (p[1][0] - cx, p[1][1] - cy)
    sign = 1.0 if v0[0] * v1[1] - v0[1] * v1[0] >= 0 else -1.0
    sweep = min(e["len"] / r, 2 * math.pi)
    step = 2 * math.acos(max(-1.0, 1 - CHORD_TOL / r)) if r > CHORD_TOL else math.pi / 4
    n = max(8, math.ceil(sweep / step))
    pts = [(cx + r * math.cos(a0 + sign * sweep * i / n), cy + r * math.sin(a0 + sign * sweep * i / n)) for i in range(n + 1)]
    pts[0], pts[-1] = tuple(p[0]), tuple(p[-1])  # snap ends to Onshape's exact vertices
    return pts


def edge_points(e: dict) -> list:
    if e["t"] == "C" and e.get("r"):
        return _arc_points(e)
    return [tuple(q) for q in e["p"]]


def _close(a, b, tol):
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def chain_loops(edges: list, tol: float = 0.02) -> tuple[list, int]:
    """Join edges end to end into closed loops. Returns (loops, edges_left_over)."""
    segs = [edge_points(e) for e in edges]
    loops, open_ = [], []
    for s in segs:
        (loops if len(s) > 2 and _close(s[0], s[-1], tol) else open_).append(s)
    while open_:
        cur = list(open_.pop(0))
        grew = True
        while grew and not _close(cur[0], cur[-1], tol):
            grew = False
            for i, s in enumerate(open_):
                if _close(cur[-1], s[0], tol):
                    cur += s[1:]
                elif _close(cur[-1], s[-1], tol):
                    cur += s[::-1][1:]
                else:
                    continue
                open_.pop(i)
                grew = True
                break
        if _close(cur[0], cur[-1], tol) and len(cur) > 3:
            loops.append(cur)
        else:
            return loops, len(open_) + 1
    return loops, 0


def min_area_rotation(poly: Polygon) -> float:
    """Angle (deg) that lines the part's minimum bounding rectangle up with X, long side along X."""
    rect = poly.minimum_rotated_rectangle
    c = list(rect.exterior.coords)
    e1 = (c[1][0] - c[0][0], c[1][1] - c[0][1])
    e2 = (c[2][0] - c[1][0], c[2][1] - c[1][1])
    long_ = e1 if math.hypot(*e1) >= math.hypot(*e2) else e2
    return -math.degrees(math.atan2(long_[1], long_[0]))


def build_part(raw: dict, kerf: float = 0.0) -> Part:
    loops, left = chain_loops(raw["edges"])
    warnings = []
    if raw.get("volume") and raw.get("thk") and raw.get("area"):
        ratio = raw["volume"] / (raw["area"] * raw["thk"])
        if ratio < 0.97:
            warnings.append(f"not a flat plate ({ratio:.0%} solid): pockets, steps or chamfers will be cut straight through")
    if left:
        warnings.append(f"{left} edge(s) didn't join into a closed loop and were skipped")
    if not loops:
        raise ValueError(f"{raw['name']}: no closed outline found")
    polys = [make_valid(Polygon(lp)) for lp in loops]
    polys = [p for p in polys if p.area > 1e-3]
    polys.sort(key=lambda p: p.area, reverse=True)
    outer = polys[0]
    holes = [p for p in polys[1:] if outer.contains(p.representative_point())]
    if len(holes) != len(polys) - 1:
        warnings.append(f"{len(polys) - 1 - len(holes)} loop(s) sat outside the outline and were ignored")
    shape = outer.difference(unary_union(holes)) if holes else outer
    if shape.geom_type != "Polygon":
        shape = max(shape.geoms, key=lambda g: g.area)
    if kerf:
        # the beam removes material: grow the outline and shrink every hole by half the kerf
        shape = shape.buffer(kerf / 2, join_style="mitre", mitre_limit=2.0)
    shape = affinity.rotate(shape, min_area_rotation(shape), origin="centroid")
    x0, y0, _, _ = shape.bounds
    shape = affinity.translate(shape, -x0, -y0)
    return Part(raw["name"], shape, raw.get("thk") or 0.0, 1, warnings)
