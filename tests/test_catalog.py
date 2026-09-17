import json

import pytest

from dp_ferramentas.catalog import load_tools
from dp_ferramentas.models import ToolDefinition


def test_required_fields():
    with pytest.raises(ValueError, match="obrigatórios"):
        ToolDefinition.from_dict({"id": "incompleta"})


def test_loads_workflow(tmp_path):
    path = tmp_path / "tools.json"
    path.write_text(json.dumps({"tools": [{"id": "a", "name": "A", "description": "Teste", "category": "FGTS", "kind": "url", "target": "https://example.com", "workflow": "fluxo", "step": 1}]}), encoding="utf-8")
    tools = load_tools(path)
    assert tools[0].workflow == "fluxo"
    assert tools[0].step == 1


def test_rejects_duplicate_ids(tmp_path):
    item = {"id": "a", "name": "A", "description": "Teste", "category": "FGTS", "kind": "url", "target": "https://example.com"}
    path = tmp_path / "tools.json"
    path.write_text(json.dumps({"tools": [item, item]}), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicados"):
        load_tools(path)
