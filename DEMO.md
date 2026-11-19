# Showing Laser Station without a laser

About 5 minutes. Nothing goes to a laser, nothing is sent to anyone, and the real sheet map is never touched.

**You need:** any browser for part 1, and a Windows PC for part 2.

## Before you start (once)

1. On the Windows PC, run the one-click install:
   **https://github.com/LILRINO71/laser-pipeline/releases/latest/download/Install-Laser-Station.bat**
   It makes two desktop icons: **Laser Station** and **Laser Station DEMO**.
2. Open **Laser Station DEMO** and click **Reset demo** (top right), so the wood is fresh and the 3 jobs are waiting.
3. Open **https://laser-station.hiheollo43.workers.dev/demo.html** in a browser tab.

## Part 1: the student, in Onshape (browser)

What to say: *"Students design the plate in Onshape. The add-on lives in the Part Studio's right-side panel."*

1. On the demo page, drag the plate to turn it. It's the real **Side Plate -Y** from our Robot V2 Onshape document.
2. Click an **edge** or a **hole**. The panel refuses it: *"That's a side face."*
   *"It only takes the big flat face, so a part can't end up standing on its side."*
3. Click the **top face**. It turns blue, and the panel says **✓ Side Plate -Y, 6.35 mm thick**.
   *"The face you click is the face that ends up facing up on the laser. So engravings are never mirrored."*
4. Type a team (like `7831`), then click **Send to laser**.
   *"In the real add-on, this exports the part from Onshape and puts it in the laser's queue."*

## Part 2: at the laser PC (Laser Station DEMO)

What to say: *"At the laser, nobody needs to export files, use Illustrator, or set power and speed."*

1. Point at the blue button: **Jobs sent from Onshape: 3 waiting**. Click it.
   Three real plates from our Robot V2 doc: two side plates and the Hub Deck.
2. Click **Load selected** (it takes the whole team's jobs).
   - Both side plates land on the map of the wood in the laser.
   - **Hub Deck** is **skipped: 3.2 mm thick, not 6 mm**. *"It catches parts that aren't for this wood."*
3. **Drag** a plate to move it, and **right-click** it to turn it. Drag one onto the other: the outline goes red and FIRE is blocked.
   *"It won't let two parts overlap, or cut off the sheet, or cut where another team already cut."*
4. Click **CUT ▸ FIRE**. The laser head traces the real paths on screen: the engraved names first (blue), then the holes, then the outlines.
   *"This is the exact path the laser would take. On the real laser, FIRE sends it to the laser's driver and presses Start."*
5. When it finishes, the cut plates turn **grey**: that wood is used. Click **Jobs sent from Onshape** again.
   The two cut plates are gone from the list. Hub Deck is still waiting, because it wasn't cut.
6. The file that would go to the laser is saved as a PDF in `C:\LaserStation\jobs\demo\laser files`.
   Red lines = cut, blue = engrave, at real size.

## Other things worth showing

- **Open STEP / DXF…**, then `C:\LaserStation\samples\demo\robot-v2-frame-plates.step`: the whole Robot V2 frame-plates Part Studio. It keeps the 2 plates that are 6 mm wood and lists the 3 that aren't.
- **Engrave only**: every line goes out blue, so there's no cutting power in the job at all.
- **Undo last cut** and **New sheet loaded**: how the shared sheet is kept honest between teams.

## What's real and what's pretend

| Real | Pretend in the demo |
|---|---|
| The parts, from our Robot V2 Onshape document | The 3D Part Studio page stands in for Onshape |
| The add-on panel and its checks | Nothing is sent from the demo panel |
| Reading the parts, the layout, the safety checks, the laser file | The laser: FIRE saves a PDF and shows the cut on screen |
| The live server: https://laser-station.hiheollo43.workers.dev | The 3 demo jobs come from files, not the internet |

**Not tested yet on the real laser:** the first real cut, the UCP Start press, and the real kerf. SCHOOL_SETUP.md has the one-time test cut.
