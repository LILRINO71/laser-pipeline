# Laser Station: Onshape → VLS 4.60, no Illustrator

Any team exports their plates from Onshape, opens the file in **Laser Station** on the laser PC, checks
where the parts land on the plywood that's already in the laser, answers one question, and it cuts.

```
Onshape: right-click Part Studio tab > Export > STEP      (or a face / drawing exported as DXF)
   ──▶ Laser Station reads every part, keeps the 6 mm ones, measures thickness, flags pockets
   ──▶ kerf compensation ──▶ nests the parts into the wood that's still free on the shared sheet
   ──▶ scores each part's name ──▶ safety checks ──▶ "Ready to fire?" ──▶ ULS driver ──▶ UCP Start
   ──▶ the cut parts are marked on the sheet map for the next team
```

Two ways in:

- **Onshape add-on (newest):** in the Part Studio, open the **Laser Station** panel, click the plate's **top face**, press
  **Send to laser**. At the laser PC, click **Jobs sent from Onshape**. The face you clicked is the side facing up, so a part
  never comes out flipped or mirrored. Setup: [onshape-addon/SETUP.md](onshape-addon/SETUP.md).
- **Export a file:** no add-on, no internet. Export STEP or DXF and open it in Laser Station. The biggest flat face is the top.

## Installing it

**[One-click install](https://github.com/LILRINO71/laser-pipeline/releases/latest/download/Install-Laser-Station.bat):** on the laser PC, click that
link and open the file. It downloads everything else. The same link updates it later and keeps your sheet map and settings.

Then follow the **super simple steps in [SCHOOL_SETUP.md](SCHOOL_SETUP.md)**.

To rebuild the installer: `python tools/build_usb.py` (makes `dist/usb/`).

## Using it

1. In Onshape, right-click the Part Studio tab that has your plates, then **Export…** → Format **STEP** → OK.
   It downloads a `.step` with every part and its name. (A single plate also works as a DXF: right-click
   its big flat face → **Export as DXF/DWG**.)
2. On the laser PC, double-click **Laser Station.bat**, type your team name, then click **Open STEP / DXF…**
3. Check the layout. **Grey** = wood other teams already cut. **Red** = your cuts. **Blue** = part names.
   Double-click a part to change how many you need.
4. Pick **Cut through** or **Engrave only**. Power and speed come from the settings saved once with
   **Save Laser Settings**, so nobody picks them per job. Drag a part on the map to choose where it cuts, right-click to turn it.
5. Click **FIRE** once. The job goes to the laser and UCP's Start is pressed for you. The only question left is when a
   job needs fresh wood. If Start can't be pressed, **Teach START** shows the program where the button is.
6. When someone puts a fresh sheet in, click **New sheet loaded**. If a cut never happened (cancelled in
   UCP, power cut), click **Undo last cut** so that wood isn't counted as used.

If a job doesn't fit in the free wood, the extra parts go on "Sheet 2 · NEEDS A NEW SHEET". After sheet 1
finishes, swap the wood and press FIRE again.

## What stops mistakes

| Check | What happens |
|---|---|
| Part runs off the sheet | **blocked**, won't send |
| Part would land on wood that's already cut, or on another part | **blocked** |
| Same files + quantities sent in the last 30 min | noted on the status line |
| Part isn't 6 mm (motor, bracket, spacer…) | skipped, listed in the notes |
| Plate has pockets / steps / chamfers (STEP only) | warning: they'd be cut straight through |
| Edges that don't join into a closed outline | warning, and those edges are left out |
| Part bigger than the bed | left out, listed in red |
| DXF with no units | warning, assumes mm |
| Job needs fresh wood | asks once that a new sheet is loaded before firing |
| Laser settings never saved, or the driver changed | **blocked**, won't send |
| Add-on: side face, curved face or whole part clicked | refused in the panel, with what to click instead |
| Add-on: picked face not found in the file | note, and the biggest flat face is the top |
| First job after saving settings | not started until someone confirms UCP shows the saved numbers |
| Engrave only | every line is sent blue, so the job contains no cut-power line |

## Command line (same engine)

```
python laser.py plates.step --team 7831 --qty "Frame Plate +Y=2"
python laser.py plate.dxf --dxf-units in --no-send
python laser.py --new-sheet
python laser.py plate.dxf --engrave
python laser.py --setup            (open the ULS driver's own settings and lock them in)
```

## Settings: `config.json` (put per-PC changes in `config.local.json`)

| Key | Default | Meaning |
|---|---|---|
| `sheet_mm` | 609.6 × 457.2 | plywood size (VLS 4.60 full bed = 24 × 18 in) |
| `margin_mm` / `gap_mm` | 5 / 4 | edge margin, space between parts |
| `thickness_mm` / `thickness_tol_mm` | 6 / 0.8 | which parts count as plates |
| `kerf_mm` | 0 | beam width; outlines grow and holes shrink by half of it |
| `cut_rgb` / `engrave_rgb` | red / blue | must match UCP's colour → power/speed rows |
| `printer` | auto | finds the printer with VLS / ULS / Universal in its name |
| `auto_start` | true | press UCP's Start after sending |
| `ucp_start_button` | auto | exact button name if auto-find misses it (see `ucp_controls.txt`) |
| `test_pdf_dir` | null | set a folder to "print" to PDF instead of the laser (testing) |
| `cloud_url` | null | the Onshape add-on's server; the station key goes in `config.local.json` as `station_key` |

## Files

- `station.pyw`: the Laser Station window
- `laser.py`: command line
- `laserpipe/importers.py`: STEP (part names, thickness, pocket check, picked top face) and DXF readers
- `laserpipe/geometry.py`: edges → outlines with holes, kerf, orientation
- `laserpipe/nest.py`: packs parts around the used wood
- `laserpipe/bed.py`: the shared sheet map + safety checks
- `laserpipe/output.py`: labels, DXF, SVG, preview page
- `laserpipe/vls_print.py`: hairline vector printing to the ULS driver
- `laserpipe/ucp.py`: presses Start in UCP
- `laserpipe/cloud.py`: jobs from the Onshape add-on
- `onshape-addon/`: the Onshape panel + its small server (Cloudflare Worker), with a fake Onshape for tests
- `SCHOOL_SETUP.md`: install + first-test steps for the laser PC
