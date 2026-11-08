"""Read plates from files exported by hand from Onshape. No API anywhere.

STEP  (best): right-click the Part Studio tab > Export > STEP. Every part comes in with its name,
              and the real 3D solid lets us measure thickness and catch pockets that aren't through.
DXF / DWG-as-DXF: right-click a plate's face > Export as DXF, or a drawing exported as DXF.
              Closed loops are grouped into parts (outline + holes). Text, dimensions, open lines ignored.

Both return "raw" part dicts: {name, thk, area, edges:[{t, p, c?, r?, len}], volume?, source}
in the same 2D-mm format that geometry.build_part() consumes.
"""

from __future__ import annotations

import math
from pathlib import Path

# ----------------------------------------------------------------------------- STEP


def _step_named_solids(path: Path):
    """Yield (name, TopoDS_Solid) using the STEP product/part names (Onshape writes part names there)."""
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDF import TDF_Label, TDF_LabelSequence
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    doc = TDocStd_Document(TCollection_ExtendedString("doc"))
    rd = STEPCAFControl_Reader()
    rd.SetNameMode(True)
    if rd.ReadFile(str(path)) != IFSelect_RetDone:
        raise ValueError(f"{path.name}: not a readable STEP file")
    rd.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

    def name_of(lab):
        attr = TDataStd_Name()
        if lab.FindAttribute(TDataStd_Name.GetID_s(), attr):
            return attr.Get().ToExtString()
        return ""

    out = []

    def walk(lab, loc, parent_name):
        nm = name_of(lab) or parent_name
        if st.IsReference_s(lab):
            ref = TDF_Label()
            st.GetReferredShape_s(lab, ref)
            walk(ref, loc.Multiplied(st.GetLocation_s(lab)), name_of(lab) or name_of(ref) or parent_name)
            return
        if st.IsAssembly_s(lab):
            kids = TDF_LabelSequence()
            st.GetComponents_s(lab, kids)
            for i in range(1, kids.Length() + 1):
                walk(kids.Value(i), loc, nm)
            return
        shape = st.GetShape_s(lab).Moved(loc)
        exp = TopExp_Explorer(shape, TopAbs_SOLID)
        solids = []
        while exp.More():
            solids.append(TopoDS.Solid_s(exp.Current()))
            exp.Next()
        for i, s in enumerate(solids):
            out.append((nm if len(solids) == 1 else f"{nm} {i + 1}", s))

    roots = TDF_LabelSequence()
    st.GetFreeShapes(roots)
    for i in range(1, roots.Length() + 1):
        walk(roots.Value(i), TopLoc_Location(), path.stem)
    return out


def read_step(path: Path) -> list:
    from build123d import GeomType, Plane, Solid

    raws = []
    for n, (name, occ_solid) in enumerate(_step_named_solids(path)):
        solid = Solid(occ_solid)
        planes = [f for f in solid.faces() if f.geom_type == GeomType.PLANE]
        if not planes:
            continue
        face = max(planes, key=lambda f: f.area)
        pl = Plane(face)
        loc = pl.to_local_coords(solid).bounding_box()
        thk = loc.max.Z - loc.min.Z
        edges = []
        for e in face.edges():
            ln = e.length
            pts = [pl.to_local_coords(e.position_at(t)) for t in ((0, 1) if e.geom_type == GeomType.LINE else
                   [i / 4 for i in range(5)] if e.geom_type == GeomType.CIRCLE else
                   [i / (min(400, 3 + int(ln)) - 1) for i in range(min(400, 3 + int(ln)))])]
            rec = {"t": "S", "len": ln, "p": [[p.X, p.Y] for p in pts]}
            if e.geom_type == GeomType.LINE:
                rec["t"] = "L"
            elif e.geom_type == GeomType.CIRCLE:
                c = pl.to_local_coords(e.arc_center)
                rec.update(t="C", c=[c.X, c.Y], r=e.radius)
            edges.append(rec)
        raws.append({"name": name or f"{path.stem} {n + 1}", "thk": thk, "area": face.area,
                     "volume": solid.volume, "edges": edges, "source": path.name})
    return raws


# ----------------------------------------------------------------------------- DXF

_UNITS = {1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0}


def read_dxf(path: Path, units: str | None = None) -> tuple[list, list]:
    """Returns (raw parts, warnings)."""
    import ezdxf
    from ezdxf import path as ezpath
    from shapely.geometry import Polygon

    from .geometry import chain_loops

    doc = ezdxf.readfile(str(path))
    warns = []
    if units:
        k = 25.4 if units == "in" else 1.0
    else:
        code = doc.header.get("$INSUNITS", 0)
        k = _UNITS.get(code, 1.0)
        if code not in _UNITS:
            warns.append(f"{path.name}: DXF has no units, assuming mm (use --dxf-units in if it's inches)")
    edges = []
    for e in doc.modelspace():
        kind = e.dxftype()
        try:
            if kind == "CIRCLE":
                c, r = e.dxf.center, e.dxf.radius
                pts = [(c.x + r * math.cos(a), c.y + r * math.sin(a)) for a in (2 * math.pi * i / 4 for i in range(5))]
                edges.append({"t": "C", "c": [c.x * k, c.y * k], "r": r * k, "len": 2 * math.pi * r * k,
                              "p": [[x * k, y * k] for x, y in pts]})
            elif kind == "ARC":
                c, r = e.dxf.center, e.dxf.radius
                a0, a1 = math.radians(e.dxf.start_angle), math.radians(e.dxf.end_angle)
                if a1 <= a0:
                    a1 += 2 * math.pi
                pts = [(c.x + r * math.cos(a0 + (a1 - a0) * i / 4), c.y + r * math.sin(a0 + (a1 - a0) * i / 4)) for i in range(5)]
                edges.append({"t": "C", "c": [c.x * k, c.y * k], "r": r * k, "len": (a1 - a0) * r * k,
                              "p": [[x * k, y * k] for x, y in pts]})
            elif kind in ("LINE", "LWPOLYLINE", "POLYLINE", "SPLINE", "ELLIPSE"):
                pts = [(v.x * k, v.y * k) for v in ezpath.make_path(e).flattening(0.005 / k if k else 0.005)]
                if kind in ("LWPOLYLINE", "POLYLINE") and e.is_closed and pts and pts[0] != pts[-1]:
                    pts.append(pts[0])
                if len(pts) >= 2:
                    edges.append({"t": "S", "p": [list(p) for p in pts], "len": 0})
        except Exception:
            continue
    loops, left = chain_loops(edges, tol=0.05)
    if left:
        warns.append(f"{path.name}: {left} open line(s) ignored (dimensions, borders or gaps)")
    polys = sorted((Polygon(lp) for lp in loops if len(lp) > 3), key=lambda p: p.area, reverse=True)
    polys = [p if p.is_valid else p.buffer(0) for p in polys if p.area > 0.5]

    def depth(i):
        return sum(1 for j, q in enumerate(polys) if j != i and q.area > polys[i].area and q.contains(polys[i].representative_point()))

    d = [depth(i) for i in range(len(polys))]
    # a drawing border / sheet outline contains whole parts (which contain their own holes): drop it
    while d and any(x >= 2 for x in d):
        top = [i for i, x in enumerate(d) if x == 0]
        warns.append(f"{path.name}: ignored {len(top)} frame/border loop(s) around the parts")
        polys = [p for i, p in enumerate(polys) if d[i] != 0]
        d = [depth(i) for i in range(len(polys))]
    raws = []
    outers = [i for i, x in enumerate(d) if x == 0]
    for n, i in enumerate(outers):
        holes = [polys[j] for j, x in enumerate(d) if x == 1 and polys[i].contains(polys[j].representative_point())]
        loops_ = [polys[i]] + holes
        edges_ = [{"t": "S", "len": 0, "p": [list(c) for c in lp.exterior.coords]} for lp in loops_]
        name = path.stem if len(outers) == 1 else f"{path.stem} {n + 1}"
        raws.append({"name": name, "thk": None, "area": polys[i].area, "edges": edges_, "source": path.name})
    return raws, warns


def read_any(path: Path, dxf_units: str | None = None) -> tuple[list, list]:
    ext = path.suffix.lower()
    if ext in (".step", ".stp"):
        return read_step(path), []
    if ext == ".dxf":
        return read_dxf(path, dxf_units)
    raise ValueError(f"{path.name}: use a .step or .dxf file (Onshape: right-click the tab > Export > STEP)")
