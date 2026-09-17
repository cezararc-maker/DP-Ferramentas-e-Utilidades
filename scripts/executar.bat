@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\pythonw.exe" (
  echo Ambiente nao encontrado. Execute scripts\instalar.ps1 primeiro.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m dp_ferramentas
endlocal
exit /b 0
