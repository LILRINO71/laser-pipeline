# Onshape add-on: setup

Students click the plate's **top face** in Onshape and press **Send to laser**. The job shows up in
Laser Station on the laser PC with that face up. It never comes out flipped or mirrored.

```
Onshape panel ──(student's own Onshape sign-in)──▶ add-on server ──(station key)──▶ Laser Station
  click top face         exports that one part as STEP         holds the job        "Jobs sent from Onshape"
```

The server is a free Cloudflare Worker. Jobs are deleted when they're cut, or after 2 weeks.
The laser PC never needs an Onshape login or API key.

You do this once. Steps 1 and 2 are on your home PC with Claude. Step 3 needs the school's Onshape admin.

## 1. Server (Cloudflare, free)

1. Make a free account at **https://dash.cloudflare.com/sign-up**.
2. Tell Claude: **"Cloudflare account made"**. Claude runs the setup on your home PC:
   - `npx wrangler login` opens your browser. Click **Allow**.
   - Claude creates the job storage, makes the station key, and puts the server online.
3. You get the server's address, like `https://laser-station.YOURNAME.workers.dev`.
   In the steps below, **ADDRESS** means that address.

## 2. Onshape app (test on your own account first)

1. Go to **https://dev-portal.onshape.com**, then **OAuth applications**, then **Create new OAuth application**.

   | Box | Type this |
   |---|---|
   | Name | `Laser Station` |
   | Primary format | `com.lilrino71.laserstation` |
   | Summary | `Send a plate to the school laser` |
   | Redirect URLs | `ADDRESS/oauth/callback` |
   | OAuth URL | `ADDRESS/panel.html` |
   | Permissions | only **Application can read your documents** |

2. Onshape shows the **OAuth secret only once**. Copy the **client identifier** and the **secret** into the file
   `onshape-addon/.secrets` (copy `.secrets.example` and fill it in). **Don't paste them into chat.**
   Then tell Claude: **"secrets saved"**. Claude uploads them with `node scripts/upload-secrets.mjs`, which never prints them.
3. In the same app, open **Extensions**, then **Add extension**:

   | Box | Type this |
   |---|---|
   | Name | `Laser Station` |
   | Location | **Element right panel** |
   | Context | **Inside part studio** |
   | Action URL | `ADDRESS/panel.html?documentId={$documentId}&wv={$workspaceOrVersion}&wvid={$workspaceOrVersionId}&elementId={$elementId}&configuration={$configuration}` |
   | Icon | optional |

4. Open **Store entries**, create an entry for the app and keep it private. Then **Subscribe** to it yourself.
   (Onshape's own steps are: register the app, add the extension, make a store entry, subscribe.)
5. Open any Part Studio. On the right edge there's a new **Laser Station** button. Click it,
   then **Sign in with Onshape**, then **Grant**. Click the plate's top face. Type a team. **Send to laser**.

If any screen looks different from this, take a photo and show Claude.

## 3. School (puhsd Onshape)

Students' Onshape accounts are the district's, so the district has to allow the app:

- Ask the district Onshape admin to open **Enterprise settings, then Developer**, and either register this app
  there with the same boxes as step 2 or let you register it. Then they **assign it to your team's users or teams**.
  Onshape lets admins do this without an App Store listing.
- Each student signs in once with their school Onshape login and clicks **Grant**.
- Each part sent uses about 5 Onshape API calls from the district's allowance (more if Onshape is slow to export).
  The jobs list on the laser PC shows this month's total.

## 4. Laser PC

1. Update Laser Station with the same install link as always.
2. Click **Jobs sent from Onshape**. The first time, it asks for the **station key**. It's in
   `onshape-addon/station-key.txt` on the home PC. Type it in once. It stays only on that PC.
3. The button turns **blue** when jobs are waiting. Click it, pick one team's parts, then **Load selected**.
   Check the map, then **FIRE**. Once the last sheet is sent, those jobs leave the list.

## Testing without Onshape (for Claude)

```
cd onshape-addon
npm install
cp test/dev.vars.example .dev.vars
node test/mock-onshape.mjs          # fake Onshape on :8788, fake Part Studio at /frame.html
npx wrangler dev --port 8787        # the server, pointed at the fake Onshape
node test/api-test.mjs              # 23 server checks
```
