// Sends the add-on's secrets to Cloudflare without ever printing them.
//   node scripts/upload-secrets.mjs
// - Makes station-key.txt (the laser PC's password for the job queue) the first time.
// - Reads .secrets (ONSHAPE_CLIENT_ID=..., ONSHAPE_CLIENT_SECRET=...) if it exists.
// Both files are in .gitignore. Never paste them into chat.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";

const here = new URL("..", import.meta.url);
const keyFile = new URL("station-key.txt", here);
if (!existsSync(keyFile)) {
  writeFileSync(keyFile, randomBytes(24).toString("base64url") + "\n");
  console.log("Made a new station key in onshape-addon/station-key.txt");
}
const values = { STATION_KEY: readFileSync(keyFile, "utf8").trim() };
const secretsFile = new URL(".secrets", here);
if (existsSync(secretsFile)) {
  for (const line of readFileSync(secretsFile, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*(ONSHAPE_CLIENT_ID|ONSHAPE_CLIENT_SECRET)\s*=\s*(.+?)\s*$/);
    if (m && !m[2].includes("paste")) values[m[1]] = m[2];
  }
}
for (const [name, value] of Object.entries(values)) {
  const r = spawnSync(process.execPath, ["node_modules/wrangler/bin/wrangler.js", "secret", "put", name], {
    cwd: here, input: value + "\n", encoding: "utf8",
  });
  console.log(r.status === 0 ? `uploaded ${name}` : `FAILED ${name}: ${(r.stderr || "").split("\n").filter(Boolean).slice(-2).join(" ")}`);
}
const missing = ["ONSHAPE_CLIENT_ID", "ONSHAPE_CLIENT_SECRET"].filter((k) => !values[k]);
if (missing.length) console.log(`Not uploaded yet (put them in onshape-addon/.secrets): ${missing.join(", ")}`);
