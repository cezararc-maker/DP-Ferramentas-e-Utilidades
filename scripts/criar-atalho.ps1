$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonw = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"
if (-not (Test-Path -LiteralPath $pythonw)) {
    throw "Ambiente do programa não encontrado. Execute scripts\instalar.ps1 primeiro."
}

$applicationFolder = Join-Path $env:LOCALAPPDATA "DP Ferramentas e Utilidades"
New-Item -ItemType Directory -Path $applicationFolder -Force | Out-Null
$launcher = Join-Path $applicationFolder "DP_Ferramentas_Utilidades.exe"

$escapedProjectRoot = $projectRoot.Replace("\", "\\").Replace('"', '\"')
$launcherSource = @"
using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows.Forms;

internal static class Program
{
    [DllImport("shell32.dll", SetLastError = true)]
    private static extern void SetCurrentProcessExplicitAppUserModelID(string appID);

    [STAThread]
    private static void Main()
    {
        SetCurrentProcessExplicitAppUserModelID("CONTALEX.DP.FerramentasUtilidades");
        string projectRoot = "$escapedProjectRoot";
        string pythonw = Path.Combine(projectRoot, ".venv", "Scripts", "pythonw.exe");

        if (!File.Exists(pythonw))
        {
            MessageBox.Show(
                "O ambiente do programa não foi encontrado. Execute scripts\\instalar.ps1.",
                "DP - Ferramentas & Utilidades",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning
            );
            return;
        }

        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = pythonw,
                Arguments = "-m dp_ferramentas",
                WorkingDirectory = projectRoot,
                UseShellExecute = false
            });
        }
        catch (Exception error)
        {
            MessageBox.Show(
                "Não foi possível abrir o programa.\n\n" + error.Message,
                "DP - Ferramentas & Utilidades",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error
            );
        }
    }
}
"@

if (Test-Path -LiteralPath $launcher) {
    Remove-Item -LiteralPath $launcher -Force
}
Add-Type -TypeDefinition $launcherSource -Language CSharp -ReferencedAssemblies "System.Windows.Forms" -OutputAssembly $launcher -OutputType WindowsApplication

if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Não foi possível criar o inicializador nativo do programa."
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
    $shortcut.TargetPath = $launcher
    $shortcut.Arguments = ""
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.Description = "DP - Ferramentas & Utilidades"
    $shortcut.IconLocation = "$launcher,0"
    $shortcut.Save()
}

Write-Host "Inicializador nativo criado em: $launcher" -ForegroundColor Green
Write-Host "Atalhos atualizados na Área de Trabalho e no Menu Iniciar." -ForegroundColor Green
Write-Host "Remova o atalho Python antigo da barra de tarefas e fixe o novo atalho." -ForegroundColor Cyan
