@echo off
rem Baixa a versao mais nova do GitHub e atualiza as dependencias.
cd /d "%~dp0.."
where git >nul 2>nul
if errorlevel 1 (
  echo Git nao encontrado: baixe o ZIP novo do repositorio e rode o Instalar.bat.
  pause
  exit /b 1
)
git pull --ff-only
if errorlevel 1 (
  echo Nao consegui atualizar: ha alteracoes locais? Veja a mensagem acima.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1" -NoShortcut
echo.
pause
