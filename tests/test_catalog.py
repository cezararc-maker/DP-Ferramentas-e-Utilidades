import json

import pytest

from dp_ferramentas.catalog import load_projects, load_tools
from dp_ferramentas.models import ProjectDefinition, ToolDefinition


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


def test_project_definition_validates_progress():
    with pytest.raises(ValueError, match="Progresso inválido"):
        ProjectDefinition.from_dict({"id": "x", "name": "X", "summary": "Teste", "status": "ATIVO", "progress": 101})


def test_loads_projects_and_dependencies(tmp_path):
    path = tmp_path / "projects.json"
    path.write_text(json.dumps({"projects": [{"id": "p", "name": "Projeto", "summary": "Teste", "status": "ATIVO", "progress": 40, "dependencies": ["Outro"]}]}), encoding="utf-8")
    projects = load_projects(path)
    assert projects[0].progress == 40
    assert projects[0].dependencies == ["Outro"]


def test_rejects_duplicate_project_ids(tmp_path):
    item = {"id": "p", "name": "Projeto", "summary": "Teste", "status": "ATIVO"}
    path = tmp_path / "projects.json"
    path.write_text(json.dumps({"projects": [item, item]}), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicados"):
        load_projects(path)
