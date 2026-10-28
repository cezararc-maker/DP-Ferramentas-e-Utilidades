$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e .
& (Join-Path $PSScriptRoot "criar-atalho.ps1")
Write-Host "Instalacao concluida. Use o atalho DP - Ferramentas & Utilidades." -ForegroundColor Green
