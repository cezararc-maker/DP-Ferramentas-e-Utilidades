from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from .models import ToolDefinition

APP_FOLDER = "DP Ferramentas e Utilidades"


def resource_path(relative: str) -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    base = Path(bundle_root) if bundle_root else Path(__file__).resolve().parents[2]
    return base / relative


def user_config_path() -> Path:
    base = Path(os.getenv("APPDATA", Path.home())) / APP_FOLDER
    base.mkdir(parents=True, exist_ok=True)
    return base / "tools.json"


def ensure_user_config() -> Path:
    destination = user_config_path()
    if not destination.exists():
        shutil.copy2(resource_path("config/tools.example.json"), destination)
    return destination


def load_tools(path: Path | None = None) -> list[ToolDefinition]:
    source = path or ensure_user_config()
    payload = json.loads(source.read_text(encoding="utf-8"))
    tools = [ToolDefinition.from_dict(item) for item in payload.get("tools", [])]
    ids = [item.id for item in tools]
    if len(ids) != len(set(ids)):
        raise ValueError("O catálogo possui identificadores de ferramentas duplicados.")
    return tools
