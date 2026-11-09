"""Build the one-click USB installer in dist/usb/ (run on a PC with Python 3.14 installed).

Makes a private copy of Python with the exact tested libraries, adds the app, and zips it.
The result is three files to drag onto any USB stick:
    START HERE.txt
    Install Laser Station.bat
    LaserStation.zip
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
APP = DIST / "LaserStation"
USB = DIST / "usb"
SKIP_PY = {"Doc", "include", "libs", "Scripts", "__pycache__", "site-packages", "test", "idlelib"}
APP_FILES = ["laser.py", "station.pyw", "config.json", "README.md", "SCHOOL_SETUP.md", "requirements.txt", "Laser Station.bat", "Save Laser Settings.bat"]


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    APP.mkdir(parents=True)
    USB.mkdir()
    py = APP / "python"
    print("Copying Python...")
    shutil.copytree(sys.base_prefix, py, ignore=lambda d, names: [n for n in names if n in SKIP_PY])
    (py / "Lib" / "site-packages").mkdir(exist_ok=True)
    exe = py / "python.exe"
    env = {"PATH": r"C:\Windows\System32", "SYSTEMROOT": r"C:\Windows", "PYTHONNOUSERSITE": "1", "TEMP": str(DIST), "TMP": str(DIST)}
    print("Installing the tested libraries...")
    subprocess.run([exe, "-m", "ensurepip"], check=True, env=env)
    subprocess.run([exe, "-m", "pip", "install", "-q", "--no-warn-script-location", "--disable-pip-version-check",
                    "-r", ROOT / "requirements.txt"], check=True, env=env)
    print("Adding the app...")
    for f in APP_FILES:
        shutil.copy2(ROOT / f, APP / f)
    for d in ("laserpipe", "samples"):
        shutil.copytree(ROOT / d, APP / d, ignore=shutil.ignore_patterns("__pycache__"))
    for junk in list(APP.rglob("__pycache__")):
        shutil.rmtree(junk, ignore_errors=True)
    print("Precompiling so it starts fast...")
    subprocess.run([exe, "-m", "compileall", "-q", "-j", "0", "--invalidation-mode", "unchecked-hash",
                    py / "Lib", APP / "laserpipe"], env=env)  # a few test files in libraries never compile; that's fine
    print("Zipping...")
    z = USB / "LaserStation.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as zf:
        for f in sorted(APP.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(APP))
    shutil.copy2(ROOT / "tools" / "Install Laser Station.bat", USB / "Install Laser Station.bat")
    shutil.copy2(ROOT / "tools" / "START HERE.txt", USB / "START HERE.txt")
    shutil.copy2(ROOT / "tools" / "Install Laser Station.bat", DIST / "Install-Laser-Station.bat")  # the one-click download for GitHub
    print(f"Done: {USB}  ({z.stat().st_size / 1e6:.0f} MB zip, {sum(f.stat().st_size for f in APP.rglob('*') if f.is_file()) / 1e6:.0f} MB installed)")


if __name__ == "__main__":
    main()
