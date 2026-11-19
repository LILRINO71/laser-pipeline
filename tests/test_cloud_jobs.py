"""Run: python tests/test_cloud_jobs.py
Needs the local add-on test servers with at least one top-up and one bottom-up job queued from team 7831:
    onshape-addon: node test/mock-onshape.mjs   and   npx wrangler dev --port 8787   (see onshape-addon/SETUP.md)

Laser Station <-> add-on server, end to end: list, load with the picked tops, mirror check, clear after cutting.
"""
import json, shutil, sys, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
repo = Path(__file__).resolve().parents[1]
scratch = repo / "tests" / "out"
scratch.mkdir(parents=True, exist_ok=True)
app = scratch / "app_cloud"
if app.exists():
    shutil.rmtree(app)
app.mkdir()
for f in ("station.pyw", "laser.py", "config.json"):
    shutil.copy2(repo / f, app / f)
for d in ("laserpipe", "samples"):
    shutil.copytree(repo / d, app / d, ignore=shutil.ignore_patterns("__pycache__"))
KEY = "test-station-key-0123456789abcdef"
(app / "config.local.json").write_text(json.dumps({"cloud_url": "http://localhost:8787", "station_key": KEY}))
sys.path.insert(0, str(app))

import importlib.machinery, importlib.util
import shapely.geometry as G
from laserpipe import cloud

results = []


def check(name, ok, extra=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if extra else ""))


cfg = {"cloud_url": "http://localhost:8787", "station_key": KEY}
jobs, calls = cloud.list_jobs(cfg)
check("station lists the queue", len(jobs) >= 2, f"{len(jobs)} jobs, {calls} calls")
try:
    cloud.list_jobs({"cloud_url": "http://localhost:8787", "station_key": "wrong-key-wrong-key-wrong-key-00"})
    check("wrong station key refused", False)
except RuntimeError as e:
    check("wrong station key refused", "station key" in str(e).lower(), str(e))
try:
    cloud.list_jobs({"cloud_url": "http://example.com", "station_key": KEY})
    check("plain http server refused", False)
except ValueError:
    check("plain http server refused", True)

loader = importlib.machinery.SourceFileLoader("station", str(app / "station.pyw"))
spec = importlib.util.spec_from_loader("station", loader)
station = importlib.util.module_from_spec(spec)
loader.exec_module(station)
st = station.Station()


def pump_until(fn, limit=40):
    t = time.time()

    def poll():
        if not fn() and time.time() - t < limit:
            st.after(30, poll)
        else:
            st.quit()

    st.after(0, poll)
    st.mainloop()
    st.update()


pump_until(lambda: "waiting" in str(st.jobs_btn.cget("text")))
check("button shows jobs waiting", f"{len(jobs)} waiting" in st.jobs_btn.cget("text"), st.jobs_btn.cget("text"))
check("button turns blue when jobs wait", st.jobs_btn.cget("style") == "Jobs.TButton")
st.open_cloud()
pump_until(lambda: len(st.cloud_tree.get_children()) == len(jobs))
check("list window shows every job", len(st.cloud_tree.get_children()) == len(jobs))

up = [j for j in jobs if j["top"]["normal"][2] > 0]
down = [j for j in jobs if j["top"]["normal"][2] < 0]
pick = [up[0]["id"], down[0]["id"]]
st.cloud_tree.selection_set(pick)
st.load_cloud()
pump_until(lambda: not st.loading and st.job is not None)
j = st.job
names = [r["name"] for r in j.raws]
check("both parts loaded with different names", len(names) == 2 and len(set(names)) == 2, str(names))
check("team taken from the job", st.team.get() == up[0]["team"], st.team.get())
check("quantities taken from the job", sorted(st.qty.values()) == sorted([up[0]["qty"], down[0]["qty"]]), str(st.qty))
check("both tops found in the STEP", all(r.get("top_picked") for r in j.raws))
check("parts placed on the sheet", j.sheets and sum(len(s.placements) for s in j.sheets) == up[0]["qty"] + down[0]["qty"])


def chirality(raw):
    pts = [tuple(q) for e in raw["edges"] for q in e["p"]]
    hole = [e for e in raw["edges"] if e["t"] == "C" and abs(e["r"] - 4) < 0.01][0]["c"]
    c = G.MultiPoint(pts).convex_hull.centroid
    far = max(pts, key=lambda q: (q[0] - hole[0]) ** 2 + (q[1] - hole[1]) ** 2)
    return (hole[0] - c.x) * (far[1] - c.y) - (hole[1] - c.y) * (far[0] - c.x)


a, b = chirality(j.raws[0]), chirality(j.raws[1])
check("top-up and bottom-up parts come out as mirror images", a * b < 0, f"{a:.0f} vs {b:.0f}")
st._sent(len(j.sheets) - 1, "Sheet sent.", None)
pump_until(lambda: len(st.cloud_jobs) == len(jobs) - 2, limit=20)
left, _ = cloud.list_jobs(cfg)
check("cut jobs cleared from the queue", not any(x["id"] in pick for x in left) and len(left) == len(jobs) - 2, f"{len(left)} left")
st.destroy()
print(f"{sum(results)}/{len(results)} passed")
