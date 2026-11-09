# Laser Station: super simple setup

Stuck? Open Claude on the web, paste this page, and add a photo of the screen.

## 1. Install (one time)

1. Plug the USB stick into the laser PC.
2. Double-click **Install Laser Station.bat**.
3. Type the admin password when Windows asks.
4. Wait for **Done**, then press any key.

You now have a **Laser Station** icon on the desktop.

## 2. Save the laser settings (one time, only the person in charge)

Use the power and speed that you already know cut your wood cleanly. Laser Station won't fire until this is done.

1. Open **Laser Station**. Next to **Laser driver** it should say **✓ Found**.
   If it says **NOT FOUND**, pick the laser from that list. If the laser isn't in the list, UCP isn't installed yet.
2. Click the green **Save Laser Settings** button at the top right.
3. In the red-and-gray window that opens, go to the **Manual Control** tab.
4. Click **Red** and enter your **cut through** power and speed. Press **Set**.
5. Click **Blue** and enter your **engrave** power and speed. Press **Set**.
6. Press the red **OK**. That's what saves them. It should now say **Laser settings: saved**.

Don't use the red **Save** in that window. It only makes a backup file.

Every job now uses these numbers. Nobody picks power or speed in Laser Station.
If your wood or laser changes, do this again.

## 3. Test cut (one time, stay at the laser)

1. Put scrap wood in the **top-left corner** of the bed and focus.
2. Open **Laser Station**. Type `test` as the team.
3. Click **New sheet loaded**.
4. Click **Open STEP / DXF** and pick `C:\LaserStation\samples\test-part-studio.step`
5. Double-click each **Frame Plate** and set it to **0**. Only "Pocketed plate" stays.
   A warning about pockets is normal for this test part.
6. Leave it on **Cut through**. Click **CUT ▸ FIRE**, then **Yes, FIRE**.
7. **The laser won't start yet.** In UCP, select the job and click **Settings**.
   Do Red and Blue show your numbers?
   - **Yes:** answer Yes in Laser Station, then press the green **START** in UCP.
   - **No:** answer No and **don't press START**. Tell Claude "presets don't stick".

Now check these:

| Check | If it's wrong |
|---|---|
| UCP shows **lines**, not a filled picture | Tell Claude "UCP shows raster" |
| The part landed **top-left**, not flipped | Tell Claude what you saw |
| The name is **scored**, not cut through | Run step 2 again with less Blue power |
| The part measures **80 × 50 mm** | Measured 79.8? Type `0.2` in the **Kerf** box. It's remembered |
| Your sheets are **24 × 18 in** | Tell Claude the real size |

Then do the same test with **Engrave only** selected. It should mark the surface and not cut through.

Finally, open one of your real Onshape files and check the part names and holes look right.
This is the first real Onshape file it will have read.

The next job will press **START** by itself. Check that it does. If it doesn't, press it yourself and paste
`C:\LaserStation\ucp_controls.txt` into Claude.

## Every day

1. In Onshape, right-click your Part Studio tab, then **Export**, then **STEP**.
2. Open **Laser Station** and type your team.
3. Click **Open STEP / DXF** and pick your file.
4. Pick **Cut through** or **Engrave only**.
5. Look at the parts list. Set anything you don't want to **0**.
6. Want it somewhere else? **Drag the part** on the map. **Right-click** it to turn it. A red outline means that spot is taken.
7. Click **FIRE**, then **Yes, FIRE**. Stay at the laser.

## Rules for the laser room

- **Never walk away while it's running.**
- **Keep a fire extinguisher right there.**
- If it flames up, press **PAUSE** and get the teacher. Use the extinguisher if it keeps burning.
- Clear old scrap out of the cutting table before you start.
- **At the end of the day, take all wood and scrap out of the laser.** Next time, put a partly used sheet back in the same corner, or click **New sheet loaded** for fresh wood.
- New wood in the laser? Click **New sheet loaded**.
- Never move the wood between teams.
- Job didn't cut? Click **Undo last cut**.
