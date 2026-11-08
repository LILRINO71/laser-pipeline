"""Pack parts onto sheets (MaxRects, best-short-side-fit, 90 deg rotation allowed)."""

from __future__ import annotations

from dataclasses import dataclass, field

from shapely import affinity


@dataclass
class Placement:
    part: object  # geometry.Part
    copy: int
    x: float
    y: float
    rotated: bool

    def shape(self):
        s = self.part.poly
        if self.rotated:
            s = affinity.rotate(s, 90, origin=(0, 0))
            x0, y0, _, _ = s.bounds
            s = affinity.translate(s, -x0, -y0)
        return affinity.translate(s, self.x, self.y)


@dataclass
class Sheet:
    w: float
    h: float
    placements: list = field(default_factory=list)
    needs_new_wood: bool = True  # False only for the sheet already sitting in the laser


class _MaxRects:
    def __init__(self, w, h):
        self.free = [(0.0, 0.0, w, h)]

    def find(self, w, h, allow_rot):
        best = None
        for fx, fy, fw, fh in self.free:
            for rw, rh, rot in ((w, h, False), (h, w, True)) if allow_rot else ((w, h, False),):
                if rw <= fw + 1e-6 and rh <= fh + 1e-6:
                    score = (min(fw - rw, fh - rh), max(fw - rw, fh - rh), fy, fx)
                    if best is None or score < best[0]:
                        best = (score, fx, fy, rw, rh, rot)
        return best

    def place(self, x, y, w, h):
        out = []
        for fx, fy, fw, fh in self.free:
            if x >= fx + fw or x + w <= fx or y >= fy + fh or y + h <= fy:
                out.append((fx, fy, fw, fh))
                continue
            if x > fx:
                out.append((fx, fy, x - fx, fh))
            if x + w < fx + fw:
                out.append((x + w, fy, fx + fw - x - w, fh))
            if y > fy:
                out.append((fx, fy, fw, y - fy))
            if y + h < fy + fh:
                out.append((fx, y + h, fw, fy + fh - y - h))
        self.free = [r for i, r in enumerate(out) if not any(
            j != i and r[0] >= o[0] - 1e-9 and r[1] >= o[1] - 1e-9 and r[0] + r[2] <= o[0] + o[2] + 1e-9 and r[1] + r[3] <= o[1] + o[3] + 1e-9
            and (r != o or j < i) for j, o in enumerate(out))]


def nest(parts, sheet_w, sheet_h, margin=5.0, gap=4.0, allow_rot=True, occupied=()):
    """Returns (sheets, too_big). Coordinates are mm from the sheet's bottom-left corner.

    occupied: shapes already cut out of the sheet in the laser now; sheet 1 packs around them,
    any further sheets are fresh wood.
    """
    uw, uh = sheet_w - 2 * margin + gap, sheet_h - 2 * margin + gap
    items = [(p, i) for p in parts for i in range(p.qty)]
    items.sort(key=lambda it: (-max(it[0].size), -it[0].poly.area))
    sheets, packers, too_big = [], [], []
    if occupied:
        first = _MaxRects(uw, uh)
        for s in occupied:
            x0, y0, x1, y1 = s.bounds
            first.place(x0 - margin - gap / 2, y0 - margin - gap / 2, x1 - x0 + gap * 1.5, y1 - y0 + gap * 1.5)
        sheets.append(Sheet(sheet_w, sheet_h, needs_new_wood=False))
        packers.append(first)
    for part, i in items:
        w, h = part.size[0] + gap, part.size[1] + gap
        if not ((w <= uw and h <= uh) or (allow_rot and h <= uw and w <= uh)):
            too_big.append(part)
            continue
        for sheet, pk in zip(sheets, packers):
            hit = pk.find(w, h, allow_rot)
            if hit:
                break
        else:
            sheet, pk = Sheet(sheet_w, sheet_h), _MaxRects(uw, uh)
            sheets.append(sheet)
            packers.append(pk)
            hit = pk.find(w, h, allow_rot)
        _, fx, fy, rw, rh, rot = hit
        pk.place(fx, fy, rw, rh)
        sheet.placements.append(Placement(part, i, fx + margin, fy + margin, rot))
    sheets = [s for s in sheets if s.placements]
    for s in sheets:  # cut order: left to right, bottom to top
        s.placements.sort(key=lambda p: (round(p.x / 50), p.y))
    return sheets, too_big
