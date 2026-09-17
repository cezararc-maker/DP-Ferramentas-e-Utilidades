@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente nao encontrado. Execute scripts\instalar.ps1 primeiro.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m dp_ferramentas
endlocal
