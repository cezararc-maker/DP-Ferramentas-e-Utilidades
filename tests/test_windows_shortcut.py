from pathlib import Path


def test_shortcut_targets_native_launcher_instead_of_python():
    script = (
        Path(__file__).parents[1] / "scripts" / "criar-atalho.ps1"
    ).read_text(encoding="utf-8")

    assert 'DP_Ferramentas_Utilidades.exe' in script
    assert '$shortcut.TargetPath = $launcher' in script
    assert '$shortcut.TargetPath = $pythonw' not in script
    assert 'SetCurrentProcessExplicitAppUserModelID' in script
    assert 'UseShellExecute = false' in script
