from __future__ import annotations

import logging
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

from .models import ToolDefinition

LOGGER = logging.getLogger(__name__)
URL_KINDS = {"url", "github"}


def target_exists(tool: ToolDefinition) -> bool:
    return tool.kind in URL_KINDS or tool.expanded_target.exists()


def open_tool(tool: ToolDefinition) -> None:
    target = tool.target if tool.kind in URL_KINDS else str(tool.expanded_target)
    LOGGER.info("Abrindo %s: %s", tool.name, target)
    if tool.kind in URL_KINDS:
        webbrowser.open(target)
    elif tool.kind in {"html", "file", "folder"}:
        os.startfile(target)
    elif tool.kind in {"executable", "batch"}:
        subprocess.Popen([target], cwd=str(Path(target).parent))
    elif tool.kind == "python":
        python = Path(target).parent / ".venv" / "Scripts" / "python.exe"
        executable = str(python) if python.exists() else sys.executable
        subprocess.Popen([executable, target], cwd=str(Path(target).parent))
    else:
        raise ValueError(f"Tipo de ferramenta não suportado: {tool.kind}")


def open_documentation(tool: ToolDefinition) -> None:
    if not tool.documentation:
        raise FileNotFoundError("Esta ferramenta ainda não possui documentação cadastrada.")
    documentation = os.path.expandvars(os.path.expanduser(tool.documentation))
    if documentation.startswith(("http://", "https://")):
        webbrowser.open(documentation)
    else:
        os.startfile(documentation)
