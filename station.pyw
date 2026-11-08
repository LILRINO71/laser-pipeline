"""Laser Station: the window on the laser PC. Any team opens their STEP/DXF, checks the layout
on the shared plywood sheet, answers one question, and the laser fires.

Double-click "Laser Station.bat" (or this file).
"""

from __future__ import annotations

import json
import threading
import tkinter as tk
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from laserpipe.bed import Bed
from laserpipe.job import ROOT, Job, load_config

PREFS = ROOT / "station_prefs.json"
WOOD, USED, CUT, MARK, BAD = "#ecd9b4", "#9a9a9a", "#d01c1c", "#1f4fd8", "#b3261e"


class Station(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.title("Laser Station · VLS 4.60")
        self.geometry("1180x760")
        self.minsize(900, 600)
        self.bed = Bed.load(*self.cfg["sheet_mm"])
        self.job: Job | None = None
        self.qty: dict[str, int] = {}
        self.view = 0
        prefs = self._prefs()
        self.team = tk.StringVar(value=prefs.get("team", ""))
        self.thk = tk.StringVar(value=str(self.cfg["thickness_mm"]))
        self.kerf = tk.StringVar(value=str(prefs.get("kerf", self.cfg["kerf_mm"])))
        self.busy = False
        self._build_ui()
        self.refresh_bed()
        self.bind("<Configure>", lambda e: self.after_idle(self.draw))

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        st = ttk.Style(self)
        st.configure("Fire.TButton", font=("Segoe UI", 13, "bold"), foreground=BAD, padding=10)
        st.configure("H.TLabel", font=("Segoe UI", 11, "bold"))
        top = ttk.Frame(self, padding=(12, 10))
        top.pack(fill="x")
        ttk.Label(top, text="Team").pack(side="left")
        ttk.Entry(top, textvariable=self.team, width=16).pack(side="left", padx=(4, 14))
        ttk.Button(top, text="Open STEP / DXF…", command=self.open_files).pack(side="left")
        ttk.Label(top, text="Thickness mm").pack(side="left", padx=(16, 4))
        ttk.Entry(top, textvariable=self.thk, width=5).pack(side="left")
        ttk.Label(top, text="Kerf mm").pack(side="left", padx=(12, 4))
        ttk.Entry(top, textvariable=self.kerf, width=5).pack(side="left")
        ttk.Button(top, text="Re-layout", command=self.rebuild).pack(side="left", padx=10)
        self.bed_lbl = ttk.Label(top, text="", foreground="#555")
        self.bed_lbl.pack(side="right")

        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=12)
        left = ttk.Frame(body)
        body.add(left, weight=1)
        ttk.Label(left, text="Parts (double-click to change how many)", style="H.TLabel").pack(anchor="w")
        self.tree = ttk.Treeview(left, columns=("qty", "size", "note"), show="tree headings", height=14)
        self.tree.heading("#0", text="Part")
        self.tree.heading("qty", text="Qty")
        self.tree.heading("size", text="Size mm")
        self.tree.heading("note", text="Notes")
        self.tree.column("#0", width=170)
        self.tree.column("qty", width=40, anchor="center")
        self.tree.column("size", width=90)
        self.tree.column("note", width=170)
        self.tree.pack(fill="both", expand=True, pady=(4, 6))
        self.tree.bind("<Double-1>", self.edit_qty)
        row = ttk.Frame(left)
        row.pack(fill="x")
        ttk.Button(row, text="−", width=3, command=lambda: self.bump(-1)).pack(side="left")
        ttk.Button(row, text="+", width=3, command=lambda: self.bump(+1)).pack(side="left", padx=4)
        ttk.Button(row, text="All ×2", command=lambda: self.bump(0, mult=2)).pack(side="left")
        self.msgs = tk.Text(left, height=9, wrap="word", relief="flat", background=self.cget("background"), font=("Segoe UI", 9))
        self.msgs.pack(fill="x", pady=(8, 0))
        self.msgs.tag_configure("bad", foreground=BAD, font=("Segoe UI", 9, "bold"))
        self.msgs.tag_configure("warn", foreground="#8a5a00")

        right = ttk.Frame(body)
        body.add(right, weight=3)
        hdr = ttk.Frame(right)
        hdr.pack(fill="x")
        self.sheet_lbl = ttk.Label(hdr, text="Wood in the laser", style="H.TLabel")
        self.sheet_lbl.pack(side="left")
        ttk.Button(hdr, text="▶", width=3, command=lambda: self.flip(1)).pack(side="right")
        ttk.Button(hdr, text="◀", width=3, command=lambda: self.flip(-1)).pack(side="right")
        self.canvas = tk.Canvas(right, background="#f7f6f2", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, pady=4)

        bot = ttk.Frame(self, padding=(12, 8))
        bot.pack(fill="x")
        ttk.Button(bot, text="New sheet loaded", command=self.new_sheet).pack(side="left")
        ttk.Button(bot, text="Undo last cut", command=self.undo).pack(side="left", padx=6)
        ttk.Button(bot, text="Save DXF + preview only", command=self.save_only).pack(side="left")
        self.fire_btn = ttk.Button(bot, text="CUT  ▸  FIRE", style="Fire.TButton", command=self.fire)
        self.fire_btn.pack(side="right")
        self.status = ttk.Label(bot, text="Open a STEP (Onshape: right-click the Part Studio tab > Export > STEP).", foreground="#555")
        self.status.pack(side="right", padx=14)

    # ------------------------------------------------------------------ state
    def _prefs(self):
        try:
            return json.loads(PREFS.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_prefs(self):
        PREFS.write_text(json.dumps({"team": self.team.get(), "kerf": self.kerf.get()}), encoding="utf-8")

    def refresh_bed(self):
        jobs = ", ".join(f"{u['team']} {datetime.fromtimestamp(u['time']):%H:%M}" for u in self.bed.used[-3:])
        used = 100 * (1 - self.bed.free_fraction())
        self.bed_lbl.config(text=f"Wood in laser: {used:.0f}% used" + (f" by {jobs}" if jobs else " (fresh sheet)"))
        self.draw()

    def open_files(self):
        paths = filedialog.askopenfilenames(title="Pick your Onshape export", initialdir=str(Path.home() / "Downloads"),
                                            filetypes=[("STEP or DXF", "*.step *.stp *.STEP *.dxf *.DXF"), ("All", "*.*")])
        if not paths:
            return
        self.job = Job(self.cfg, self.team.get())
        try:
            self.job.add_files(paths)
        except Exception as e:
            messagebox.showerror("Couldn't read that file", str(e))
            self.job = None
            return
        self.qty = {}
        self.rebuild()

    def rebuild(self):
        if not self.job:
            return
        j = self.job
        j.team = self.team.get().strip() or "unknown team"
        j.notes = [n for n in j.notes if not n.startswith("skipped ")]
        try:
            thk = float(self.thk.get() or 0)
            kerf = float(self.kerf.get() or 0)
        except ValueError:
            messagebox.showerror("Numbers", "Thickness and kerf must be numbers (mm).")
            return
        self._save_prefs()
        j.build(thk, kerf, self.qty)
        for p in j.parts:
            self.qty.setdefault(p.name, p.qty)
        self.bed = Bed.load(*self.cfg["sheet_mm"])
        j.plan(self.bed)
        self.view = 0
        self.fill_tree()
        self.fill_msgs()
        self.refresh_bed()

    def fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        for p in self.job.parts:
            self.tree.insert("", "end", iid=p.name, text=p.name, values=(p.qty, f"{p.size[0]:.0f} × {p.size[1]:.0f}", "; ".join(p.warnings)))

    def fill_msgs(self):
        j = self.job
        self.msgs.delete("1.0", "end")
        for i, errs in j.errors.items():
            for e in errs:
                self.msgs.insert("end", f"BLOCKED (sheet {i + 1}): {e}\n", "bad")
        for p in j.too_big:
            self.msgs.insert("end", f"{p.name} is bigger than the sheet and was left out\n", "bad")
        for p in j.parts:
            for w in p.warnings:
                self.msgs.insert("end", f"{p.name}: {w}\n", "warn")
        for n in j.notes:
            self.msgs.insert("end", n + "\n")
        n = len(j.sheets)
        new = sum(1 for s in j.sheets if s.needs_new_wood)
        self.status.config(text=f"{sum(len(s.placements) for s in j.sheets)} parts on {n} sheet(s)"
                           + (f", {new} need fresh plywood" if new else ", all on the wood in the laser"))

    def edit_qty(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        v = simpledialog.askinteger("How many?", f"How many of {sel[0]}?", initialvalue=self.qty.get(sel[0], 1), minvalue=0, maxvalue=50)
        if v is not None:
            self.qty[sel[0]] = v
            self.rebuild()

    def bump(self, d, mult=None):
        if not self.job:
            return
        if mult:
            self.qty = {k: v * mult for k, v in self.qty.items()}
        else:
            for s in self.tree.selection():
                self.qty[s] = max(0, self.qty.get(s, 1) + d)
        self.rebuild()

    def flip(self, d):
        if self.job and self.job.sheets:
            self.view = (self.view + d) % len(self.job.sheets)
            self.draw()

    # ------------------------------------------------------------------ drawing
    def draw(self):
        c = self.canvas
        c.delete("all")
        W, H = max(c.winfo_width(), 50), max(c.winfo_height(), 50)
        bw, bh = self.bed.w, self.bed.h
        k = min((W - 20) / bw, (H - 20) / bh)
        ox, oy = (W - bw * k) / 2, (H - bh * k) / 2

        def xy(pts):
            out = []
            for x, y in pts:
                out += [ox + x * k, oy + (bh - y) * k]
            return out

        sheet = self.job.sheets[self.view] if self.job and self.job.sheets else None
        c.create_rectangle(ox, oy, ox + bw * k, oy + bh * k, fill=WOOD, outline="#8b7a5a")
        c.create_text(ox + 4, oy + 4, text="laser home (top-left)", anchor="nw", fill="#8b7a5a", font=("Segoe UI", 8))
        if sheet is None or not sheet.needs_new_wood:
            for u in self.bed.used_shapes():
                for g in getattr(u, "geoms", [u]):
                    if hasattr(g, "exterior"):
                        c.create_polygon(xy(g.exterior.coords), fill=USED, outline="#777", stipple="gray50")
        if sheet:
            cuts, marks = self.job.paths(sheet)
            for lp in marks:
                c.create_line(xy(lp + lp[:1]), fill=MARK, width=1)
            for lp in cuts:
                c.create_line(xy(lp + lp[:1]), fill=CUT, width=1.4)
            n = len(self.job.sheets)
            where = "NEEDS A NEW SHEET OF PLYWOOD" if sheet.needs_new_wood else "on the wood in the laser now"
            self.sheet_lbl.config(text=f"Sheet {self.view + 1} of {n} · {where}")
            if self.job.errors.get(self.view):
                c.create_text(W / 2, 14, text="BLOCKED: " + self.job.errors[self.view][0], fill=BAD, font=("Segoe UI", 11, "bold"))
        else:
            self.sheet_lbl.config(text="Wood in the laser (grey = already cut)")

    # ------------------------------------------------------------------ actions
    def new_sheet(self):
        if messagebox.askyesno("New sheet", "Is a fresh, uncut sheet of plywood in the laser now?\nThis clears the map of used wood."):
            self.bed.new_sheet()
            self.rebuild() if self.job else self.refresh_bed()

    def undo(self):
        if not self.bed.used:
            return
        u = self.bed.used[-1]
        if messagebox.askyesno("Undo", f"Forget the last cut ({u['team']}, {datetime.fromtimestamp(u['time']):%H:%M})?\n"
                               "Only do this if it never actually cut."):
            self.bed.undo_last()
            self.rebuild() if self.job else self.refresh_bed()

    def save_only(self):
        if self.job and self.job.sheets:
            out = self.job.save(self.bed)
            import webbrowser
            webbrowser.open((out / "preview.html").as_uri())

    def fire(self):
        j = self.job
        if self.busy or not j or not j.sheets:
            return
        i = self.view
        s = j.sheets[i]
        if j.errors.get(i):
            messagebox.showerror("Blocked", "This sheet failed a safety check:\n\n" + "\n".join(j.errors[i]))
            return
        dup = j.duplicate_of()
        if dup and not messagebox.askyesno("Already cut?", f"These exact parts were sent by {dup}.\nCut them again?"):
            return
        if not self.ask_ready(s, i):
            return
        self._save_prefs()
        self.busy = True
        self.fire_btn.state(["disabled"])
        self.status.config(text=f"Sending sheet {i + 1} to the laser…")
        threading.Thread(target=self._send, args=(i,), daemon=True).start()

    def ask_ready(self, s, i) -> bool:
        """The one question before the laser fires."""
        d = tk.Toplevel(self)
        d.title("Ready to fire?")
        d.transient(self)
        d.grab_set()
        d.resizable(False, False)
        wood = ("Swap in a NEW sheet of plywood first (the map will reset)." if s.needs_new_wood
                else "The plywood in the laser is the sheet on screen (grey = already cut), pushed into the top-left corner.")
        txt = (f"Fire the laser for {len(s.placements)} part(s) on sheet {i + 1}?\n\n"
               f"•  {wood}\n•  Focus is set for this wood.\n•  Lid closed, exhaust / air assist on.\n"
               "•  You'll stay at the laser until it finishes.")
        ttk.Label(d, text=txt, padding=18, wraplength=440, justify="left", font=("Segoe UI", 10)).pack()
        ans = {"ok": False}
        row = ttk.Frame(d, padding=(18, 0, 18, 16))
        row.pack(fill="x")

        def yes():
            ans["ok"] = True
            d.destroy()

        ttk.Button(row, text="Cancel", command=d.destroy).pack(side="right")
        ttk.Button(row, text="Yes, FIRE", style="Fire.TButton", command=yes).pack(side="right", padx=8)
        d.bind("<Escape>", lambda e: d.destroy())
        self.wait_window(d)
        if ans["ok"] and s.needs_new_wood:
            self.bed.new_sheet()
            s.needs_new_wood = False
        return ans["ok"]

    def _send(self, i):
        from laserpipe import ucp, vls_print

        j = self.job
        try:
            test_pdf = self.cfg.get("test_pdf_dir")
            printer = vls_print.find_laser_printer("Microsoft Print to PDF" if test_pdf else self.cfg.get("printer"))
            j.send(i, printer, Path(test_pdf) if test_pdf else None)
            j.record(self.bed, i)
            msg = f"Sheet {i + 1} sent to {printer}."
            if self.cfg.get("auto_start") and not test_pdf:
                ok, m = ucp.press_start(self.cfg.get("ucp_start_button"))
                msg += " " + m
            self.after(0, self._sent, i, msg, None)
        except BaseException as e:  # SystemExit from the printer helpers too
            self.after(0, self._sent, i, None, f"{e}\n\n{traceback.format_exc(limit=2)}")

    def _sent(self, i, msg, err):
        self.busy = False
        self.fire_btn.state(["!disabled"])
        if err:
            self.status.config(text="Not sent.")
            messagebox.showerror("Laser", err)
            return
        self.status.config(text=msg)
        j = self.job
        left = [k for k in range(len(j.sheets)) if k > i]
        if left:
            self.view = left[0]
            self.draw()
            messagebox.showinfo("Sent", msg + f"\n\nSheet {left[0] + 1} needs fresh plywood. When this cut is done, swap the wood "
                                "and press FIRE again.")
        else:
            self.bed = Bed.load(*self.cfg["sheet_mm"])
            messagebox.showinfo("Sent", msg + "\n\nThe used wood is marked on the map for the next team.")
            self.job = None
            self.tree.delete(*self.tree.get_children())
            self.refresh_bed()


if __name__ == "__main__":
    Station().mainloop()
