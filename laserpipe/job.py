"""One laser job: files in -> parts -> nested around the wood already used -> checked -> sent."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

from . import geometry, nest, output
from .bed import Bed, check_sheet
from .importers import read_any

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "jobs" / "history.json"


def load_config() -> dict:
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    local = ROOT / "config.local.json"  # per-machine overrides (not in git)
    if local.is_file():
        cfg.update(json.loads(local.read_text(encoding="utf-8")))
    return cfg


class Job:
    def __init__(self, cfg: dict, team: str = ""):
        self.cfg = cfg
        self.team = team.strip() or "unknown team"
        self.mode = "cut"  # "cut" or "engrave"
        self.files: list[Path] = []
        self.raws: list = []
        self.notes: list[str] = []  # info + warnings for the operator
        self.parts: list = []
        self.sheets: list = []
        self.too_big: list = []
        self.errors: dict[int, list[str]] = {}
        self.moves: dict[tuple, tuple] = {}  # (part name, copy) -> (sheet index, x, y, rotated), from dragging on the map
        self.name = f"{datetime.now():%Y%m%d-%H%M%S}"

    # ------------------------------------------------------------ input
    def add_files(self, paths, dxf_units=None):
        for p in map(Path, paths):
            raws, warns = read_any(p, dxf_units)
            self.files.append(p)
            self.raws += raws
            self.notes += warns
        if self.files:
            self.name = f"{datetime.now():%Y%m%d-%H%M%S}-{_slug(self.team)}-{_slug(self.files[0].stem)}"

    def build(self, thickness: float | None, kerf: float, qty: dict | None = None):
        qty = {k.lower(): v for k, v in (qty or {}).items()}
        tol = self.cfg["thickness_tol_mm"]
        if self.mode == "engrave":
            kerf = 0  # nothing is cut away, so the lines stay exactly where they were drawn
        self.parts = []
        for r in self.raws:
            if thickness and r.get("thk") is not None and abs(r["thk"] - thickness) > tol:
                self.notes.append(f"skipped {r['name']}: {r['thk']:.1f} mm thick, not {thickness:g} mm")
                continue
            try:
                p = geometry.build_part(r, kerf=kerf)
            except Exception as e:
                self.notes.append(f"skipped {r['name']}: {e}")
                continue
            p.qty = qty.get(r["name"].lower(), qty.get("*", 1))
            if p.size[0] < 3 or p.size[1] < 3:
                p.warnings.append("tiny part (<3 mm), may fall through the honeycomb")
            if p.qty > 0:
                self.parts.append(p)
        return self.parts

    # ------------------------------------------------------------ layout
    def plan(self, bed: Bed):
        c = self.cfg
        used = bed.used_shapes()
        self.sheets, self.too_big = nest.nest(self.parts, bed.w, bed.h, c["margin_mm"], c["gap_mm"], occupied=used)
        if self.sheets and not used:
            self.sheets[0].needs_new_wood = False  # empty map = the sheet in the laser is fresh
        self._apply_moves()
        return self.check(bed)

    def _apply_moves(self):
        for key, (idx, x, y, rot) in self.moves.items():
            if idx >= len(self.sheets):
                continue
            for s in self.sheets:
                for pl in s.placements:
                    if (pl.part.name, pl.copy) == key:
                        s.placements.remove(pl)
                        pl.x, pl.y, pl.rotated = x, y, rot
                        self.sheets[idx].placements.append(pl)
                        break
                else:
                    continue
                break

    def remember_move(self, sheet_index: int, pl) -> None:
        self.moves[(pl.part.name, pl.copy)] = (sheet_index, pl.x, pl.y, pl.rotated)

    def check(self, bed: Bed):
        """Run the hard safety checks on the layout as it stands now."""
        c = self.cfg
        used = bed.used_shapes()
        self.errors = {}
        for i, s in enumerate(self.sheets):
            errs = check_sheet(s, [] if s.needs_new_wood else used, c["margin_mm"], c["gap_mm"])
            if errs:
                self.errors[i] = errs
        return self.sheets

    def paths(self, sheet, labels=True):
        cuts, marks = output.sheet_paths(sheet, labels=labels and self.cfg["labels"] and self.mode == "cut")
        if self.mode == "engrave":
            return [], cuts  # every line goes out blue, so no cut-power line exists in the job
        return cuts, marks

    def duplicate_of(self) -> str | None:
        """Same files + quantities sent in the last 30 min? Returns that job's description."""
        h = self.fingerprint()
        for j in reversed(_history()):
            if j.get("hash") == h and time.time() - j["time"] < 1800:
                return f"{j['team']} at {datetime.fromtimestamp(j['time']):%H:%M}"
        return None

    def fingerprint(self) -> str:
        m = hashlib.sha1()
        for f in sorted(self.files):
            m.update(f.read_bytes())
        m.update(json.dumps([self.mode] + sorted((p.name, p.qty) for p in self.parts)).encode())
        return m.hexdigest()

    # ------------------------------------------------------------ output
    def save(self, bed: Bed) -> Path:
        out = ROOT / "jobs" / self.name
        out.mkdir(parents=True, exist_ok=True)
        svgs, stats = [], []
        for i, s in enumerate(self.sheets, 1):
            cuts, marks = self.paths(s)
            output.write_dxf(out / f"sheet{i}.dxf", s, cuts, marks)
            used = [] if s.needs_new_wood else bed.used_shapes()
            sv = output.svg(s, cuts, marks, self.cfg["cut_rgb"], self.cfg["engrave_rgb"], used=used)
            (out / f"sheet{i}.svg").write_text(sv, encoding="utf-8")
            svgs.append(sv)
            stats.append({"parts": len(s.placements), "cut_m": output.cut_length(cuts) / 1000,
                          "fill": sum(p.shape().envelope.area for p in s.placements) / (s.w * s.h) * 100,
                          "new_wood": s.needs_new_wood, "errors": self.errors.get(i - 1, [])})
        settings = {"team": self.team, "job": "engrave only" if self.mode == "engrave" else "cut through", "sheet": f"{bed.w:.0f} × {bed.h:.0f} mm", "files": ", ".join(f.name for f in self.files)}
        (out / "preview.html").write_text(output.preview_html(self.name, "", svgs, self.parts, self.too_big, stats, settings, self.notes),
                                          encoding="utf-8")
        return out

    def send(self, i: int, printer: str, to_pdf: Path | None = None) -> None:
        from . import vls_print

        s = self.sheets[i]
        if self.errors.get(i):
            raise RuntimeError("Sheet failed its safety checks: " + "; ".join(self.errors[i]))
        cuts, marks = self.paths(s)
        layers = [(tuple(self.cfg["engrave_rgb"]), marks), (tuple(self.cfg["cut_rgb"]), cuts)]
        dest = None
        if to_pdf:
            to_pdf.mkdir(parents=True, exist_ok=True)
            dest = str(to_pdf / f"{self.name}-sheet{i + 1}.pdf")
        vls_print.print_sheet(printer, f"{self.team} {self.name} sheet {i + 1}", s.w, s.h, layers, dest)

    def record(self, bed: Bed, i: int) -> None:
        """Mark sheet i's parts as cut on the bed map and in the job history."""
        bed.mark_cut(self.team, self.name, [pl.shape() for pl in self.sheets[i].placements])
        hist = _history()
        hist.append({"time": time.time(), "team": self.team, "job": self.name, "mode": self.mode, "sheet": i + 1, "hash": self.fingerprint(),
                     "parts": [pl.part.name for pl in self.sheets[i].placements]})
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        HISTORY.write_text(json.dumps(hist[-500:], indent=1), encoding="utf-8")


def _history() -> list:
    try:
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    except Exception:
        return []


def _slug(s: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in s)[:24].strip("-") or "job"
