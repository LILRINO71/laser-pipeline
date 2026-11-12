"""Jobs sent from the Onshape add-on (onshape-addon/). The laser PC only talks to the add-on's server with the
station key; it never needs an Onshape login or API key.

config: "cloud_url" (the add-on server, in config.json) and "station_key" (config.local.json, never in git).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from .job import ROOT

FOLDER = ROOT / "jobs" / "onshape"
_ID = re.compile(r"^[A-Za-z0-9-]{6,40}$")


def configured(cfg: dict) -> bool:
    return bool(cfg.get("cloud_url") and cfg.get("station_key"))


def _call(cfg: dict, path: str, method: str = "GET") -> bytes:
    url = str(cfg["cloud_url"]).rstrip("/") + path
    if not url.startswith("https://") and not url.startswith("http://localhost") and not url.startswith("http://127.0.0.1"):
        raise ValueError("The add-on server address must start with https://")
    req = urllib.request.Request(url, method=method, headers={"Authorization": f"Bearer {cfg['station_key']}", "User-Agent": "LaserStation"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error")
        except Exception:
            msg = None
        raise RuntimeError(msg or f"Add-on server error {e.code}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Can't reach the add-on server ({e.reason}). Is this PC online?") from None


def list_jobs(cfg: dict) -> tuple[list[dict], int]:
    """Oldest first. Each job: {id, team, qty, part, top: {normal, origin}, at (ms)}. Also this month's Onshape calls."""
    d = json.loads(_call(cfg, "/api/station/jobs"))
    jobs = [j for j in d.get("jobs", []) if _ID.match(str(j.get("id", "")))]
    jobs.sort(key=lambda j: j.get("at", 0))
    return jobs, int(d.get("apiCallsThisMonth", 0))


def download(cfg: dict, job: dict) -> Path:
    FOLDER.mkdir(parents=True, exist_ok=True)
    data = _call(cfg, f"/api/station/jobs/{job['id']}/step")
    if not data.startswith(b"ISO-10303-21"):
        raise RuntimeError(f"Job {job.get('part')} isn't a STEP file.")
    safe = re.sub(r"[^A-Za-z0-9 _-]", "_", str(job.get("part") or "part"))[:40].strip() or "part"
    p = FOLDER / f"{job['id']} {safe}.step"
    p.write_bytes(data)
    return p


def remove(cfg: dict, job_id: str) -> None:
    if _ID.match(job_id):
        _call(cfg, f"/api/station/jobs/{job_id}", method="DELETE")


def top_of(job: dict) -> dict | None:
    t = job.get("top") or {}
    n, o = t.get("normal"), t.get("origin")
    if isinstance(n, list) and len(n) == 3 and all(isinstance(v, (int, float)) for v in n):
        return {"normal": n, "origin": o if isinstance(o, list) and len(o) == 3 else None}
    return None
