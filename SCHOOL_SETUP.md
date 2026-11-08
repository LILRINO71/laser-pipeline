# Setting up Laser Station on the school laser PC

You'll do this yourself, without Claude Code. If anything goes wrong, open Claude on the web, paste this
whole file plus the exact error text, and ask what to do.

## 1. Get the files onto the laser PC (pick one)

- **GitHub:** sign in at github.com/LILRINO71/laser-pipeline → green **Code** button → **Download ZIP**.
  (The repo is private, so you have to be signed in as LILRINO71.)
- **USB stick:** copy the `laser-pipeline` folder from your home PC (`C:\Users\hiheo\Claude\laser-pipeline`).

Unzip or copy it somewhere permanent, for example `Documents\laser-pipeline`. Not the Downloads folder,
which can get cleaned out.

## 2. Install Python (once, about 3 minutes, no admin needed)

1. Go to https://www.python.org/downloads/windows/ and download the latest **Python 3.14** "Windows installer (64-bit)".
2. On the first screen, **tick "Add python.exe to PATH"**, then click **Install Now**.
   If it asks for admin, cancel, run it again, choose **Customize installation**, and untick "for all users".

## 3. Run setup

Double-click **setup.bat** in the folder. It:
- installs the libraries (exact tested versions, a few minutes the first time)
- runs a self-test on `samples\test-part-studio.step` (it should say "Sheet 1: 3 parts", plus one skip and one warning; those are expected)
- prints the laser printer it found, which should contain "VLS" or "Universal"

If it says it **couldn't find the laser's printer driver**, it lists the printers it sees. Open
`config.json`, set `"printer": "<the laser's exact name>"`, and run setup again.

## 4. Match UCP's colours (once)

Open UCP → Settings (or the materials/manual tab):
- **Red (255, 0, 0)** = vector **cut** with your 6 mm plywood power/speed (what you already use).
- **Blue (0, 0, 255)** = light vector **score** for the part names (low power, fast).
- Every other colour off.

If your shop already uses different colours, change `cut_rgb` / `engrave_rgb` in `config.json` instead.

## 5. First test cut (do this before you trust it). Stay at the laser.

1. Put a scrap of 6 mm plywood in the **top-left corner** of the bed and focus.
2. Double-click **Laser Station.bat** → team "test" → **New sheet loaded** → open `samples\test-part-studio.step`.
3. In the parts list, set Frame Plate +Y and -Y to **0** (double-click) so only the small "Pocketed plate" is left.
4. **CUT ▸ FIRE** → Yes.
5. Check each of these:

| Check | If it's wrong |
|---|---|
| In UCP's preview the part shows as **lines (vector)**, not a filled image | tell Claude: "UCP shows raster"; it's a driver line-width setting |
| It landed near the **top-left** of the bed, not mirrored or flipped | tell Claude what you saw: "mirrored", "bottom-left", etc. |
| UCP's **Start was pressed** by itself | press it yourself this time. Open `ucp_controls.txt` in the folder and paste it into Claude to get the right `ucp_start_button` value |
| A popup asked for settings every job | run `python laser.py --setup` once and pick your settings there |
| Outside size is **80 × 50 mm** (measure it) | set `kerf_mm` to (80 − measured width), e.g. 79.8 → `0.2` |
| Part name is scored lightly in blue, not cut through | lower the blue power in UCP |

Once all six pass, it's ready for real plates.

## Everyday rules for the laser room (print this)

1. Fresh sheet in? Click **New sheet loaded** first.
2. Don't move or flip the wood between teams. The map assumes it's still in the top-left corner.
3. Job cancelled or didn't cut? Click **Undo last cut**.
4. Never walk away while it's cutting.
