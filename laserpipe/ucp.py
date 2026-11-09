"""Press Start in Universal Control Panel after a job has been printed to it.

UCP is skinned, so its buttons may have no readable name. The reliable route is a taught point:
someone holds the mouse over the green START once and we remember where it sits in the window.
Without one, this looks for a button named Start / Run / Play. If that fails it writes what it
could see to ucp_controls.txt and the operator presses Start by hand.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import win32api
import win32con
import win32gui

DUMP = Path(__file__).resolve().parents[1] / "ucp_controls.txt"
TITLE_RE = r".*(Universal Control Panel|UCP|Universal Laser|ULS Engraver).*"
START_RE = re.compile(r"^(start|run|play|go|start job|run job)$", re.I)
GA_ROOT = 2


def _top_windows() -> list[tuple[int, str]]:
    found = []

    def add(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            found.append((hwnd, win32gui.GetWindowText(hwnd)))

    win32gui.EnumWindows(add, None)
    return found


def read_point() -> dict:
    """Where the mouse is now, as a spot inside the window under it."""
    x, y = win32api.GetCursorPos()
    hwnd = win32gui.GetAncestor(win32gui.WindowFromPoint((x, y)), GA_ROOT)
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    return {"ucp_window_title": win32gui.GetWindowText(hwnd),
            "ucp_start_point": [(x - left) / max(1, right - left), (y - top) / max(1, bottom - top)]}


def _find_taught(title: str) -> int | None:
    windows = _top_windows()
    for hwnd, text in windows:
        if text == title:
            return hwnd
    for hwnd, text in windows:  # the title can carry the job name after the program name
        if len(title) >= 8 and text.startswith(title[:8]):
            return hwnd
    return None


def _click_taught(point, title: str, wait_s: float) -> tuple[bool, str]:
    deadline = time.time() + wait_s
    hwnd = _find_taught(title)
    while hwnd is None and time.time() < deadline:
        time.sleep(0.5)
        hwnd = _find_taught(title)
    if hwnd is None:
        return False, "Couldn't find the UCP window. Open UCP and press START there."
    time.sleep(3)  # let the job land in UCP's queue
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.5)
    win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)  # Windows only hands over the foreground after a key event
    win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except win32gui.error:
        pass
    time.sleep(0.4)
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    x, y = int(left + point[0] * (right - left)), int(top + point[1] * (bottom - top))
    if win32gui.GetAncestor(win32gui.WindowFromPoint((x, y)), GA_ROOT) != hwnd:
        return False, "Something is covering UCP's START. Press it yourself."
    back = win32api.GetCursorPos()
    win32api.SetCursorPos((x, y))
    time.sleep(0.15)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
    time.sleep(0.08)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
    time.sleep(0.1)
    win32api.SetCursorPos(back)
    return True, "Pressed START in UCP."


def press_start(button_name: str | None = None, wait_s: float = 20.0, point=None, title: str | None = None) -> tuple[bool, str]:
    if point and title:
        return _click_taught(point, title, wait_s)
    try:
        from pywinauto import Desktop
    except ImportError:
        return False, "pywinauto isn't installed, so press START in UCP yourself."
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
        DUMP.write_text("No UCP window found. Open windows:\n" + "\n".join(t for _, t in _top_windows()), encoding="utf-8")
        return False, "Couldn't find the UCP window."
    time.sleep(3)  # let the job show up in UCP's queue
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
    DUMP.write_text(f"UCP window: {win.window_text()}\nButtons (name | automation id | help text):\n" + "\n".join(seen), encoding="utf-8")
    return False, "Couldn't find UCP's START button."
