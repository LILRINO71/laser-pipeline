"""The plywood sheet sitting in the laser, shared by every team.

Each job that gets cut is recorded with its real outlines, so the next team's parts are nested into
the wood that's still left. "New sheet loaded" wipes the map.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from shapely import wkt
from shapely.geometry import box
from shapely.ops import unary_union

STATE = Path(__file__).resolve().parents[1] / "sheet_state.json"


class Bed:
    def __init__(self, w: float, h: float):
        self.w, self.h = w, h
        self.loaded_at = time.time()
        self.used: list[dict] = []  # {team, job, time, wkt}

    # ---- persistence
    @classmethod
    def load(cls, w: float, h: float) -> "Bed":
        b = cls(w, h)
        if STATE.is_file():
            try:
                d = json.loads(STATE.read_text(encoding="utf-8"))
                if abs(d["w"] - w) < 0.1 and abs(d["h"] - h) < 0.1:
                    b.loaded_at, b.used = d["loaded_at"], d["used"]
            except Exception:
                pass
        return b

    def save(self) -> None:
        tmp = STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"w": self.w, "h": self.h, "loaded_at": self.loaded_at, "used": self.used}), encoding="utf-8")
        tmp.replace(STATE)

    # ---- state
    def new_sheet(self) -> None:
        self.loaded_at, self.used = time.time(), []
        self.save()

    def mark_cut(self, team: str, job: str, shapes) -> None:
        self.used.append({"team": team, "job": job, "time": time.time(), "wkt": unary_union(list(shapes)).wkt})
        self.save()

    def undo_last(self):
        if self.used:
            u = self.used.pop()
            self.save()
            return u
        return None

    def used_shapes(self):
        return [wkt.loads(u["wkt"]) for u in self.used]

    def free_fraction(self) -> float:
        used = sum(s.area for s in self.used_shapes())
        return 1 - used / (self.w * self.h)


def check_sheet(sheet, used_shapes, margin: float, gap: float) -> list[str]:
    """Hard safety checks. Any message here blocks cutting."""
    errs = []
    inside = box(margin * 0.5, margin * 0.5, sheet.w - margin * 0.5, sheet.h - margin * 0.5)
    shapes = [(pl.part.name, pl.shape()) for pl in sheet.placements]
    for name, s in shapes:
        if not inside.contains(s):
            errs.append(f"{name} runs off the edge of the sheet")
        for u in used_shapes:
            if s.distance(u) < gap * 0.45:
                errs.append(f"{name} would cut into wood that's already been cut")
                break
    for i in range(len(shapes)):
        for j in range(i + 1, len(shapes)):
            if shapes[i][1].distance(shapes[j][1]) < gap * 0.45:
                errs.append(f"{shapes[i][0]} and {shapes[j][0]} overlap")
    return errs
