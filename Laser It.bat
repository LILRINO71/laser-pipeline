@echo off
cd /d "%~dp0"
title Laser It - Onshape to VLS 4.60
python laser.py %*
echo.
pause
