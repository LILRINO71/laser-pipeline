"""Sheet geometry -> cut/engrave paths, part labels, DXF, SVG and an HTML preview."""

from __future__ import annotations

import html
import math
from pathlib import Path

from shapely import affinity
from shapely.geometry import box
from shapely.ops import polylabel

try:
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath

    _FONT = FontProperties(family="DejaVu Sans", weight="bold")
except Exception:  # labels are optional
    TextPath = None


def _label_paths(text: str, region, heights=(6.0, 5.0, 4.0, 3.0, 2.5)):
    """Outline text that fits inside region (a shapely polygon). Returns list of closed polylines."""
    if TextPath is None or region.is_empty:
        return []
    try:
        start = polylabel(region, tolerance=0.5)
    except Exception:
        start = region.representative_point()
    x0, y0, x1, y1 = region.bounds
    cands = [(start.x, start.y)] + [
        (x0 + (x1 - x0) * i / 8, y0 + (y1 - y0) * j / 8) for i in range(1, 8) for j in range(1, 8)
    ]
    cands.sort(key=lambda c: math.hypot(c[0] - start.x, c[1] - start.y))
    for h in heights:
        tp = TextPath((0, 0), text, size=h / 0.72, prop=_FONT)  # cap height ~ h
        ext = tp.get_extents()
        bx0, by0, bx1, by1 = ext.x0, ext.y0, ext.x1, ext.y1
        tw, th = bx1 - bx0, by1 - by0
        for cx, cy in cands:
            for rot in (0, 90):
                w, hh = (tw, th) if rot == 0 else (th, tw)
                if region.contains(box(cx - w / 2, cy - hh / 2, cx + w / 2, cy + hh / 2)):
                    out = []
                    for poly in tp.to_polygons(closed_only=True):
                        pts = [(px - bx0 - tw / 2, py - by0 - th / 2) for px, py in poly]
                        if rot:
                            pts = [(-py, px) for px, py in pts]
                        out.append([(cx + px, cy + py) for px, py in pts])
                    return out
    return []


def sheet_paths(sheet, labels=True):
    """Returns (cut_loops, engrave_loops). Holes come before each part's outline so plates don't shift."""
    cuts, marks = [], []
    for pl in sheet.placements:
        s = pl.shape()
        for ring in s.interiors:
            cuts.append(list(ring.coords))
        cuts.append(list(s.exterior.coords))
        if labels:
            name = pl.part.name if pl.part.qty == 1 else f"{pl.part.name} ({pl.copy + 1})"
            region = s.buffer(-1.5)
            if region.geom_type == "MultiPolygon":
                region = max(region.geoms, key=lambda g: g.area)
            marks += _label_paths(name[:28], region)
    return cuts, marks


def write_dxf(path: Path, sheet, cuts, marks):
    import ezdxf

    doc = ezdxf.new("R2010", setup=False)
    doc.header["$INSUNITS"] = 4  # mm
    doc.layers.add("CUT", color=1)
    doc.layers.add("ENGRAVE", color=5)
    doc.layers.add("SHEET", color=8)
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (sheet.w, 0), (sheet.w, sheet.h), (0, sheet.h)], close=True, dxfattribs={"layer": "SHEET"})
    for lp in cuts:
        msp.add_lwpolyline(lp, close=True, dxfattribs={"layer": "CUT", "color": 1})
    for lp in marks:
        msp.add_lwpolyline(lp, close=True, dxfattribs={"layer": "ENGRAVE", "color": 5})
    doc.saveas(path)


def svg(sheet, cuts, marks, cut_rgb, mark_rgb, stroke=0.35, used=()) -> str:
    def d(lp):
        return "M" + " L".join(f"{x:.3f},{sheet.h - y:.3f}" for x, y in lp) + " Z"

    c = "#%02x%02x%02x" % tuple(cut_rgb)
    m = "#%02x%02x%02x" % tuple(mark_rgb)
    body = [f'<rect x="0" y="0" width="{sheet.w:.2f}" height="{sheet.h:.2f}" class="sheet"/>']
    for u in used:  # wood other jobs already cut
        dd = " ".join(d(list(g.exterior.coords)) for g in getattr(u, "geoms", [u]) if hasattr(g, "exterior"))
        body.append(f'<path d="{dd}" class="used"/>')
    body.append(f'<path d="{" ".join(d(lp) for lp in cuts)}" fill="none" stroke="{c}" stroke-width="{stroke}" fill-rule="evenodd"/>')
    if marks:
        body.append(f'<path d="{" ".join(d(lp) for lp in marks)}" fill="none" stroke="{m}" stroke-width="{stroke * 0.6}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-2 -2 {sheet.w + 4:.2f} {sheet.h + 4:.2f}" '
            f'width="{sheet.w:.2f}mm" height="{sheet.h:.2f}mm">{"".join(body)}</svg>')


def cut_length(loops) -> float:
    return sum(math.dist(a, b) for lp in loops for a, b in zip(lp, lp[1:] + lp[:1]))


def preview_html(job: str, source: str, sheets_svg: list, parts, too_big, stats: list, settings: dict, notes=()) -> str:
    rows = "".join(
        f"<tr><td>{html.escape(p.name)}</td><td>{p.qty}</td><td>{p.size[0]:.1f} × {p.size[1]:.1f}</td>"
        f"<td>{p.thickness:.2f}</td><td>{html.escape('; '.join(p.warnings)) or '—'}</td></tr>" for p in parts)
    big = "".join(f"<li>{html.escape(p.name)} ({p.size[0]:.0f} × {p.size[1]:.0f} mm) is bigger than the sheet</li>" for p in too_big)
    big += "".join(f"<li>{html.escape(n)}</li>" for n in notes)
    cards = "".join(
        f'<section class="card"><h2>Sheet {i + 1} <span>{st["parts"]} parts · {st["cut_m"]:.2f} m of cut · '
        f'{st["fill"]:.0f}% used · {"LOAD NEW WOOD" if st.get("new_wood") else "wood in the laser now"}</span></h2>'
        + "".join(f'<p class="warn">BLOCKED: {html.escape(e)}</p>' for e in st.get("errors", []))
        + f'<div class="sv">{s}</div></section>' for i, (s, st) in enumerate(zip(sheets_svg, stats)))
    setting = " · ".join(f"{k}: {html.escape(str(v))}" for k, v in settings.items())
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(job)} laser job</title><style>
:root{{--bg:#f6f5f2;--fg:#1d1d1b;--mut:#6b6a66;--card:#fff;--line:#e3e1dc;--wood:#f1e3c8}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161614;--fg:#eceae4;--mut:#9a988f;--card:#20201d;--line:#34332e;--wood:#3a3022}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,Segoe UI,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px}} h1{{margin:0 0 4px;font-size:24px}}
.mut{{color:var(--mut)}} .card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:16px 0}}
h2{{margin:0 0 10px;font-size:17px}} h2 span{{font-weight:400;color:var(--mut);font-size:14px;margin-left:8px}}
.sv svg{{width:100%;height:auto;display:block}} .sheet{{fill:var(--wood);stroke:var(--mut);stroke-width:.4}} .used{{fill:var(--mut);opacity:.45}}
table{{width:100%;border-collapse:collapse;font-size:14px}} td,th{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}}
.warn{{color:#b3261e}} code{{font-size:13px}}</style></head><body><main>
<h1>{html.escape(job)}</h1><div class="mut">{html.escape(source)}</div><div class="mut">{setting}</div>
{f'<ul class="warn">{big}</ul>' if big else ''}
{cards}
<section class="card"><h2>Parts</h2><table><tr><th>Part</th><th>Qty</th><th>Size (mm)</th><th>Thickness</th><th>Notes</th></tr>{rows}</table></section>
<p class="mut">Red = cut through. Blue = vector score (part name). Grey = wood other jobs already used. Holes are cut before outlines.</p>
</main></body></html>"""
