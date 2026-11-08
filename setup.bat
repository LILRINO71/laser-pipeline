@echo off
rem One-time setup for the laser PC. Safe to run again.
cd /d "%~dp0"
title Laser Station setup
where python >nul 2>nul
if errorlevel 1 (
  echo Python isn't installed or isn't on PATH.
  echo Install Python 3.14 from https://www.python.org/downloads/windows/
  echo   - "Install for current user" is fine, no admin needed
  echo   - TICK "Add python.exe to PATH" on the first screen
  echo Then run setup.bat again.
  pause
  exit /b 1
)
python --version
echo.
echo Installing the parts the laser station needs (a few minutes the first time)...
python -m pip install --user --upgrade pip
python -m pip install --user -r requirements.txt
if errorlevel 1 (
  echo.
  echo Install failed. Copy the red text above into Claude and ask what to do.
  pause
  exit /b 1
)
echo.
echo Self-test: reading the sample STEP and laying it out (nothing is sent to the laser)...
python laser.py samples\test-part-studio.step --team selftest --no-send --no-open
if errorlevel 1 (
  echo Self-test FAILED. Copy the text above into Claude.
  pause
  exit /b 1
)
echo.
echo Looking for the laser's printer driver...
python -c "from laserpipe.vls_print import find_laser_printer as f; print('Found laser printer:', f())"
echo.
echo Setup done. Double-click "Laser Station.bat" to use it.
pause
