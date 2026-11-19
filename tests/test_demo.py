"""Run: python tests/test_demo.py   (Windows; needs the libraries in requirements.txt)

Demo mode, end to end, in a copy of the app: Onshape demo jobs -> layout -> FIRE -> PDF + animation; real map untouched."""
import json, shutil, sys, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
repo = Path(__file__).resolve().parents[1]
scratch = repo / "tests" / "out"  # screenshots + a throwaway copy of the app (git-ignored)
scratch.mkdir(parents=True, exist_ok=True)
app = scratch / "app_demo"
if app.exists():
    shutil.rmtree(app)
app.mkdir()
for f in ("station.pyw", "laser.py", "config.json"):
    shutil.copy2(repo / f, app / f)
for d in ("laserpipe", "samples"):
    shutil.copytree(repo / d, app / d, ignore=shutil.ignore_patterns("__pycache__"))
real_map = app / "sheet_state.json"
real_map.write_text('{"w": 609.6, "h": 457.2, "loaded_at": 1, "used": []}')  # stands in for the laser PC's real map
before = real_map.read_text()
sys.path.insert(0, str(app))
sys.argv = ["station.pyw", "--demo"]

import importlib.machinery, importlib.util
from PIL import ImageGrab

results = []


def check(name, ok, extra=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if extra else ""))


loader = importlib.machinery.SourceFileLoader("station", str(app / "station.pyw"))
spec = importlib.util.spec_from_loader("station", loader)
station = importlib.util.module_from_spec(spec)
loader.exec_module(station)
st = station.Station()
st.geometry("1280x820+20+20")


def pump_until(fn, limit=60):
    t = time.time()

    def poll():
        if not fn() and time.time() - t < limit:
            st.after(30, poll)
        else:
            st.quit()

    st.after(0, poll)
    st.mainloop()
    st.update()


def shot(name, win=None):
    w = win or st
    w.attributes("-topmost", True)
    w.update()
    time.sleep(0.35)
    w.update()
    ImageGrab.grab(bbox=(w.winfo_rootx(), w.winfo_rooty(), w.winfo_rootx() + w.winfo_width(), w.winfo_rooty() + w.winfo_height()),
                   all_screens=True).save(scratch / name)
    w.attributes("-topmost", False)


check("demo title", "DEMO" in st.title())
check("demo uses its own sheet map", str(station.bed_mod.STATE).endswith(r"jobs\demo\sheet_state.json"), str(station.bed_mod.STATE))
pump_until(lambda: "waiting" in str(st.jobs_btn.cget("text")))
check("3 demo jobs waiting (no internet needed)", "3 waiting" in st.jobs_btn.cget("text"), st.jobs_btn.cget("text"))
check("driver line says demo", "Demo" in st.driver_lbl.cget("text"), st.driver_lbl.cget("text"))
shot("demo_start.png")

st.open_cloud()
pump_until(lambda: len(st.cloud_tree.get_children()) == 3)
shot("demo_jobs.png", st.cloud_win)
st.load_cloud()  # nothing selected, one team waiting: loads all
pump_until(lambda: not st.loading and st.job is not None)
j = st.job
placed = sorted(pl.part.name for s in j.sheets for pl in s.placements)
check("both 6.35 mm side plates placed", placed == ["Side Plate +Y", "Side Plate -Y"], str(placed))
check("Hub Deck skipped as too thin", any("Hub Deck" in n and "3.2 mm" in n for n in j.notes), str([n for n in j.notes if "Hub" in n]))
check("tops picked in Onshape were found", all(r.get("top_picked") for r in j.raws))
shot("demo_loaded.png")

pdf_dir = app / "jobs" / "demo" / "laser files"
mid = {}


def grab_mid():
    import re
    m = re.search(r"cutting… (\d+)%", st.status.cget("text"))
    if m and int(m.group(1)) >= 55 and not mid:
        mid["t"] = st.status.cget("text")
        shot("demo_cutting.png")
    return not st.busy and st.job is None


st.fire()
pump_until(grab_mid, limit=90)
check("animation ran with progress", "t" in mid, mid.get("t", ""))
pdfs = list(pdf_dir.glob("*.pdf"))
check("laser file saved as PDF", len(pdfs) == 1 and pdfs[0].stat().st_size > 1000, str([p.name for p in pdfs]))
check("status says nothing went to a laser", "Nothing went to a laser" in st.status.cget("text"), st.status.cget("text"))
check("demo map now shows the cut wood", len(st.bed.used) == 1)
check("real sheet map untouched", real_map.read_text() == before)
pump_until(lambda: "3 waiting" not in st.jobs_btn.cget("text"), limit=10)  # clearing runs in the background
check("cut jobs cleared, Hub Deck (not cut) still waiting", "1 waiting" in st.jobs_btn.cget("text"), st.jobs_btn.cget("text"))
shot("demo_after.png")

st.reset_demo()
pump_until(lambda: "3 waiting" in str(st.jobs_btn.cget("text")), limit=10)
check("Reset demo: fresh wood and all jobs back", not st.bed.used and "3 waiting" in st.jobs_btn.cget("text"))

# the plain-file route still works in demo: open the whole Robot V2 frame-plates STEP
job = station.Job(st.cfg, "7831")
job.add_files([app / "samples" / "demo" / "robot-v2-frame-plates.step"])
job.build(6.0, 0.0)
check("whole Robot V2 studio: 2 plates kept, 3 thin ones skipped", len(job.parts) == 2 and sum("skipped" in n for n in job.notes) == 3,
      str([p.name for p in job.parts]))
st.destroy()
print(f"{sum(results)}/{len(results)} passed")
