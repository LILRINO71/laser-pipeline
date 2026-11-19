@echo off
rem Laser Station in DEMO mode: no laser needed. FIRE saves the laser file as a PDF and shows the cut on screen.
rem Uses its own sheet map, so the real one is never touched.
cd /d "%~dp0"
if exist "python\pythonw.exe" (
  start "" "python\pythonw.exe" -E -s station.pyw --demo
) else (
  start "" pythonw station.pyw --demo
)
