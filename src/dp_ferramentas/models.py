from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    id: str
    name: str
    description: str
    category: str
    kind: str
    target: str
    status: str = "Em desenvolvimento"
    icon: str = "▣"
    documentation: str = ""
    workflow: str = ""
    step: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "ToolDefinition":
        required = {"id", "name", "description", "category", "kind", "target"}
        missing = sorted(required - data.keys())
        if missing:
            raise ValueError(f"Campos obrigatórios ausentes: {', '.join(missing)}")
        return cls(**{key: data[key] for key in cls.__dataclass_fields__ if key in data})

    @property
    def expanded_target(self) -> Path:
        return Path(os.path.expandvars(os.path.expanduser(self.target)))


@dataclass(frozen=True, slots=True)
class ProjectDefinition:
    id: str
    name: str
    summary: str
    status: str
    progress: int = 0
    category: str = "Geral"
    repository: str = ""
    local_path: str = ""
    last_update: str = ""
    last_commit: str = ""
    blocker: str = ""
    next_task: str = ""
    dependencies: list[str] = field(default_factory=list)
    icon: str = "PRJ"
    launch_kind: str = ""
    launch_target: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectDefinition":
        required = {"id", "name", "summary", "status"}
        missing = sorted(required - data.keys())
        if missing:
            raise ValueError(f"Campos obrigatórios ausentes no projeto: {', '.join(missing)}")
        payload = {key: data[key] for key in cls.__dataclass_fields__ if key in data}
        progress = int(payload.get("progress", 0))
        if not 0 <= progress <= 100:
            raise ValueError(f"Progresso inválido para {data.get('id', 'projeto')}: {progress}")
        payload["progress"] = progress
        payload["dependencies"] = list(payload.get("dependencies", []))
        return cls(**payload)

    @property
    def expanded_local_path(self) -> Path | None:
        if not self.local_path:
            return None
        return Path(os.path.expandvars(os.path.expanduser(self.local_path)))

    @property
    def expanded_launch_target(self) -> Path | None:
        if not self.launch_target or self.launch_kind in {"url", "github"}:
            return None
        return Path(os.path.expandvars(os.path.expanduser(self.launch_target)))
