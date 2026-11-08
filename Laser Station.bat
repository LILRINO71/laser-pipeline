@echo off
cd /d "%~dp0"
if exist "python\pythonw.exe" (
  start "" "python\pythonw.exe" -E -s station.pyw
) else (
  start "" pythonw station.pyw
)
