from __future__ import annotations

import os
from dataclasses import dataclass
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
