"""Send vector paths straight to the ULS/VLS printer driver (no Illustrator).

UCP is a Windows printer driver: anything printed to it with hairline strokes becomes vector
cuts, and the RGB colour picks the power/speed row (red = cut, blue = score by default).
We draw with GDI cosmetic pens (width 0 = 1 device pixel = hairline), page size = the sheet.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import pywintypes
import win32con
import win32gui
import win32print
import win32ui

SETTINGS_FILE = Path(__file__).resolve().parents[1] / "printer_settings.json"
DM_FIELDS = ["Orientation", "PaperSize", "PaperLength", "PaperWidth", "Scale", "Copies", "PrintQuality",
             "Color", "Duplex", "YResolution", "Fields"]


LASER_NAME = re.compile(r"\bvls|\buls|versalaser|universal\s*laser", re.I)  # never just "laser": that matches HP LaserJets


def printer_list() -> list[tuple[str, str]]:
    """[(printer name, driver name), ...]"""
    found = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS, None, 2)
    return [(p["pPrinterName"], p["pDriverName"]) for p in found]


def find_laser_printer(name: str | None = None) -> str:
    printers = printer_list()
    names = [p for p, _ in printers]
    if name:
        hits = [p for p in names if p.lower() == name.lower()] or [p for p in names if name.lower() in p.lower()]
        if not hits:
            raise SystemExit(f"No printer matching '{name}'. Installed: {', '.join(names)}")
        return hits[0]
    for p, driver in printers:
        if LASER_NAME.search(p) or LASER_NAME.search(driver):
            return p
    raise SystemExit("Couldn't find the laser's printer driver (looked for VLS/ULS/Universal Laser). "
                     f"Installed printers: {', '.join(names)}. Pick it in Laser Station's Laser driver list.")


def _saved(printer: str) -> dict:
    try:
        saved = json.loads(SETTINGS_FILE.read_text())
    except (OSError, ValueError):
        return {}
    return saved if saved.get("printer") == printer else {}


def preset_problem(printer: str) -> str | None:
    """Why the saved power/speed settings can't be used, or None if they can."""
    saved = _saved(printer)
    if not saved:
        return "The laser settings haven't been saved yet."
    h = win32print.OpenPrinter(printer)
    try:
        extra = win32print.GetPrinter(h, 2)["pDevMode"].DriverExtra
    finally:
        win32print.ClosePrinter(h)
    if saved.get("driver_data") and extra != len(base64.b64decode(saved["driver_data"])):
        return "The laser's driver changed since the settings were saved, so they need saving again."
    return None


def preset_verified(printer: str) -> bool:
    return bool(_saved(printer).get("verified"))


def mark_verified(printer: str) -> None:
    saved = _saved(printer)
    saved["verified"] = True
    SETTINGS_FILE.write_text(json.dumps(saved, indent=1))


def _save_settings(printer: str, dm) -> None:
    data = {"printer": printer, "verified": False, "fields": {k: getattr(dm, k) for k in DM_FIELDS},
            "driver_data": base64.b64encode(bytes(dm.DriverData or b"")).decode()}
    SETTINGS_FILE.write_text(json.dumps(data, indent=1))


def _devmode(printer: str, require: bool = False):
    if require and (problem := preset_problem(printer)):
        raise SystemExit(problem)
    h = win32print.OpenPrinter(printer)
    try:
        dm = win32print.GetPrinter(h, 2)["pDevMode"]
        saved = _saved(printer)
        if saved:
            for k, v in saved["fields"].items():
                setattr(dm, k, v)
            if saved.get("driver_data") and dm.DriverExtra == len(base64.b64decode(saved["driver_data"])):
                dm.DriverData = base64.b64decode(saved["driver_data"])
        return h, dm
    except Exception:
        win32print.ClosePrinter(h)
        raise


def setup_settings(printer: str, hwnd: int | None = None) -> bool:
    """Open the driver's own settings dialog and lock in what's chosen. True if OK was pressed."""
    h, dm = _devmode(printer)
    try:
        hwnd = hwnd or win32gui.GetDesktopWindow()
        r = win32print.DocumentProperties(hwnd, h, printer, dm, dm, win32con.DM_IN_PROMPT | win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER)
        if r == win32con.IDCANCEL:
            return False
        if r < 0:
            raise RuntimeError(f"The laser's driver reported error {r}")
        _save_settings(printer, dm)
        return True
    finally:
        win32print.ClosePrinter(h)


def print_sheet(printer: str, job_name: str, sheet_w: float, sheet_h: float, layers: list, output_file: str | None = None) -> None:
    """layers: [(rgb_tuple, [loop, ...]), ...] in drawing order. mm, origin bottom-left of the sheet."""
    h, dm = _devmode(printer, require=output_file is None)  # a real laser job never runs on unsaved settings
    try:
        dm.PaperSize = 256  # DMPAPER_USER: custom size = the sheet
        dm.PaperWidth = int(round(sheet_w * 10))  # tenths of a mm
        dm.PaperLength = int(round(sheet_h * 10))
        dm.Orientation = win32con.DMORIENT_PORTRAIT
        dm.Fields |= win32con.DM_PAPERSIZE | win32con.DM_PAPERWIDTH | win32con.DM_PAPERLENGTH | win32con.DM_ORIENTATION
        win32print.DocumentProperties(0, h, printer, dm, dm, win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER)
    finally:
        win32print.ClosePrinter(h)

    hdc = win32gui.CreateDC("WINSPOOL", printer, dm)
    dc = win32ui.CreateDCFromHandle(hdc)
    try:
        dpx = dc.GetDeviceCaps(win32con.LOGPIXELSX)
        dpy = dc.GetDeviceCaps(win32con.LOGPIXELSY)
        offx = dc.GetDeviceCaps(win32con.PHYSICALOFFSETX)
        offy = dc.GetDeviceCaps(win32con.PHYSICALOFFSETY)

        def pt(x, y):  # sheet mm (y up) -> printable-area pixels (y down)
            return int(round(x / 25.4 * dpx)) - offx, int(round((sheet_h - y) / 25.4 * dpy)) - offy

        dc.StartDoc(job_name, output_file) if output_file else dc.StartDoc(job_name)
        dc.StartPage()
        dc.SelectObject(win32ui.CreateBrush(win32con.BS_NULL, 0, 0))
        for rgb, loops in layers:
            pen = win32ui.CreatePen(win32con.PS_SOLID, 0, win32api_rgb(rgb))
            old = dc.SelectObject(pen)
            for lp in loops:
                pts = []
                for p in (pt(x, y) for x, y in lp):
                    if not pts or p != pts[-1]:
                        pts.append(p)
                if pts[0] != pts[-1]:
                    pts.append(pts[0])
                if len(pts) > 2:
                    dc.Polyline(pts)  # one connected vector per loop
            dc.SelectObject(old)
        dc.EndPage()
        dc.EndDoc()
    except pywintypes.error as e:
        dc.AbortDoc()
        raise SystemExit(f"Printing failed: {e}")
    finally:
        dc.DeleteDC()


def win32api_rgb(rgb) -> int:
    r, g, b = rgb
    return r | (g << 8) | (b << 16)
