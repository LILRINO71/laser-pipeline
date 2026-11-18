# AI agent tools: CLI-Anything and REA for Laser Station (laser pipeline)

Research note, 2026-11-17. It covers two agent toolkits:

- **[CLI-Anything](https://github.com/HKUDS/CLI-Anything)** (Apache-2.0) wraps real desktop programs (FreeCAD, Blender, 3MF and others) in CLIs that agents can drive.
- **[REA](https://github.com/morluto/rea)** (MIT) is an MCP server and CLI that gives agents reverse-engineering tools.

This file covers only what matters for **this** repo.

How to read the labels:

- **Confirmed**: checked against the tool's own repo or docs.
- **Recommendation**: a suggestion, not tested.
- Nothing below was run end to end on this project yet.

## What could help here

| Tool | Use in this repo | Value |
|---|---|---|
| CLI-Anything **FreeCAD** harness | A second STEP to DXF route: `import` the STEP, flatten it with TechDraw/Draft, then `export dxf`. **Confirmed**: the harness has DXF import and export. The **recommendation**: use it to cross-check the current pipeline on one plate before trusting it, then confirm the result in VLS 4.60 on the real laser | Medium-High |
| `cli-hub matrix preflight 3d-cad --json` | On the school laser PC, report which CAD tools are present and which are missing | Low |
| REA | **Don't use REA on VLS 4.60 or the Universal Laser drivers.** They're commercial software, so the EULA and DMCA apply. Our own `laser.py` and `laserpipe/` have their source, so REA isn't needed for them | None |

## Proposed changes (not made yet)

1. Add an optional `--engine freecad` path in `laserpipe/` that calls `cli-anything-freecad --json`, with the current path kept as the default.
2. Use one known plate to compare the two DXFs (number of entities, kerf, layers) before switching.

## Status on the dev PC (2026-11-17)

- **Installed:** the agent skills `cli-hub-meta-skill` and `reverse-engineer-anything`, plus `cli-anything-hub` 0.4.1 (pip).
- **Not usable yet:**
  - The REA CLI/MCP needs Node 24.22.1 or newer, and the PC has 24.15.0.
  - The FreeCAD/Blender harnesses need those programs installed. Neither is.

## Rules for REA

Use REA only on code and builds we made, or on devices we own. Reverse engineering commercial software can break its EULA or DMCA §1201, and §1201(f) covers only narrow interoperability work. REA's tool results are sent to the AI model provider, so never point it at keys, `.env` files or credentials.
