@echo off
rem Inicia o Video Editor e abre a interface no navegador.
title Video Editor
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
if errorlevel 1 pause
