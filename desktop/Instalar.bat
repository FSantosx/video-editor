@echo off
rem Instala (ou repara) o Video Editor. Pode rodar de novo quando quiser.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1" %*
echo.
pause
