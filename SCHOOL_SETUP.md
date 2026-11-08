# Setting up Laser Station on the school laser PC

You'll do this yourself, without Claude Code. If anything goes wrong, open Claude on the web, paste this
whole file plus the exact error text (or a photo), and ask what to do.

## 1. Install (one click)

1. On your home PC, drag the two files in `laser-pipeline\dist\usb` onto any USB stick:
   `Install Laser Station.bat` and `LaserStation.zip`. Keep them together.
2. On the laser PC, double-click **Install Laser Station.bat** and enter the admin password when Windows asks.

It takes about a minute. You don't need to install Python and it doesn't need the internet: the stick carries its
own copy of Python with the exact libraries that were tested. It installs to `C:\LaserStation`, puts a
**Laser Station** icon on the desktop for every Windows login, and lets every login share the same sheet map.

The window should end with "Found: <laser printer>" and "Done". If it says the laser's driver wasn't found,
it lists the printers it can see. Create `C:\LaserStation\config.local.json` containing
`{"printer": "the laser's exact name"}`.

Running the installer again later is safe. It updates the program and keeps the sheet map and settings.

## 2. Match UCP's colours (once)

Open UCP → Settings (or the materials/manual tab):
- **Red (255, 0, 0)** = vector **cut** with your 6 mm plywood power/speed (what you already use).
- **Blue (0, 0, 255)** = light vector **score** for the part names (low power, fast).
- Every other colour off.

## 3. First test cut (do this before you trust it). Stay at the laser.

1. Put a scrap of 6 mm plywood in the **top-left corner** of the bed and focus.
2. Open **Laser Station** → team "test" → **New sheet loaded** → open `C:\LaserStation\samples\test-part-studio.step`.
3. In the parts list, set Frame Plate +Y and -Y to **0** (double-click) so only the small "Pocketed plate" is left.
4. **CUT ▸ FIRE** → Yes.
5. Check each of these:

| Check | If it's wrong |
|---|---|
| In UCP's preview the part shows as **lines (vector)**, not a filled image | tell Claude: "UCP shows raster" |
| It landed near the **top-left** of the bed, not mirrored or flipped | tell Claude what you saw: "mirrored", "bottom-left", etc. |
| UCP's **Start was pressed** by itself | press it yourself this time, then paste `C:\LaserStation\ucp_controls.txt` into Claude to get the right `ucp_start_button` value |
| No popup asking for settings on every job | run `C:\LaserStation\python\python.exe C:\LaserStation\laser.py --setup` once and pick your settings there |
| Outside size is **80 × 50 mm** (measure with calipers) | type the difference into the **Kerf** box, e.g. measured 79.8 → `0.2`. It's remembered |
| Part name is scored lightly in blue, not cut through | lower the blue power in UCP |

6. **Then test a real export:** in Onshape, right-click your plates' Part Studio tab → Export → STEP, and open that file.
   Check that the part names, thicknesses and hole count look right before you cut. (Everything so far was tested on
   sample files, so this is the first real Onshape export it will read.)

Once these pass, it's ready for real plates.

## Everyday rules for the laser room (print this)

1. Fresh sheet in? Click **New sheet loaded** first.
2. Don't move or flip the wood between teams. The map assumes it's still in the top-left corner.
3. Look at the parts list before firing. Any 6 mm part counts, so set things you don't want to 0.
4. Job cancelled or didn't cut? Click **Undo last cut**.
5. Never walk away while it's cutting.
