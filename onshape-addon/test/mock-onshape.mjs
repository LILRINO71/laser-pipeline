// Fake Onshape for testing the add-on with no Onshape account and no API calls.
// Serves: OAuth authorize/token, bodydetails, STEP translation + download, and frame.html,
// a stand-in for the Part Studio page that hosts the panel and sends SELECTION messages like Onshape does.
//   node test/mock-onshape.mjs      (port 8788; the worker runs on 8787 with .dev.vars pointing here;
//   open /frame.html?worker=http://localhost:PORT if the worker got another port)
import { createServer } from "node:http";
import { readFileSync } from "node:fs";

const PORT = 8788;
const WORKER = process.env.WORKER || "http://localhost:8787";
const STEP = readFileSync(new URL("./fixtures/l-plate.step", import.meta.url), "utf8");
const DID = "aaaaaaaaaaaaaaaaaaaaaaaa", WID = "bbbbbbbbbbbbbbbbbbbbbbbb", EID = "cccccccccccccccccccccccc";
const stats = { authorize: 0, token: 0, api: 0, bodydetails: 0, translations: 0, polls: 0, downloads: 0, refresh: 0, badAuth: 0 };
let tokenGen = 1;
let validTokens = new Set();
let pollCount = 0;

// L plate, 6 mm (metres, like the real API). Plane normals are deliberately reported un-oriented
// (bottom face says +Z) to prove the server works out "up" itself.
const box = (a, b) => ({ minCorner: { x: a[0], y: a[1], z: a[2] }, maxCorner: { x: b[0], y: b[1], z: b[2] } });
const plane = (n, o) => ({ type: "PLANE", normal: { x: n[0], y: n[1], z: n[2] }, origin: { x: o[0], y: o[1], z: o[2] } });
const BODY = {
  id: "JHD", type: "SOLID", properties: { name: "Test L Plate" },
  faces: [
    { id: "JHO", area: 0.0028, surface: plane([0, 0, 1], [0, 0, 0.006]), box: box([0, 0, 0.006], [0.1, 0.06, 0.006]) },
    { id: "JHK", area: 0.0028, surface: plane([0, 0, 1], [0, 0, 0]), box: box([0, 0, 0], [0.1, 0.06, 0]) },
    { id: "JHS", area: 0.00012, surface: plane([1, 0, 0], [0.1, 0, 0]), box: box([0.1, 0, 0], [0.1, 0.02, 0.006]) },
    { id: "JHC", area: 0.00015, surface: { type: "CYLINDER", origin: { x: 0.085, y: 0.01, z: 0 } }, box: box([0.081, 0.006, 0], [0.089, 0.014, 0.006]) },
  ],
};

function send(res, status, body, type = "application/json") {
  res.writeHead(status, { "content-type": type, "cache-control": "no-store" });
  res.end(typeof body === "string" ? body : JSON.stringify(body));
}

function authed(req) {
  const t = (req.headers.authorization || "").replace(/^Bearer /, "");
  if (!validTokens.has(t)) { stats.badAuth++; return false; }
  return true;
}

async function readBody(req) {
  let b = "";
  for await (const c of req) b += c;
  return b;
}

const frame = (WORKER) => `<!doctype html><meta charset="utf-8"><title>Fake Part Studio</title>
<style>body{font:14px system-ui;margin:0;display:grid;grid-template-columns:320px 1fr;height:100vh}
#canvas{padding:16px;background:#eef1f4}button{margin:4px 4px 4px 0;padding:6px 10px}iframe{border:0;border-right:1px solid #ccc;width:320px;height:100vh}
pre{font-size:11px;white-space:pre-wrap;max-height:50vh;overflow:auto;background:#fff;padding:8px}</style>
<iframe id="panel" src="${WORKER}/panel.html?documentId=${DID}&wv=w&wvid=${WID}&elementId=${EID}&configuration="></iframe>
<div id="canvas"><h2>Fake Part Studio (test)</h2>
<p>Pretend to click in the 3D view:</p>
<button id="top">Top face</button><button id="bottom">Bottom face</button><button id="side">Side face</button>
<button id="hole">Hole (curved)</button><button id="body">Whole part</button><button id="clear">Click empty space</button>
<p>Messages from the panel:</p><pre id="log"></pre></div>

<script>
const f=document.getElementById('panel'), log=document.getElementById('log');
const sel=(s)=>f.contentWindow.postMessage({messageName:'SELECTION',documentId:'${DID}',workspaceId:'${WID}',elementId:'${EID}',selections:s},'${WORKER}');
const ent=(id,t)=>[{selectionType:'ENTITY',selectionId:id,entityType:t}];
const on=(id,fn)=>document.getElementById(id).addEventListener('click',fn);
on('top',()=>sel(ent('JHO','FACE'))); on('bottom',()=>sel(ent('JHK','FACE'))); on('side',()=>sel(ent('JHS','FACE')));
on('hole',()=>sel(ent('JHC','FACE'))); on('body',()=>sel([{selectionType:'BODY',selectionId:'JHD',bodyType:'SOLID'}]));
on('clear',()=>sel([]));
window.messages=[];
addEventListener('message',e=>{if(e.origin!=='${WORKER}')return;window.messages.push(e.data);log.textContent+=JSON.stringify(e.data)+'\\n';});
</script>`;

createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const p = url.pathname;
  if (p === "/frame.html") {
    const w = url.searchParams.get("worker") || WORKER; // ?worker=http://localhost:8789 when 8787 is taken
    if (!/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(w)) return send(res, 400, "bad worker");
    return send(res, 200, frame(w), "text/html");
  }
  if (p === "/stats") return send(res, 200, stats);
  if (p === "/expire") { validTokens = new Set(); return send(res, 200, { ok: true }); } // forces a refresh
  if (p === "/oauth/authorize") {
    stats.authorize++;
    if (url.searchParams.get("client_id") !== "test-client") return send(res, 400, { error: "bad client" });
    const back = new URL(url.searchParams.get("redirect_uri"));
    back.searchParams.set("code", "good-code");
    back.searchParams.set("state", url.searchParams.get("state"));
    res.writeHead(302, { location: back.toString() });
    return res.end();
  }
  if (p === "/oauth/token" && req.method === "POST") {
    const f = new URLSearchParams(await readBody(req));
    if (f.get("client_secret") !== "test-secret") return send(res, 401, { error: "bad secret" });
    const ok = (f.get("grant_type") === "authorization_code" && f.get("code") === "good-code") ||
      (f.get("grant_type") === "refresh_token" && f.get("refresh_token") === "refresh-1");
    if (!ok) return send(res, 400, { error: "invalid_grant" });
    if (f.get("grant_type") === "refresh_token") stats.refresh++; else stats.token++;
    const t = `tok-${tokenGen++}`;
    validTokens.add(t);
    return send(res, 200, { access_token: t, refresh_token: "refresh-1", expires_in: 3600, token_type: "Bearer" });
  }
  if (p.startsWith("/api/")) {
    stats.api++;
    if (!authed(req)) return send(res, 401, { message: "Unauthenticated" });
    if (p === `/api/v12/partstudios/d/${DID}/w/${WID}/e/${EID}/bodydetails`) { stats.bodydetails++; return send(res, 200, { bodies: [BODY] }); }
    if (p === `/api/v12/partstudios/d/${DID}/w/${WID}/e/${EID}/translations` && req.method === "POST") {
      stats.translations++;
      const b = JSON.parse(await readBody(req));
      if (b.formatName !== "STEP" || b.partIds !== "JHD") return send(res, 400, { message: "bad export request " + JSON.stringify(b) });
      pollCount = 0;
      return send(res, 200, { id: "tr-1", requestState: "ACTIVE" });
    }
    if (p === "/api/v12/translations/tr-1") {
      stats.polls++;
      pollCount++;
      return send(res, 200, pollCount < 2 ? { id: "tr-1", requestState: "ACTIVE" } : { id: "tr-1", requestState: "DONE", resultExternalDataIds: ["ext-1"] });
    }
    if (p === `/api/v12/documents/d/${DID}/externaldata/ext-1`) { stats.downloads++; return send(res, 200, STEP, "application/step"); }
    return send(res, 404, { message: "no such endpoint " + p });
  }
  send(res, 404, "not found", "text/plain");
}).listen(PORT, () => console.log(`fake Onshape on http://localhost:${PORT}  (frame: /frame.html)`));
