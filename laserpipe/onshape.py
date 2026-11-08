"""Pull flat plate profiles out of an Onshape Part Studio with ONE API call.

A FeatureScript runs inside Onshape, finds every solid part, picks its biggest flat face,
and sends back that face's edges (sampled points, plus centre/radius for circles) in the
face's own 2D coordinates, in mm. No drawing, no DXF export, no translation polling.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]

PROFILE_SCRIPT = r"""
function(context is Context, queries is map)
{
    var out = [];
    for (var body in evaluateQuery(context, qBodyType(qEverything(EntityType.BODY), BodyType.SOLID)))
    {
        var faces = evaluateQuery(context, qGeometry(qOwnedByBody(body, EntityType.FACE), GeometryType.PLANE));
        if (size(faces) == 0)
            continue;
        var best = faces[0];
        var bestA = 0 * meter ^ 2;
        for (var f in faces)
        {
            var a = evArea(context, { "entities" : f });
            if (a > bestA)
            {
                bestA = a;
                best = f;
            }
        }
        var plane = evPlane(context, { "face" : best });
        var bb = evBox3d(context, { "topology" : body, "cSys" : planeToCSys(plane), "tight" : true });
        var edges = [];
        for (var e in evaluateQuery(context, qAdjacent(best, AdjacencyType.EDGE, EntityType.EDGE)))
        {
            var len = evLength(context, { "entities" : e }) / millimeter;
            var c = evCurveDefinition(context, { "edge" : e });
            var rec = { "len" : len, "t" : "S" };
            var n = 3 + floor(len);
            if (c is Line)
            {
                rec.t = "L";
                n = 2;
            }
            else if (c is Circle)
            {
                rec.t = "C";
                var cc = worldToPlane(plane, c.coordSystem.origin) / millimeter;
                rec.c = [cc[0], cc[1]];
                rec.r = c.radius / millimeter;
                n = 5;
            }
            if (n > 400)
                n = 400;
            var params = [];
            for (var i = 0; i < n; i += 1)
                params = append(params, i / (n - 1));
            var tl = evEdgeTangentLines(context, { "edge" : e, "parameters" : params, "arcLengthParameterization" : true });
            var pts = [];
            for (var l in tl)
            {
                var p = worldToPlane(plane, l.origin) / millimeter;
                pts = append(pts, [p[0], p[1]]);
            }
            rec.p = pts;
            edges = append(edges, rec);
        }
        out = append(out, {
                    "name" : getProperty(context, { "entity" : body, "propertyType" : PropertyType.NAME }),
                    "thk" : (bb.maxCorner[2] - bb.minCorner[2]) / millimeter,
                    "area" : bestA / (millimeter ^ 2),
                    "edges" : edges });
    }
    return out;
}
"""

URL_RE = re.compile(
    r"https://(?P<host>[^/]+)/documents/(?P<did>[0-9a-f]{24})/(?P<wvm>[wvm])/(?P<wvmid>[0-9a-f]{24})/e/(?P<eid>[0-9a-f]{24})"
)


def parse_url(url: str) -> dict:
    m = URL_RE.search(url)
    if not m:
        raise SystemExit(
            "That doesn't look like an Onshape tab link.\n"
            "Open the Part Studio tab with your laser plates and copy the whole address bar, e.g.\n"
            "https://cad.onshape.com/documents/<doc>/w/<workspace>/e/<tab>"
        )
    return m.groupdict()


def _load_env() -> None:
    """Read KEY=VALUE lines from .env files without overriding real env vars."""
    for f in [ROOT / ".env", Path(os.environ.get("ONSHAPE_ENV_FILE", "")) if os.environ.get("ONSHAPE_ENV_FILE") else None]:
        if f and f.is_file():
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class CallBudget:
    """Counts every Onshape request in a log and refuses to go past the yearly cap."""

    def __init__(self):
        self.log = Path(os.environ.get("ONSHAPE_CALL_LOG", ROOT / "api_calls.log"))
        self.limit = int(os.environ.get("ONSHAPE_CALL_LIMIT", "2500"))

    def used_this_year(self) -> int:
        if not self.log.is_file():
            return 0
        year = str(dt.date.today().year)
        return sum(1 for ln in self.log.read_text(encoding="utf-8").splitlines() if ln.startswith(year) and " 401 " not in ln)

    def check_and_record(self, method: str, path: str) -> None:
        used = self.used_this_year()
        if used >= self.limit - 5:
            raise SystemExit(f"Onshape call cap reached ({used}/{self.limit} this year). Not calling the API.")
        with self.log.open("a", encoding="utf-8") as f:
            f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {method} {path}\n")


def _decode(v):
    """Turn Onshape's typed BTFSValue JSON into plain Python."""
    if isinstance(v, dict) and "btType" in v or isinstance(v, dict) and "typeTag" in v:
        bt = v.get("btType", "")
        val = v.get("value")
        if bt.endswith("Array"):
            return [_decode(x) for x in val]
        if bt.endswith("Map"):
            return {_decode(kv["key"]): _decode(kv["value"]) for kv in val}
        return val
    return v


def fetch_profiles(url: str, cache_dir: Path | None = None, use_cache: bool = False) -> tuple[list, dict]:
    ref = parse_url(url)
    cache = (cache_dir or ROOT / "cache") / f"{ref['did']}_{ref['eid']}_{ref['wvmid']}.json"
    if use_cache and cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8")), ref

    _load_env()
    ak, sk = os.environ.get("ONSHAPE_ACCESS_KEY"), os.environ.get("ONSHAPE_SECRET_KEY")
    if not ak or not sk:
        raise SystemExit("No Onshape API keys. Put ONSHAPE_ACCESS_KEY and ONSHAPE_SECRET_KEY in laser-pipeline\\.env")

    path = f"/api/v6/partstudios/d/{ref['did']}/{ref['wvm']}/{ref['wvmid']}/e/{ref['eid']}/featurescript"
    CallBudget().check_and_record("POST", path)
    auth = base64.b64encode(f"{ak}:{sk}".encode()).decode()
    r = requests.post(
        f"https://{ref['host']}{path}",
        json={"script": PROFILE_SCRIPT.strip()},
        params={"rollbackBarIndex": -1},
        headers={"Authorization": f"Basic {auth}", "Accept": "application/json;charset=UTF-8; qs=0.09"},
        timeout=180,
    )
    if r.status_code == 404:
        raise SystemExit("Onshape says that tab doesn't exist or isn't a Part Studio. Link the Part Studio tab, not a drawing or assembly.")
    if r.status_code in (401, 403):
        raise SystemExit(f"Onshape refused the API keys ({r.status_code}). Check .env, and that the keys belong to the account that owns {ref['host']}.")
    if not r.ok:
        raise SystemExit(f"Onshape error {r.status_code}: {r.text[:800]}")
    body = r.json()
    for n in body.get("notices", []):
        msg = n.get("message", {}).get("message") if isinstance(n.get("message"), dict) else n.get("message")
        if n.get("level") == "ERROR" or "error" in str(msg).lower():
            raise SystemExit(f"FeatureScript error in Onshape: {msg}")
    parts = _decode(body.get("result")) or []
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(parts), encoding="utf-8")
    return parts, ref
