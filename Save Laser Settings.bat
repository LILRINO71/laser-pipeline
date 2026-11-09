@echo off
rem Opens the laser's own settings window. Whatever is chosen there is locked in for every job.
cd /d "%~dp0"
echo In the window that opens: Manual Control tab, Red = cut through, Blue = engrave. Press SET after each, then OK.
if exist python\python.exe (
  python\python.exe -E -s laser.py --setup
) else (
  python laser.py --setup
)
pause
