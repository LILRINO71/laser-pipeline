# Laser Pipeline: Onshape → VLS 4.60, no Illustrator

Paste an Onshape Part Studio link. The pipeline pulls every 6 mm plate's flat profile, nests them onto
plywood sheets, scores each part's name, shows a preview, and prints straight to the Universal Laser
(UCP) driver. You load wood, focus and press Start.

```
Onshape Part Studio ──(1 API call, FeatureScript)──▶ flat outlines + holes (mm)
   ──▶ kerf compensation ──▶ nesting (MaxRects, 90° rotation) ──▶ part-name labels
   ──▶ sheetN.dxf / sheetN.svg / preview.html
   ──▶ GDI hairline vectors ──▶ ULS printer driver ──▶ UCP queue ──▶ laser
```

The old route was Onshape → drawing → DXF → Illustrator (hairline + red) → Print → UCP. Illustrator was
only there to set line colours and widths, and then to "print" to the ULS driver. This prints red hairline
vectors to that driver itself.

## Use it

Double-click **`Laser It.bat`**, paste the Part Studio link, check the preview, type `y`.

Or from a terminal:

```
python laser.py "<part studio link>"                      # preview, then asks before sending
python laser.py "<link>" --qty "Frame Plate +Y=2" --qty "Frame Plate -Y=2"
python laser.py "<link>" --qty "*=2" --kerf 0.15 --yes    # 2 of everything, no prompt
python laser.py "<link>" --only "frame plate" --sheet 24x12in
python laser.py "<link>" --cached --yes                   # resend the last job, 0 Onshape calls
python laser.py --setup                                    # save laser material settings once
```

Each job lands in `jobs/<date-time>-<tab>/` with `sheetN.dxf` (layers CUT = red, ENGRAVE = blue),
`sheetN.svg` and `preview.html`. The DXFs still open in Illustrator or Inkscape if you ever want them.

| Flag | What it does |
|---|---|
| `--qty "Name=N"` | how many of a part (repeatable); `"*=N"` sets every part |
| `--only a,b` | only parts whose names contain these words |
| `--sheet 24x18in` | material size (default = full VLS 4.60 bed, 609.6 × 457.2 mm) |
| `--thickness 6` | only parts this thick, ±0.8 mm (`0` = any); skips motors, brackets, etc. |
| `--kerf 0.15` | grows outlines and shrinks holes by half the beam width |
| `--no-labels` | don't score part names |
| `--printer "name"` | printer name, if auto-find (VLS / ULS / Universal) picks the wrong one |
| `--no-send` | files + preview only |
| `--to-pdf DIR` | print through Microsoft Print to PDF instead (testing without the laser) |

Defaults (sheet size, margins, colours, kerf) live in `config.json`.

## Set up the school laser PC (once)

1. Install Python 3.11+ from python.org (tick "Add to PATH").
2. In this folder: `python -m pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and paste the Onshape API keys (Onshape → My account → Developer → API keys).
   The keys must belong to the account that owns the document. The site (cad.onshape.com or a school
   `*.onshape.com`) is read from the link.
4. Match UCP's colour mapping: in UCP, set **red (255, 0, 0)** to your 6 mm plywood **vector cut** and
   **blue (0, 0, 255)** to a light **vector score** for the labels. Or use a UCP material-database entry for
   6 mm plywood. If your shop already uses other colours, change `cut_rgb` / `engrave_rgb` in `config.json`.
5. Optional: `python laser.py --setup` opens the ULS driver's own settings window. Whatever you choose
   there is saved to `printer_settings.json` and reused for every job.

### First test at school (things only the real laser can check)

- [ ] `python laser.py "<link>" --no-send`: preview looks right.
- [ ] Send one small part. In UCP's viewer it should show as **vector** lines, not a raster image.
- [ ] Sheet origin and orientation in UCP match the bed (top-left = laser home). If it's mirrored or
      rotated, note what you see; it's one line to fix.
- [ ] Measure a cut M4 hole and the plate's outside size, then set `kerf_mm` in `config.json`.
- [ ] If UCP ignores `--setup` settings (some versions keep materials only in the UCP app), skip
      `--setup` and use UCP's material database instead.

## How the Onshape part works

`laserpipe/onshape.py` sends one FeatureScript to the Part Studio (`POST .../featurescript`). For each solid it
takes the largest planar face, measures thickness with a tight box in that face's frame, and returns the face's
edges in 2D: lines as end points, circles and arcs as centre + radius + samples, splines as dense samples.
`geometry.py` rebuilds true arcs (0.01 mm chord error), joins edges into loops, sorts outline vs holes, applies
kerf, and turns each part so its smallest bounding rectangle lies flat. That costs one call per Part Studio, logged
to `api_calls.log`, and it refuses to run near `ONSHAPE_CALL_LIMIT` (default 2,500, the free-account yearly cap).
`--cached` re-runs with zero calls.

Limits: blind pockets on the big face would be cut through (laser plates don't normally have any). One link = one
Part Studio; for parts spread over several tabs, run it once per tab.

## Files

- `laser.py`: command line
- `laserpipe/onshape.py`: API call + FeatureScript
- `laserpipe/geometry.py`: edges → polygons, kerf, orientation
- `laserpipe/nest.py`: sheet packing
- `laserpipe/output.py`: labels, DXF, SVG, preview page
- `laserpipe/vls_print.py`: hairline GDI printing to the ULS driver, saved driver settings
