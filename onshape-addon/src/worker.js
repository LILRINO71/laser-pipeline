// Laser Station add-on server (Cloudflare Worker).
// Students open the panel inside Onshape, sign in with their own Onshape login, click the plate's top face,
// and press Send. This server exports that one part as STEP through the Onshape API and keeps it in a queue.
// Laser Station at the laser PC lists the queue with the station key and downloads the jobs.
//
// Secrets (wrangler secret put): ONSHAPE_CLIENT_ID, ONSHAPE_CLIENT_SECRET, STATION_KEY
// Vars (wrangler.toml): OAUTH_BASE, API_HOST_PATTERN
// KV namespace binding: LASER  (sess:<hash>, state:<state>, job:<id>, count:<yyyy-mm>)

const API = "/api/v12";
const JOB_TTL = 14 * 24 * 3600;
const SESSION_TTL = 30 * 24 * 3600;
const MAX_JOBS = 100;

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    try {
      const route = ROUTES[`${req.method} ${url.pathname}`] || matchStation(req.method, url.pathname);
      if (!route) return json({ error: "Not found" }, 404);
      return await route(req, env, url, ctx);
    } catch (e) {
      if (e instanceof HttpError) return json({ error: e.message, signIn: e.signIn || undefined }, e.status);
      console.error(e && e.stack ? e.stack : e);
      return json({ error: "Server error: " + (e && e.message ? e.message : e) }, 500);
    }
  },
};

class HttpError extends Error {
  constructor(status, message, signIn = false) {
    super(message);
    this.status = status;
    this.signIn = signIn;
  }
}

const ROUTES = {
  "GET /": () => Response.redirect("https://github.com/LILRINO71/laser-pipeline", 302),
  "GET /oauth/start": oauthStart,
  "GET /oauth/callback": oauthCallback,
  "GET /api/config": (req, env) => json({ apiHostPattern: hostPattern(env).source }),
  "GET /api/me": me,
  "POST /api/face": face,
  "POST /api/send": send,
  "POST /api/signout": signOut,
};

function matchStation(method, path) {
  if (method === "GET" && path === "/api/station/jobs") return stationList;
  const m = path.match(/^\/api\/station\/jobs\/([A-Za-z0-9-]{6,40})(\/step)?$/);
  if (!m) return null;
  if (method === "GET" && m[2]) return (req, env, url) => stationStep(req, env, m[1]);
  if (method === "DELETE" && !m[2]) return (req, env, url) => stationDelete(req, env, m[1]);
  return null;
}

// ------------------------------------------------------------------ helpers

function json(obj, status = 200, headers = {}) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...headers },
  });
}

function randomHex(bytes) {
  const a = new Uint8Array(bytes);
  crypto.getRandomValues(a);
  return [...a].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function sha256(text) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function hostPattern(env) {
  return new RegExp(env.API_HOST_PATTERN || "^https://([a-z0-9-]+\\.)?onshape\\.com$");
}

function oauthBase(env) {
  return (env.OAUTH_BASE || "https://oauth.onshape.com").replace(/\/$/, "");
}

const ID = /^[0-9a-f]{24}$/;

function docRef(body, env) {
  const r = {
    server: String(body.server || "https://cad.onshape.com").replace(/\/$/, ""),
    did: String(body.documentId || ""),
    wv: String(body.wv || "w"),
    wvid: String(body.wvid || ""),
    eid: String(body.elementId || ""),
    configuration: String(body.configuration || ""),
  };
  if (!hostPattern(env).test(r.server)) throw new HttpError(400, "That isn't an Onshape page.");
  if (!ID.test(r.did) || !ID.test(r.wvid) || !ID.test(r.eid) || !["w", "v"].includes(r.wv))
    throw new HttpError(400, "Open this panel from a Part Studio.");
  if (r.configuration.length > 2000) throw new HttpError(400, "Configuration too long.");
  return r;
}

async function readJson(req) {
  if ((req.headers.get("content-length") || 0) > 20000) throw new HttpError(413, "Request too big.");
  try {
    return await req.json();
  } catch {
    throw new HttpError(400, "Bad request.");
  }
}

// ------------------------------------------------------------------ sign in (Onshape OAuth)
// No cookies: the panel lives in an iframe inside Onshape. The panel makes a random state, keeps it in its own
// storage, and only accepts the session that comes back with that same state.

async function oauthStart(req, env, url) {
  const state = url.searchParams.get("state") || "";
  const ret = url.searchParams.get("return") || "/panel.html";
  if (!/^[0-9a-f]{32,64}$/.test(state)) throw new HttpError(400, "Bad sign-in request.");
  if (!ret.startsWith("/panel.html")) throw new HttpError(400, "Bad return page.");
  if (!env.ONSHAPE_CLIENT_ID) throw new HttpError(500, "The add-on isn't set up yet (no Onshape client id).");
  await env.LASER.put(`state:${state}`, JSON.stringify({ ret }), { expirationTtl: 600 });
  const q = new URLSearchParams({
    response_type: "code",
    client_id: env.ONSHAPE_CLIENT_ID,
    redirect_uri: `${url.origin}/oauth/callback`,
    state,
  });
  return Response.redirect(`${oauthBase(env)}/oauth/authorize?${q}`, 302);
}

async function oauthCallback(req, env, url) {
  const state = url.searchParams.get("state") || "";
  const code = url.searchParams.get("code") || "";
  if (!/^[0-9a-f]{32,64}$/.test(state)) throw new HttpError(400, "Bad sign-in reply.");
  const saved = await env.LASER.get(`state:${state}`, "json");
  if (!saved) throw new HttpError(400, "Sign-in took too long. Close the panel and open it again.");
  await env.LASER.delete(`state:${state}`);
  if (!code) throw new HttpError(400, "Onshape didn't allow the sign-in: " + (url.searchParams.get("error") || "no code"));
  const tok = await tokenRequest(env, {
    grant_type: "authorization_code",
    code,
    redirect_uri: `${url.origin}/oauth/callback`,
  });
  const sid = randomHex(32);
  await saveSession(env, await sha256(sid), tok);
  const back = new URL(saved.ret, url.origin);
  back.hash = `sid=${sid}&state=${state}`;
  return Response.redirect(back.toString(), 302);
}

async function tokenRequest(env, params) {
  const r = await fetch(`${oauthBase(env)}/oauth/token`, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded", accept: "application/json" },
    body: new URLSearchParams({ ...params, client_id: env.ONSHAPE_CLIENT_ID, client_secret: env.ONSHAPE_CLIENT_SECRET }),
  });
  const t = await r.json().catch(() => ({}));
  if (!r.ok || !t.access_token) throw new HttpError(401, "Onshape sign-in failed. Sign in again.", true);
  return t;
}

async function saveSession(env, key, tok, old = {}) {
  const s = {
    access: tok.access_token,
    refresh: tok.refresh_token || old.refresh,
    exp: Date.now() + (Number(tok.expires_in) || 3600) * 1000,
  };
  await env.LASER.put(`sess:${key}`, JSON.stringify(s), { expirationTtl: SESSION_TTL });
  return s;
}

async function session(req, env) {
  const h = req.headers.get("authorization") || "";
  const sid = h.startsWith("Bearer ") ? h.slice(7) : "";
  if (!/^[0-9a-f]{64}$/.test(sid)) throw new HttpError(401, "Sign in with Onshape first.", true);
  const key = await sha256(sid);
  const s = await env.LASER.get(`sess:${key}`, "json");
  if (!s) throw new HttpError(401, "Sign in with Onshape first.", true);
  return { key, s };
}

async function me(req, env) {
  await session(req, env);
  return json({ signedIn: true });
}

async function signOut(req, env) {
  const { key } = await session(req, env);
  await env.LASER.delete(`sess:${key}`);
  return json({ ok: true });
}

// ------------------------------------------------------------------ Onshape API calls

async function onshape(env, sess, url, init = {}, raw = false) {
  let { s } = sess;
  for (let attempt = 0; attempt < 2; attempt++) {
    if (s.exp - Date.now() < 60000 || attempt === 1) {
      if (!s.refresh) throw new HttpError(401, "Sign in with Onshape again.", true);
      s = sess.s = await saveSession(env, sess.key, await tokenRequest(env, { grant_type: "refresh_token", refresh_token: s.refresh }), s);
    }
    sess.calls = (sess.calls || 0) + 1;
    const r = await fetch(url, {
      ...init,
      headers: { authorization: `Bearer ${s.access}`, accept: raw ? "*/*" : "application/json", ...(init.headers || {}) },
    });
    if (r.status === 401 && attempt === 0) continue;
    if (r.status === 403 || r.status === 404) throw new HttpError(403, "Onshape won't share this document with the add-on (no access).");
    if (r.status === 429) throw new HttpError(429, "Onshape says too many requests. Wait a minute.");
    if (!r.ok) throw new HttpError(502, `Onshape error ${r.status}.`);
    return raw ? r : r.json();
  }
}

async function countCalls(env, sess, ctx) {
  if (!sess.calls) return;
  const key = `count:${new Date().toISOString().slice(0, 7)}`;
  const job = (async () => {
    const n = Number((await env.LASER.get(key)) || 0);
    await env.LASER.put(key, String(n + sess.calls), { expirationTtl: 400 * 24 * 3600 });
  })();
  ctx && ctx.waitUntil ? ctx.waitUntil(job) : await job;
}

function vec(v) {
  return v && [Number(v.x) || 0, Number(v.y) || 0, Number(v.z) || 0];
}
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const mid = (box) => box && box.minCorner && box.maxCorner && vec(box.minCorner).map((v, i) => (v + vec(box.maxCorner)[i]) / 2);

// Find the picked face in the Part Studio and work out which way is "up" (out of the part).
function describeFace(details, faceId) {
  for (const body of details.bodies || []) {
    const f = (body.faces || []).find((x) => x.id === faceId);
    if (!f) continue;
    if (String(body.type || "").toUpperCase() !== "SOLID") throw new HttpError(400, "That's not a solid part. Click a face of the plate.");
    const surf = f.surface || {};
    if (String(surf.type || "").toUpperCase() !== "PLANE") throw new HttpError(400, "That face isn't flat. Click the flat top of the plate.");
    let n = vec(surf.normal || surf.direction);
    const o = vec(surf.origin) || [0, 0, 0];
    const len = Math.hypot(...n);
    if (!len) throw new HttpError(502, "Onshape didn't say which way the face points.");
    n = n.map((v) => v / len);
    // A plate's top is parallel to its biggest flat face; anything else is an edge/side face.
    const flat = (body.faces || []).filter((x) => String((x.surface || {}).type || "").toUpperCase() === "PLANE" && x.area);
    const biggest = flat.reduce((a, x) => (x.area > a.area ? x : a), f);
    const bn = vec(biggest.surface.normal || biggest.surface.direction);
    const bl = Math.hypot(...bn);
    if (bl && Math.abs(dot(n, bn)) / bl < 0.9999)
      throw new HttpError(400, "That's a side face. Click the big flat face on top of the plate.");
    // Outward check that doesn't depend on Onshape's sign conventions: "up" points away from the middle of the part.
    const fc = mid(f.box) || o;
    const corners = (body.faces || []).flatMap((x) => (x.box && x.box.minCorner ? [vec(x.box.minCorner), vec(x.box.maxCorner)] : []));
    const pts = corners.length ? corners : (body.vertices || []).map((v) => vec(v.point));
    if (pts.length) {
      const c = pts.reduce((a, p) => a.map((v, i) => v + p[i] / pts.length), [0, 0, 0]);
      if (dot(n, sub(fc, c)) < 0) n = n.map((v) => -v);
    }
    // thickness straight through the face (only exact for flat plates; the laser PC checks again)
    const along = pts.map((p) => dot(p, n));
    const thk = along.length ? (Math.max(...along) - Math.min(...along)) * 1000 : null;
    return {
      faceId,
      partId: body.id,
      partName: (body.properties && body.properties.name) || "Part",
      normal: n.map((v) => +v.toFixed(9)),
      origin: o.map((v) => +(v * 1000).toFixed(4)), // metres -> mm
      areaMm2: f.area ? +(f.area * 1e6).toFixed(1) : null,
      approxThicknessMm: thk && +thk.toFixed(2),
    };
  }
  return null;
}

async function bodyDetails(env, sess, r, fresh) {
  const q = r.configuration ? `?configuration=${encodeURIComponent(r.configuration)}` : "";
  const url = `${r.server}${API}/partstudios/d/${r.did}/${r.wv}/${r.wvid}/e/${r.eid}/bodydetails${q}`;
  // cache for 2 minutes per signed-in student so clicking around doesn't spend API calls
  const cacheKey = new Request(`https://cache.laser-station/${sess.key}/${await sha256(url)}`);
  const cache = typeof caches !== "undefined" ? caches.default : null;
  if (!fresh && cache) {
    const hit = await cache.match(cacheKey);
    if (hit) return hit.json();
  }
  const d = await onshape(env, sess, url);
  if (cache) await cache.put(cacheKey, new Response(JSON.stringify(d), { headers: { "cache-control": "max-age=120" } }));
  return d;
}

async function face(req, env, url, ctx) {
  const sess = await session(req, env);
  const body = await readJson(req);
  const r = docRef(body, env);
  const faceId = String(body.faceId || "");
  if (!/^[A-Za-z0-9._:-]{1,64}$/.test(faceId)) throw new HttpError(400, "Click a face first.");
  let info = describeFace(await bodyDetails(env, sess, r, false), faceId);
  if (!info) info = describeFace(await bodyDetails(env, sess, r, true), faceId); // model changed since the cache
  await countCalls(env, sess, ctx);
  if (!info) throw new HttpError(400, "Couldn't find that face. Click a face of a part in this Part Studio.");
  return json(info);
}

async function send(req, env, url, ctx) {
  const sess = await session(req, env);
  const body = await readJson(req);
  const r = docRef(body, env);
  const team = String(body.team || "").trim().slice(0, 30);
  const qty = Math.round(Number(body.qty));
  if (!team) throw new HttpError(400, "Type your team name.");
  if (!(qty >= 1 && qty <= 50)) throw new HttpError(400, "How many: 1 to 50.");
  const top = body.top || {};
  const n = (top.normal || []).map(Number);
  const o = (top.origin || []).map(Number);
  if (n.length !== 3 || o.length !== 3 || ![...n, ...o].every(Number.isFinite) || Math.abs(Math.hypot(...n) - 1) > 1e-3)
    throw new HttpError(400, "Click the top face again.");
  const partId = String(body.partId || "");
  if (!/^[A-Za-z0-9._:-]{1,64}$/.test(partId)) throw new HttpError(400, "Click the top face again.");
  const partName = String(body.partName || "Part").slice(0, 60);

  const listed = await env.LASER.list({ prefix: "job:", limit: MAX_JOBS + 1 });
  if (listed.keys.length >= MAX_JOBS) throw new HttpError(429, "The laser queue is full. Ask someone at the laser to clear old jobs.");

  // STEP export of just this part. Version links (v) work too; microversions can't be exported.
  const tr = await onshape(env, sess, `${r.server}${API}/partstudios/d/${r.did}/${r.wv}/${r.wvid}/e/${r.eid}/translations`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      formatName: "STEP",
      partIds: partId,
      storeInDocument: false,
      configuration: r.configuration || undefined,
      destinationName: partName,
    }),
  });
  let info = tr;
  const t0 = Date.now();
  while (info.requestState === "ACTIVE" && Date.now() - t0 < 60000) {
    await new Promise((res) => setTimeout(res, Date.now() - t0 < 6000 ? 1500 : 3000));
    info = await onshape(env, sess, `${r.server}${API}/translations/${encodeURIComponent(tr.id)}`);
  }
  if (info.requestState !== "DONE" || !(info.resultExternalDataIds || []).length) {
    await countCalls(env, sess, ctx);
    throw new HttpError(502, info.requestState === "FAILED" ? `Onshape couldn't export it: ${info.failureReason || "unknown reason"}` : "Onshape took too long to export. Try again.");
  }
  const file = await onshape(env, sess, `${r.server}${API}/documents/d/${r.did}/externaldata/${encodeURIComponent(info.resultExternalDataIds[0])}`, {}, true);
  const step = await file.text();
  await countCalls(env, sess, ctx);
  if (!step.startsWith("ISO-10303-21")) throw new HttpError(502, "Onshape sent something that isn't a STEP file.");
  if (step.length > 20e6) throw new HttpError(413, "That part is too big a file for the queue.");

  const id = `${Date.now()}-${randomHex(4)}`;
  const meta = { team, qty, part: partName, top: { normal: n, origin: o }, at: Date.now() };
  await env.LASER.put(`job:${id}`, step, { expirationTtl: JOB_TTL, metadata: meta });
  return json({ ok: true, id, waiting: listed.keys.length + 1 });
}

// ------------------------------------------------------------------ Laser Station (station key)

async function stationAuth(req, env) {
  const h = req.headers.get("authorization") || "";
  const got = new TextEncoder().encode(h.startsWith("Bearer ") ? h.slice(7) : "");
  const want = new TextEncoder().encode(env.STATION_KEY || "");
  const same = want.length >= 24 && got.length === want.length && crypto.subtle.timingSafeEqual(got, want);
  if (!same) throw new HttpError(401, "Wrong station key.");
}

async function stationList(req, env) {
  await stationAuth(req, env);
  const jobs = [];
  let cursor;
  do {
    const page = await env.LASER.list({ prefix: "job:", cursor });
    for (const k of page.keys) jobs.push({ id: k.name.slice(4), ...(k.metadata || {}) });
    cursor = page.list_complete ? null : page.cursor;
  } while (cursor);
  const calls = Number((await env.LASER.get(`count:${new Date().toISOString().slice(0, 7)}`)) || 0);
  return json({ jobs, apiCallsThisMonth: calls });
}

async function stationStep(req, env, id) {
  await stationAuth(req, env);
  const step = await env.LASER.get(`job:${id}`);
  if (step === null) throw new HttpError(404, "That job is gone (already cut or older than 2 weeks).");
  return new Response(step, { headers: { "content-type": "application/step", "cache-control": "no-store" } });
}

async function stationDelete(req, env, id) {
  await stationAuth(req, env);
  await env.LASER.delete(`job:${id}`);
  return json({ ok: true });
}
