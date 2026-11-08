@echo off
cd /d "%~dp0"
start "" pythonw station.pyw
if errorlevel 1 python station.pyw
