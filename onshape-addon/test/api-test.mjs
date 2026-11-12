// Server checks against the fake Onshape. Start both first:
//   node test/mock-onshape.mjs          (port 8788)
//   npx wrangler dev --port 8787        (uses .dev.vars, copy it from test/dev.vars.example)
//   node test/api-test.mjs
const W = process.env.WORKER || "http://localhost:8787";
const M = "http://localhost:8788";
const KEY = "test-station-key-0123456789abcdef";
const DOC = { documentId: "a".repeat(24), wv: "w", wvid: "b".repeat(24), elementId: "c".repeat(24), server: M };
let pass = 0, fail = 0;
const check = (name, ok, extra = "") => { ok ? pass++ : fail++; console.log(`${ok ? "PASS" : "FAIL"} ${name}${extra ? `  [${extra}]` : ""}`); };
const post = (path, sid, body) => fetch(W + path, {
  method: "POST",
  headers: { "content-type": "application/json", ...(sid ? { authorization: `Bearer ${sid}` } : {}) },
  body: JSON.stringify(body),
}).then(async (r) => ({ status: r.status, ...(await r.json()) }));
const station = (path, method = "GET", key = KEY) => fetch(W + path, { method, headers: { authorization: `Bearer ${key}` } });

// sign in the way the panel does (state made by the panel, session handed back in the #hash)
const state = [...crypto.getRandomValues(new Uint8Array(24))].map((b) => b.toString(16).padStart(2, "0")).join("");
let r = await fetch(`${W}/oauth/start?state=${state}&return=/panel.html`, { redirect: "manual" });
check("sign-in goes to Onshape", r.status === 302 && r.headers.get("location").startsWith(`${M}/oauth/authorize`));
r = await fetch(r.headers.get("location"), { redirect: "manual" });
r = await fetch(r.headers.get("location"), { redirect: "manual" });
const back = new URL(r.headers.get("location"));
const h = new URLSearchParams(back.hash.slice(1));
const sid = h.get("sid");
check("session comes back with the same state", h.get("state") === state && /^[0-9a-f]{64}$/.test(sid || ""));
r = await fetch(`${W}/oauth/callback?state=${state}&code=good-code`);
check("sign-in reply can't be replayed", r.status === 400);
r = await fetch(`${W}/oauth/start?state=${state}&return=https://evil.example.com/`);
check("sign-in can't return to another site", r.status === 400);

let f = await post("/api/face", sid, { ...DOC, faceId: "JHO" });
check("top face points up", JSON.stringify(f.normal) === "[0,0,1]" && f.partId === "JHD" && f.approxThicknessMm === 6, JSON.stringify(f.normal));
f = await post("/api/face", sid, { ...DOC, faceId: "JHK" });
check("bottom face points down (sign fixed by the server)", JSON.stringify(f.normal) === "[0,0,-1]", JSON.stringify(f.normal));
f = await post("/api/face", sid, { ...DOC, faceId: "JHS" });
check("side face refused", f.status === 400 && /side face/.test(f.error), f.error);
f = await post("/api/face", sid, { ...DOC, faceId: "JHC" });
check("curved face refused", f.status === 400 && /flat/.test(f.error), f.error);
f = await post("/api/face", sid, { ...DOC, faceId: "NOPE" });
check("unknown face refused", f.status === 400, f.error);
f = await post("/api/face", sid, { ...DOC, server: "https://evil.example.com", faceId: "JHO" });
check("token never sent to a non-Onshape server", f.status === 400, f.error);
f = await post("/api/face", null, { ...DOC, faceId: "JHO" });
check("no session -> sign in", f.status === 401 && f.signIn === true);

const before = await (await station("/api/station/jobs")).json();
const top = { normal: [0, 0, -1], origin: [0, 0, 0] };
let s = await post("/api/send", sid, { ...DOC, team: "", qty: 1, partId: "JHD", partName: "P", top });
check("team required", s.status === 400);
s = await post("/api/send", sid, { ...DOC, team: "T", qty: 99, partId: "JHD", partName: "P", top });
check("quantity limited", s.status === 400);
await fetch(`${M}/expire`); // Onshape forgets the token: the server must refresh it by itself
s = await post("/api/send", sid, { ...DOC, team: "Test team", qty: 3, partId: "JHD", partName: "Test L Plate", top });
check("send exports and queues the part", s.ok === true && s.waiting === before.jobs.length + 1, JSON.stringify(s));
const stats = await (await fetch(`${M}/stats`)).json();
check("expired Onshape token refreshed by itself", stats.refresh >= 1);

const list = await (await station("/api/station/jobs")).json();
const job = list.jobs.find((j) => j.id === s.id);
check("station sees the job with team, qty and top", job && job.team === "Test team" && job.qty === 3 && job.top.normal[2] === -1);
const step = await (await station(`/api/station/jobs/${s.id}/step`)).text();
check("station downloads the STEP", step.startsWith("ISO-10303-21"));
check("wrong station key refused", (await station("/api/station/jobs", "GET", "x".repeat(33))).status === 401);
check("no station key refused", (await fetch(`${W}/api/station/jobs`)).status === 401);
check("station deletes the job", (await station(`/api/station/jobs/${s.id}`, "DELETE")).status === 200);
check("deleted job is gone", (await station(`/api/station/jobs/${s.id}/step`)).status === 404);

r = await fetch(`${W}/panel.html`);
const csp = r.headers.get("content-security-policy") || "";
check("panel only embeddable in Onshape", /frame-ancestors https:\/\/\*\.onshape\.com/.test(csp), csp);
check("signing out ends the session", (await post("/api/signout", sid, {})).ok && (await post("/api/face", sid, { ...DOC, faceId: "JHO" })).status === 401);

console.log(`${pass}/${pass + fail} passed`);
process.exit(fail ? 1 : 0);
