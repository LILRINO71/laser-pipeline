// Laser Station panel inside Onshape's right-side panel.
// Onshape opens it as panel.html?documentId=..&wv=..&wvid=..&elementId=..&configuration=..
"use strict";

const $ = (id) => document.getElementById(id);
const q = new URLSearchParams(location.search);
const doc = {
  documentId: q.get("documentId") || "",
  wv: q.get("wv") || "w",
  wvid: q.get("wvid") || "",
  elementId: q.get("elementId") || "",
  configuration: q.get("configuration") || "",
};
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage blocked: works until the panel closes */ } },
  del(k) { try { localStorage.removeItem(k); } catch { /* ignore */ } },
};
let memSid = null; // fallback when storage is blocked
let parentOrigin = null;
let picked = null; // face info from the server
let lastFaceId = null;

function sid() { return store.get("ls_sid") || memSid; }

function randomHex(n) {
  const a = new Uint8Array(n);
  crypto.getRandomValues(a);
  return [...a].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function api(path, body) {
  const r = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: { "content-type": "application/json", ...(sid() ? { authorization: `Bearer ${sid()}` } : {}) },
    body: body ? JSON.stringify({ ...doc, server: parentOrigin, ...body }) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (data.signIn) { forgetSession(); showSignIn(); }
  if (!r.ok) throw new Error(data.error || `Error ${r.status}`);
  return data;
}

// ------------------------------------------------------------ sign in

function takeSessionFromHash() {
  if (!location.hash.includes("sid=")) return;
  const h = new URLSearchParams(location.hash.slice(1));
  const want = store.get("ls_oauth_state");
  // only accept a session that comes back with the state this panel made
  if (want && h.get("state") === want && /^[0-9a-f]{64}$/.test(h.get("sid") || "")) {
    store.set("ls_sid", h.get("sid"));
    memSid = h.get("sid");
  }
  store.del("ls_oauth_state");
  history.replaceState(null, "", location.pathname + location.search);
}

function forgetSession() { store.del("ls_sid"); memSid = null; }

function showSignIn() {
  $("signin").hidden = false;
  $("main").hidden = true;
  $("signout").hidden = true;
}

function startSignIn() {
  const state = randomHex(24);
  store.set("ls_oauth_state", state);
  if (store.get("ls_oauth_state") !== state) {
    $("signin").querySelector("p").textContent = "This browser is blocking the add-on's storage. Allow site data for this page, then try again.";
    return;
  }
  location.href = `/oauth/start?${new URLSearchParams({ state, return: location.pathname + location.search })}`;
}

// ------------------------------------------------------------ Onshape messages

function post(messageName, extra = {}) {
  if (!parentOrigin || window.parent === window) return;
  window.parent.postMessage({ documentId: doc.documentId, workspaceId: doc.wvid, elementId: doc.elementId, messageName, ...extra }, parentOrigin);
}

// Onshape's SELECTION message lists what's selected; dig out the faces wherever they sit in the message.
function facesIn(msg) {
  const found = [];
  const walk = (v, depth) => {
    if (!v || typeof v !== "object" || depth > 5) return;
    if (Array.isArray(v)) { v.forEach((x) => walk(x, depth + 1)); return; }
    if (typeof v.selectionId === "string") {
      const kind = String(v.entityType || v.selectionType || "").toUpperCase();
      found.push({ id: v.selectionId, face: kind === "FACE" || kind === "" });
      return;
    }
    Object.values(v).forEach((x) => walk(x, depth + 1));
  };
  walk(msg, 0);
  return found;
}

function onMessage(e) {
  if (e.origin !== parentOrigin || !e.data || typeof e.data !== "object") return;
  if (String(e.data.messageName || "").toUpperCase() !== "SELECTION") return;
  const sel = facesIn(e.data);
  if (!sel.length) return; // cleared selection: keep the last pick
  const faces = sel.filter((s) => s.face);
  if (!faces.length) { faceStatus("bad", "That's not a face. Click the flat top of the plate."); return; }
  pickFace(faces[faces.length - 1].id);
}

async function pickFace(faceId) {
  if (faceId === lastFaceId && picked) return;
  lastFaceId = faceId;
  faceStatus("", "Checking that face…");
  picked = null;
  updateSend();
  try {
    const info = await api("/api/face", { faceId });
    if (lastFaceId !== faceId) return;
    picked = info;
    const flatAxis = Math.max(...info.normal.map(Math.abs)) > 0.9999;
    const thk = flatAxis && info.approxThicknessMm ? ` · ${info.approxThicknessMm} mm thick` : "";
    faceStatus("ok", `<strong>✓ ${escapeHtml(info.partName)}</strong><br>Top face picked${thk}`);
    $("step-face").classList.add("done");
  } catch (err) {
    if (lastFaceId === faceId) faceStatus("bad", escapeHtml(err.message));
    $("step-face").classList.remove("done");
  }
  updateSend();
}

function faceStatus(kind, html) {
  const el = $("face-status");
  el.className = `status ${kind || "muted"}`;
  el.innerHTML = html;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

// ------------------------------------------------------------ send

function qty() { return Math.max(1, Math.min(50, Math.round(Number($("qty").value) || 1))); }

function updateSend() {
  $("send").disabled = !(picked && $("team").value.trim());
}

async function send() {
  const team = $("team").value.trim();
  store.set("ls_team", team);
  const res = $("result");
  $("send").disabled = true;
  res.className = "result busy";
  res.textContent = "Exporting from Onshape…";
  try {
    const r = await api("/api/send", {
      team, qty: qty(), partId: picked.partId, partName: picked.partName,
      top: { normal: picked.normal, origin: picked.origin },
    });
    res.className = "result ok";
    res.innerHTML = `<strong>Sent ${qty()} × ${escapeHtml(picked.partName)}.</strong><br>` +
      `${r.waiting} job${r.waiting === 1 ? "" : "s"} waiting at the laser. Open Laser Station there and load it.`;
    post("showMessageBubble", { message: `Sent ${picked.partName} to the laser` });
  } catch (err) {
    res.className = "result bad";
    res.textContent = err.message;
  }
  updateSend();
}

// ------------------------------------------------------------ start

async function start() {
  takeSessionFromHash();
  $("team").value = store.get("ls_team") || "";
  $("signin-btn").onclick = startSignIn;
  $("team").oninput = updateSend;
  $("minus").onclick = () => { $("qty").value = qty() - 1 || 1; };
  $("plus").onclick = () => { $("qty").value = Math.min(50, qty() + 1); };
  $("qty").onchange = () => { $("qty").value = qty(); };
  $("send").onclick = send;
  $("signout").onclick = async () => { try { await api("/api/signout", {}); } catch { /* already gone */ } forgetSession(); showSignIn(); };

  if (!doc.documentId || !doc.wvid || !doc.elementId) {
    $("foot-msg").textContent = "Open this from a Part Studio's right-side panel.";
  }
  const cfg = await fetch("/api/config").then((r) => r.json()).catch(() => ({}));
  const okHost = new RegExp(cfg.apiHostPattern || "^https://([a-z0-9-]+\\.)?onshape\\.com$");
  const candidates = [...(location.ancestorOrigins || [])];
  try { if (document.referrer) candidates.push(new URL(document.referrer).origin); } catch { /* no referrer */ }
  parentOrigin = candidates.find((o) => okHost.test(o)) || null;
  if (!parentOrigin) $("foot-msg").textContent = "Open this inside Onshape.";
  window.addEventListener("message", onMessage);
  post("applicationInit");

  if (!sid()) { showSignIn(); return; }
  try {
    await api("/api/me");
  } catch {
    if (!sid()) return; // sign-in screen already shown
  }
  $("signin").hidden = true;
  $("main").hidden = false;
  $("signout").hidden = false;
  post("requestSelection", { messageId: "laser-top-face", entityTypeSpecifier: ["FACE"] });
  updateSend();
}

start();
