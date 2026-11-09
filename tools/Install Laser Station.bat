@echo off
rem One-click install of Laser Station. Safe to run again: the sheet map and settings are kept.
rem Named Install-Laser-Station.bat it always downloads the newest version from GitHub.
rem Next to LaserStation.zip (the USB stick) it uses that zip.
rem A folder argument installs there with no admin and no shortcut (used for testing).
setlocal
set "SRC=%~dp0"
set "TARGET=%~1"
set "TESTMODE=1"
if "%TARGET%"=="" set "TESTMODE="
if "%TARGET%"=="" set "TARGET=C:\LaserStation"

if not defined TESTMODE (
  net session >nul 2>&1
  if errorlevel 1 (
    echo Windows will now ask for the admin password...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
  )
)

title Installing Laser Station
set "ZIP=%SRC%LaserStation.zip"
set "DOWNLOADED="
if /i "%~n0"=="Install-Laser-Station" goto :download
if exist "%ZIP%" goto :have_zip

:download
set "ZIP=%TEMP%\LaserStation-download.zip"
set "DOWNLOADED=1"
echo Downloading Laser Station (about 250 MB). This can take a few minutes...
"%SystemRoot%\System32\curl.exe" -L --fail --retry 3 -o "%ZIP%" "https://github.com/LILRINO71/laser-pipeline/releases/latest/download/LaserStation.zip"
if errorlevel 1 (
  echo Could not download it. Check the internet connection, or install from the USB stick.
  goto :failed
)

:have_zip
echo Installing to %TARGET% ...
if not exist "%TARGET%" mkdir "%TARGET%"
"%SystemRoot%\System32\tar.exe" -xf "%ZIP%" -C "%TARGET%"
if errorlevel 1 (
  echo Could not unpack the files.
  goto :failed
)
if defined DOWNLOADED del "%ZIP%"

if not defined TESTMODE (
  rem Every Windows login on this PC shares the same sheet map, so all users need write access.
  icacls "%TARGET%" /grant *S-1-5-32-545:^(OI^)^(CI^)M /T /C /Q >nul
)

echo.
echo Self-test: reading the sample file (nothing goes to the laser)...
set "PY=%TARGET%\python\python.exe"
"%PY%" -E -s "%TARGET%\laser.py" "%TARGET%\samples\test-part-studio.step" --team selftest --no-send --no-open
if errorlevel 1 (
  echo Self-test FAILED.
  goto :failed
)

echo.
echo Looking for the laser's printer driver...
"%PY%" -E -s -c "import sys; sys.path.insert(0, r'%TARGET%'); from laserpipe.vls_print import find_laser_printer as f; print('Found:', f())"
if errorlevel 1 echo WARNING: the laser's driver wasn't found. You can pick it in Laser Station's Laser driver list.

set "LINKDIR=%PUBLIC%\Desktop"
if defined TESTMODE set "LINKDIR=%TARGET%"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%LINKDIR%\Laser Station.lnk'); $s.TargetPath='%TARGET%\python\pythonw.exe'; $s.Arguments='-E -s station.pyw'; $s.WorkingDirectory='%TARGET%'; $s.Description='Laser Station'; $s.Save()"
if errorlevel 1 echo WARNING: couldn't make the desktop icon. Use "Laser Station.bat" in %TARGET%.

echo.
echo ============================================================
echo  Done. Use the "Laser Station" icon on the desktop.
echo  Next: do the test cut in SCHOOL_SETUP.md, in %TARGET%
echo ============================================================
if not defined TESTMODE pause
exit /b 0

:failed
echo.
echo Install did not finish. Take a photo of this window and show it to Claude.
if not defined TESTMODE pause
exit /b 1
