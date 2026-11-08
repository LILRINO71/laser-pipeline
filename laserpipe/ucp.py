"""Press Start in Universal Control Panel after a job has been printed to it.

UCP's window layout differs between versions, so this looks for a button whose name, tooltip or
automation id says Start / Run / Play. If it can't find one it writes every control it sees to
ucp_controls.txt (paste that file into Claude to get the exact button name for config.json) and
the operator presses Start by hand. Nothing here can fire the laser without the confirm dialog first.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

DUMP = Path(__file__).resolve().parents[1] / "ucp_controls.txt"
TITLE_RE = r".*(Universal Control Panel|UCP|Universal Laser).*"
START_RE = re.compile(r"^(start|run|play|go|start job|run job)$", re.I)


def press_start(button_name: str | None = None, wait_s: float = 20.0) -> tuple[bool, str]:
    try:
        from pywinauto import Desktop
    except ImportError:
        return False, "pywinauto isn't installed (run setup.bat), so press Start in UCP yourself."
    deadline = time.time() + wait_s
    win = None
    while time.time() < deadline and win is None:
        for w in Desktop(backend="uia").windows():
            try:
                if re.match(TITLE_RE, w.window_text() or ""):
                    win = w
                    break
            except Exception:
                continue
        if win is None:
            time.sleep(1)
    if win is None:
        return False, "Couldn't find the UCP window. Open UCP and press Start there."
    time.sleep(2)  # let the job show up in UCP's queue
    want = re.compile(rf"^{re.escape(button_name)}$", re.I) if button_name else START_RE
    seen = []
    for c in win.descendants(control_type="Button"):
        try:
            info = c.element_info
            names = [info.name or "", info.automation_id or "", getattr(info, "help_text", "") or ""]
            seen.append(" | ".join(names))
            if any(want.match(n.strip()) for n in names if n) and c.is_enabled():
                win.set_focus()
                c.click_input()
                return True, f"Pressed '{names[0] or names[1]}' in UCP."
        except Exception:
            continue
    DUMP.write_text("UCP buttons (name | automation id | help text):\n" + "\n".join(seen), encoding="utf-8")
    return False, f"Couldn't find UCP's Start button. Press it by hand. Saved the button list to {DUMP.name}."
