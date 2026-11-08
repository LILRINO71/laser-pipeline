"""Onshape Part Studio -> nested laser sheets -> VLS 4.60, in one command.

    python laser.py <onshape part studio link>            preview, then asks before sending
    python laser.py <link> --qty "Frame Plate +Y=2" --yes  send without asking
    python laser.py --setup                                 pick laser material settings once
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from laserpipe import geometry, nest, output
from laserpipe.onshape import fetch_profiles

ROOT = Path(__file__).resolve().parent


def parse_size(s: str) -> tuple[float, float]:
    m = re.fullmatch(r"\s*([\d.]+)\s*[xX×]\s*([\d.]+)\s*(mm|in)?\s*", s)
    if not m:
        raise argparse.ArgumentTypeError("size looks like 24x18in or 600x400mm")
    k = 25.4 if m.group(3) == "in" else 1.0
    return float(m.group(1)) * k, float(m.group(2)) * k


def main(argv=None):
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?", help="Onshape Part Studio link (copy the address bar)")
    ap.add_argument("--qty", action="append", default=[], help='"Part name=count" (repeatable), or "*=2" for everything')
    ap.add_argument("--only", help="comma-separated part names to include (substring match)")
    ap.add_argument("--sheet", type=parse_size, help="material size, e.g. 24x18in (default: VLS 4.60 bed)")
    ap.add_argument("--thickness", type=float, default=cfg["thickness_mm"], help="only plates this thick (mm); 0 = any")
    ap.add_argument("--kerf", type=float, default=cfg["kerf_mm"], help="beam width in mm to compensate (e.g. 0.15)")
    ap.add_argument("--no-labels", action="store_true", help="don't score part names")
    ap.add_argument("--printer", default=cfg["printer"], help="printer name (default: auto-find VLS/ULS)")
    ap.add_argument("--yes", "-y", action="store_true", help="send to the laser without asking")
    ap.add_argument("--no-send", action="store_true", help="make files + preview only")
    ap.add_argument("--to-pdf", help="print through 'Microsoft Print to PDF' into this folder (testing)")
    ap.add_argument("--cached", action="store_true", help="reuse the last download (0 Onshape calls)")
    ap.add_argument("--no-open", action="store_true", help="don't open the preview in the browser")
    ap.add_argument("--setup", action="store_true", help="open the laser driver's settings and remember them")
    a = ap.parse_args(argv)

    if a.setup:
        from laserpipe import vls_print
        vls_print.setup_settings(vls_print.find_laser_printer(a.printer))
        return
    if not a.url:
        a.url = input("Paste the Onshape Part Studio link: ").strip()

    sheet_w, sheet_h = a.sheet or tuple(cfg["sheet_mm"])
    raw, ref = fetch_profiles(a.url, use_cache=a.cached)
    print(f"Onshape: {len(raw)} solid part(s) in the tab")

    qty = {}
    for q in a.qty:
        name, _, n = q.rpartition("=")
        qty[name.strip().lower()] = int(n)
    only = [s.strip().lower() for s in a.only.split(",")] if a.only else None

    parts, skipped = [], []
    for r in raw:
        nm = r["name"]
        if only and not any(o in nm.lower() for o in only):
            continue
        if a.thickness and abs(r["thk"] - a.thickness) > cfg["thickness_tol_mm"]:
            skipped.append(f"{nm} ({r['thk']:.1f} mm thick)")
            continue
        try:
            p = geometry.build_part(r, kerf=a.kerf)
        except ValueError as e:
            skipped.append(str(e))
            continue
        p.qty = qty.get(nm.lower(), qty.get("*", 1))
        if p.qty > 0:
            parts.append(p)
    for s in skipped:
        print(f"  skipped: {s}")
    if not parts:
        raise SystemExit("No plates to cut. Check --thickness / --only, or that this is the right tab.")

    sheets, too_big = nest.nest(parts, sheet_w, sheet_h, cfg["margin_mm"], cfg["gap_mm"])
    for p in too_big:
        print(f"  WARNING: {p.name} ({p.size[0]:.0f} x {p.size[1]:.0f} mm) doesn't fit on the sheet")

    job = f"{datetime.now():%Y%m%d-%H%M}-{ref['eid'][:6]}"
    out = ROOT / "jobs" / job
    out.mkdir(parents=True, exist_ok=True)
    rendered, svgs, stats = [], [], []
    for i, s in enumerate(sheets, 1):
        cuts, marks = output.sheet_paths(s, labels=cfg["labels"] and not a.no_labels)
        output.write_dxf(out / f"sheet{i}.dxf", s, cuts, marks)
        sv = output.svg(s, cuts, marks, cfg["cut_rgb"], cfg["engrave_rgb"])
        (out / f"sheet{i}.svg").write_text(sv, encoding="utf-8")
        used = sum(p.shape().envelope.area for p in s.placements) / (s.w * s.h) * 100
        stats.append({"parts": len(s.placements), "cut_m": output.cut_length(cuts) / 1000, "fill": used})
        rendered.append((s, cuts, marks))
        svgs.append(sv)
        print(f"Sheet {i}: {len(s.placements)} parts, {stats[-1]['cut_m']:.2f} m of cut")

    settings = {"sheet": f"{sheet_w:.0f} × {sheet_h:.0f} mm", "kerf": f"{a.kerf} mm", "thickness": f"{a.thickness} mm"}
    page = out / "preview.html"
    page.write_text(output.preview_html(job, a.url, svgs, parts, too_big, stats, settings), encoding="utf-8")
    print(f"Files: {out}")
    if not a.no_open:
        webbrowser.open(page.as_uri())
    if a.no_send:
        return

    from laserpipe import vls_print
    printer = vls_print.find_laser_printer("Microsoft Print to PDF" if a.to_pdf else a.printer)
    if not (a.yes or a.to_pdf):
        ans = input(f"Send {len(sheets)} sheet(s) to '{printer}'? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("Not sent. Files are saved; rerun with --cached to send without another Onshape call.")
            return
    for i, (s, cuts, marks) in enumerate(rendered, 1):
        layers = [(tuple(cfg["engrave_rgb"]), marks), (tuple(cfg["cut_rgb"]), cuts)]  # score names before cutting free
        dest = str(Path(a.to_pdf).resolve() / f"{job}-sheet{i}.pdf") if a.to_pdf else None
        if dest:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
        vls_print.print_sheet(printer, f"{job} sheet {i}", s.w, s.h, layers, dest)
        print(f"Sheet {i} sent to {printer}" + (f" -> {dest}" if dest else ". Load plywood, focus, press Start."))


if __name__ == "__main__":
    sys.exit(main())
