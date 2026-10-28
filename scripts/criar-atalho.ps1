$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonw = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"
if (-not (Test-Path -LiteralPath $pythonw)) {
    throw "Ambiente do programa não encontrado. Execute scripts\instalar.ps1 primeiro."
}

$shortcutName = "DP - Ferramentas & Utilidades.lnk"
$desktop = [Environment]::GetFolderPath("Desktop")
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$destinations = @(
    (Join-Path $desktop $shortcutName),
    (Join-Path $startMenu $shortcutName)
)

$shell = New-Object -ComObject WScript.Shell
foreach ($destination in $destinations) {
    $shortcut = $shell.CreateShortcut($destination)
    $shortcut.TargetPath = $pythonw
    $shortcut.Arguments = "-m dp_ferramentas"
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.Description = "DP - Ferramentas & Utilidades"
    $shortcut.IconLocation = "$pythonw,0"
    $shortcut.Save()
}

Write-Host "Atalhos criados na Área de Trabalho e no Menu Iniciar." -ForegroundColor Green
Write-Host "Para fixar: clique com o botão direito no atalho e escolha 'Fixar na barra de tarefas'." -ForegroundColor Cyan
