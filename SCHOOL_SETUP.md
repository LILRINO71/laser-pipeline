# Laser Station: super simple setup

Stuck? Open Claude on the web, paste this page, and add a photo of the screen.

## 1. Install (one time)

1. Plug the USB stick into the laser PC.
2. Double-click **Install Laser Station.bat**.
3. Type the admin password when Windows asks.
4. Wait for **Done**, then press any key.

You now have a **Laser Station** icon on the desktop.

## 2. Set the colors in UCP (one time)

Open UCP and set:

- **Red** = cut, with your normal 6 mm plywood settings
- **Blue** = light score, low power and fast
- Every other color off

## 3. Test cut (one time, stay at the laser)

1. Put scrap 6 mm plywood in the **top-left corner** of the bed and focus.
2. Open **Laser Station**. Type `test` as the team.
3. Click **New sheet loaded**.
4. Click **Open STEP / DXF** and pick `C:\LaserStation\samples\test-part-studio.step`
5. Double-click each **Frame Plate** and set it to **0**. Only "Pocketed plate" stays.
   A warning about pockets is normal for this test part.
6. Click **CUT ▸ FIRE**, then **Yes**.

Now check these:

| Check | If it's wrong |
|---|---|
| UCP shows **lines**, not a filled picture | Tell Claude "UCP shows raster" |
| The part landed **top-left**, not flipped | Tell Claude what you saw |
| **Start** got pressed by itself | Press it yourself. Paste `C:\LaserStation\ucp_controls.txt` into Claude |
| The name is **scored**, not cut through | Lower the blue power in UCP |
| No settings popup appears | Tell Claude "settings popup every job" |
| The part measures **80 × 50 mm** | Measured 79.8? Type `0.2` in the **Kerf** box. It's remembered |

Then open one of your real Onshape files and check the part names and holes look right.
This is the first real Onshape file it will have read.

## Every day

1. In Onshape, right-click your Part Studio tab, then **Export**, then **STEP**.
2. Open **Laser Station** and type your team.
3. Click **Open STEP / DXF** and pick your file.
4. Look at the parts list. Set anything you don't want to **0**.
5. Click **CUT ▸ FIRE**, then **Yes**. Stay at the laser.

## Rules for the laser room

- New wood in the laser? Click **New sheet loaded**.
- Never move the wood between teams.
- Job didn't cut? Click **Undo last cut**.
- Never walk away while it's cutting.
