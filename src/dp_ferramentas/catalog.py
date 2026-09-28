from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from .models import ProjectDefinition, ToolDefinition

APP_FOLDER = "DP Ferramentas e Utilidades"


def resource_path(relative: str) -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    base = Path(bundle_root) if bundle_root else Path(__file__).resolve().parents[2]
    return base / relative


def user_config_dir() -> Path:
    base = Path(os.getenv("APPDATA", Path.home())) / APP_FOLDER
    base.mkdir(parents=True, exist_ok=True)
    return base


def user_config_path() -> Path:
    return user_config_dir() / "tools.json"


def user_projects_path() -> Path:
    return user_config_dir() / "projects.json"


def _ensure_config(destination: Path, bundled_relative: str) -> Path:
    if not destination.exists():
        shutil.copy2(resource_path(bundled_relative), destination)
    return destination


def _merge_missing_entries(destination: Path, bundled_relative: str, key: str) -> Path:
    _ensure_config(destination, bundled_relative)
    bundled = json.loads(resource_path(bundled_relative).read_text(encoding="utf-8"))
    current = json.loads(destination.read_text(encoding="utf-8"))
    existing_ids = {item.get("id") for item in current.get(key, [])}
    missing = [item for item in bundled.get(key, []) if item.get("id") not in existing_ids]
    if missing:
        current.setdefault(key, []).extend(missing)
        destination.write_text(
            json.dumps(current, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return destination


def ensure_user_config() -> Path:
    return _merge_missing_entries(
        user_config_path(),
        "config/tools.example.json",
        "tools",
    )


def ensure_projects_config() -> Path:
    return _ensure_config(user_projects_path(), "config/projects.example.json")


def load_tools(path: Path | None = None) -> list[ToolDefinition]:
    source = path or ensure_user_config()
    payload = json.loads(source.read_text(encoding="utf-8"))
    tools = [ToolDefinition.from_dict(item) for item in payload.get("tools", [])]
    ids = [item.id for item in tools]
    if len(ids) != len(set(ids)):
        raise ValueError("O catálogo possui identificadores de ferramentas duplicados.")
    return tools


def load_projects(path: Path | None = None) -> list[ProjectDefinition]:
    source = path or ensure_projects_config()
    payload = json.loads(source.read_text(encoding="utf-8"))
    projects = [ProjectDefinition.from_dict(item) for item in payload.get("projects", [])]
    ids = [item.id for item in projects]
    if len(ids) != len(set(ids)):
        raise ValueError("O painel possui identificadores de projetos duplicados.")
    return projects
