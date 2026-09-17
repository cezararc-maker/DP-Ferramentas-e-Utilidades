$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (-not (Test-Path .venv)) { py -3.11 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --name DP_Ferramentas_Utilidades --paths src --add-data "config\tools.example.json;config" src\dp_ferramentas\__main__.py
Write-Host "Executavel criado em dist\DP_Ferramentas_Utilidades." -ForegroundColor Green
