"""Command-line version of Laser Station (the window is station.pyw).

    python laser.py robot-plates.step                      lay out on the shared sheet, preview, ask, fire
    python laser.py plates.step --qty "Frame Plate +Y=2" --team "7831"
    python laser.py plate.dxf --dxf-units in --no-send     files + preview only
    python laser.py --new-sheet                             a fresh sheet of plywood is in the laser
    python laser.py --setup                                 save the ULS driver settings once
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from laserpipe.bed import Bed
from laserpipe.job import Job, load_config


def _ask(q: str) -> str:
    return input(q).strip().lstrip("\ufeff").strip().lower()


def main(argv=None):
    cfg = load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="STEP or DXF files exported from Onshape")
    ap.add_argument("--team", default="", help="your team name (shown on the shared sheet map)")
    ap.add_argument("--qty", action="append", default=[], help='"Part name=count" (repeatable), "*=2" for everything')
    ap.add_argument("--thickness", type=float, default=cfg["thickness_mm"], help="only plates this thick (mm); 0 = any")
    ap.add_argument("--kerf", type=float, default=cfg["kerf_mm"], help="beam width to compensate, mm")
    ap.add_argument("--dxf-units", choices=["mm", "in"], help="force DXF units if the file has none")
    ap.add_argument("--no-send", action="store_true", help="files + preview only")
    ap.add_argument("--no-open", action="store_true", help="don't open the preview page")
    ap.add_argument("--to-pdf", help="test: print through Microsoft Print to PDF into this folder")
    ap.add_argument("--new-sheet", action="store_true", help="mark the wood in the laser as fresh")
    ap.add_argument("--setup", action="store_true", help="open the laser driver's settings and remember them")
    a = ap.parse_args(argv)

    bed = Bed.load(*cfg["sheet_mm"])
    if a.setup:
        from laserpipe import vls_print
        vls_print.setup_settings(vls_print.find_laser_printer(cfg.get("printer")))
        return
    if a.new_sheet:
        bed.new_sheet()
        print("Sheet map cleared: fresh plywood in the laser.")
        if not a.files:
            return
    if not a.files:
        ap.error("give a STEP or DXF file (Onshape: right-click the Part Studio tab > Export > STEP)")

    qty = {}
    for q in a.qty:
        name, _, n = q.rpartition("=")
        qty[name.strip()] = int(n)
    job = Job(cfg, a.team)
    job.add_files(a.files, a.dxf_units)
    job.build(a.thickness, a.kerf, qty)
    if not job.parts:
        for n in job.notes:
            print(" ", n)
        raise SystemExit("No plates to cut. Check --thickness, or that this is the right file.")
    job.plan(bed)
    for n in job.notes:
        print(" ", n)
    for p in job.parts:
        for w in p.warnings:
            print(f"  WARNING {p.name}: {w}")
    for p in job.too_big:
        print(f"  WARNING: {p.name} is bigger than the sheet, left out")
    for i, s in enumerate(job.sheets):
        print(f"Sheet {i + 1}: {len(s.placements)} parts, " + ("NEW plywood" if s.needs_new_wood else "on the wood in the laser"))
        for e in job.errors.get(i, []):
            print(f"  BLOCKED: {e}")
    out = job.save(bed)
    print(f"Files: {out}")
    if not a.no_open:
        webbrowser.open((out / "preview.html").as_uri())
    if a.no_send:
        return

    from laserpipe import ucp, vls_print
    test_pdf = a.to_pdf or cfg.get("test_pdf_dir")
    printer = vls_print.find_laser_printer("Microsoft Print to PDF" if test_pdf else cfg.get("printer"))
    dup = job.duplicate_of()
    if dup and _ask(f"These exact parts were already sent by {dup}. Cut again? [y/N] ") != "y":
        return
    for i, s in enumerate(job.sheets):
        if job.errors.get(i):
            print(f"Sheet {i + 1} is blocked, not sending.")
            continue
        wood = "a NEW sheet of plywood is loaded" if s.needs_new_wood else "the wood in the laser matches the map (grey = used)"
        q = (f"\nFire sheet {i + 1} ({len(s.placements)} parts)? Check: {wood}, focus set, lid closed, exhaust on, "
             "and you'll stay at the laser. [y/N] ")
        if _ask(q) not in ("y", "yes"):
            print("Not fired. Nothing marked as used.")
            return
        if s.needs_new_wood:
            bed.new_sheet()
        job.send(i, printer, Path(test_pdf) if test_pdf else None)
        job.record(bed, i)
        msg = f"Sheet {i + 1} sent to {printer}."
        if cfg.get("auto_start") and not test_pdf:
            msg += " " + ucp.press_start(cfg.get("ucp_start_button"))[1]
        print(msg)


if __name__ == "__main__":
    sys.exit(main())
