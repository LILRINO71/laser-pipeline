// Demo stand-in for a Part Studio: the real Robot V2 side plate in 3D. Clicking a face sends the panel the same
// SELECTION message Onshape sends, so the panel on the right behaves exactly as it does inside Onshape.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const view = document.getElementById("view");
const panel = document.getElementById("panel");
const hint = document.getElementById("hint");
const bubble = document.getElementById("bubble");
const KINDS = ["top", "bottom", "side", "curved"];
const IDS = { top: "DEMO_TOP", bottom: "DEMO_BOTTOM", side: "DEMO_SIDE", curved: "DEMO_CURVED" };
const COLORS = {
  top: new THREE.Color("#e7cfa1"),
  bottom: new THREE.Color("#e7cfa1"),
  side: new THREE.Color("#8a6a3c"),
  curved: new THREE.Color("#8a6a3c"),
  picked: new THREE.Color("#4c94ef"),
  bad: new THREE.Color("#e0574a"),
};

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, 1, 1, 5000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
view.appendChild(renderer.domElement);
scene.add(new THREE.HemisphereLight(0xffffff, 0x8a7a66, 2.2));
const sun = new THREE.DirectionalLight(0xffffff, 1.6);
sun.position.set(300, 600, 200);
scene.add(sun);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
camera.position.set(260, 420, 520);
controls.target.set(0, 0, 0);

const group = new THREE.Group();
scene.add(group);
let mesh, kinds, colors, picked = null;

function paint() {
  for (let t = 0; t < kinds.length; t++) {
    const k = KINDS[kinds[t]];
    const c = picked && picked.kind === k ? (picked.ok ? COLORS.picked : COLORS.bad) : COLORS[k];
    for (let v = 0; v < 3; v++) colors.setXYZ(t * 3 + v, c.r, c.g, c.b);
  }
  colors.needsUpdate = true;
}

fetch("demo-plate.json").then((r) => r.json()).then((d) => {
  kinds = d.k;
  const pos = new Float32Array(d.t.length * 3);
  d.t.forEach((vi, i) => pos.set(d.v.slice(vi * 3, vi * 3 + 3), i * 3));
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  colors = new THREE.BufferAttribute(new Float32Array(pos.length), 3);
  geo.setAttribute("color", colors);
  geo.computeVertexNormals();
  mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.85, flatShading: true, side: THREE.DoubleSide }));
  group.add(mesh);
  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geo, 30), new THREE.LineBasicMaterial({ color: 0x5a4122 }));
  group.add(edges);
  paint();
});

const home = camera.position.clone();
function resize() {
  const w = view.clientWidth, h = view.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.position.copy(home).multiplyScalar(Math.max(1, 1.15 / camera.aspect)); // narrow screens: step back so the whole plate shows
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(view);

// flip the plate over (so the other big face is up)
let flipTarget = 0;
document.getElementById("flip").onclick = () => { flipTarget += Math.PI; };

(function loop() {
  group.rotation.x += (flipTarget - group.rotation.x) * 0.12;
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(loop);
})();

// clicking: a click (not a drag) on the plate selects the face under the mouse
const ray = new THREE.Raycaster();
let down = null;
renderer.domElement.addEventListener("pointerdown", (e) => { down = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener("pointerup", (e) => {
  if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5 || !mesh) return;
  const r = renderer.domElement.getBoundingClientRect();
  ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
  const hit = ray.intersectObject(mesh)[0];
  const sel = hit ? [{ selectionType: "ENTITY", selectionId: IDS[KINDS[kinds[hit.faceIndex]]], entityType: "FACE" }] : [];
  if (hit) {
    const kind = KINDS[kinds[hit.faceIndex]];
    picked = { kind, ok: kind === "top" || kind === "bottom" };
    paint();
    hint.innerHTML = picked.ok ? "Face picked. Now type a team in the panel and press <b>Send to laser</b>."
      : "That's an edge or a hole. The panel refuses it. Click a big flat face.";
    if (picked.ok) step(1, 2);
  }
  panel.contentWindow.postMessage({ messageName: "SELECTION", selections: sel }, location.origin);
});

function step(done, on) {
  document.getElementById(`s${done}`).className = "done";
  document.getElementById(`s${on}`).className = "on";
}

// messages from the panel (the same ones it sends to Onshape)
window.addEventListener("message", (e) => {
  if (e.origin !== location.origin || !e.data || e.source !== panel.contentWindow) return;
  if (e.data.messageName === "showMessageBubble") {
    bubble.textContent = e.data.message;
    bubble.hidden = false;
    setTimeout(() => { bubble.hidden = true; }, 4000);
    step(1, 2);
    step(2, 3);
    document.getElementById("next").hidden = false;
    document.getElementById("next").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
});
