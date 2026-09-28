from __future__ import annotations

import logging
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

from .models import ProjectDefinition, ToolDefinition

LOGGER = logging.getLogger(__name__)
URL_KINDS = {"url", "github"}
INTERNAL_KINDS = {"internal"}


def expanded_path(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value)))


def target_exists_for(kind: str, target: str) -> bool:
    if not target:
        return False
    return kind in URL_KINDS or kind in INTERNAL_KINDS or expanded_path(target).exists()


def open_target(kind: str, target: str) -> None:
    expanded = target if kind in URL_KINDS else str(expanded_path(target))
    LOGGER.info("Abrindo alvo %s: %s", kind, expanded)
    if kind in URL_KINDS:
        webbrowser.open(expanded)
    elif kind in {"html", "file", "folder"}:
        os.startfile(expanded)
    elif kind in {"executable", "batch"}:
        subprocess.Popen([expanded], cwd=str(Path(expanded).parent))
    elif kind == "python":
        python = Path(expanded).parent / ".venv" / "Scripts" / "python.exe"
        executable = str(python) if python.exists() else sys.executable
        subprocess.Popen([executable, expanded], cwd=str(Path(expanded).parent))
    else:
        raise ValueError(f"Tipo de alvo não suportado: {kind}")


def target_exists(tool: ToolDefinition) -> bool:
    return target_exists_for(tool.kind, tool.target)


def open_tool(tool: ToolDefinition) -> None:
    LOGGER.info("Abrindo %s", tool.name)
    open_target(tool.kind, tool.target)


def open_documentation(tool: ToolDefinition) -> None:
    if not tool.documentation:
        raise FileNotFoundError("Esta ferramenta ainda não possui documentação cadastrada.")
    documentation = os.path.expandvars(os.path.expanduser(tool.documentation))
    if documentation.startswith(("http://", "https://")):
        webbrowser.open(documentation)
    else:
        os.startfile(documentation)


def project_folder_exists(project: ProjectDefinition) -> bool:
    path = project.expanded_local_path
    return bool(path and path.exists())


def open_project_folder(project: ProjectDefinition) -> None:
    path = project.expanded_local_path
    if not path:
        raise FileNotFoundError("Este projeto ainda não possui pasta local cadastrada.")
    if not path.exists():
        raise FileNotFoundError(f"Não encontrei a pasta do projeto:\n{path}")
    os.startfile(path)


def open_project_repository(project: ProjectDefinition) -> None:
    if not project.repository:
        raise FileNotFoundError("Este projeto ainda não possui repositório GitHub cadastrado.")
    webbrowser.open(project.repository)


def run_project(project: ProjectDefinition) -> None:
    if not project.launch_kind or not project.launch_target:
        raise FileNotFoundError("Este projeto ainda não possui comando de execução cadastrado.")
    if not target_exists_for(project.launch_kind, project.launch_target):
        raise FileNotFoundError(
            f"Não encontrei o alvo configurado para execução:\n{project.launch_target}"
        )
    open_target(project.launch_kind, project.launch_target)


def local_git_snapshot(project: ProjectDefinition) -> str:
    path = project.expanded_local_path
    if not path or not path.exists() or not (path / ".git").exists():
        return project.last_commit or "Não disponível"
    try:
        commit = subprocess.run(
            ["git", "-C", str(path), "log", "-1", "--pretty=%h · %s"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.strip()
        return commit or project.last_commit or "Não disponível"
    except Exception:
        LOGGER.debug("Não foi possível consultar o Git local de %s", project.name, exc_info=True)
        return project.last_commit or "Não disponível"
