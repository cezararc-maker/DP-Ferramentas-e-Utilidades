import json

import pytest

from dp_ferramentas.catalog import ensure_projects_config, ensure_user_config, load_projects, load_tools, user_config_path, user_projects_path
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


def test_existing_user_catalog_receives_new_bundled_tools_without_losing_custom(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    path = user_config_path()
    custom = {
        "id": "custom",
        "name": "Ferramenta personalizada",
        "description": "Mantida pelo usuário",
        "category": "Documentos",
        "kind": "url",
        "target": "https://example.com",
    }
    path.write_text(json.dumps({"tools": [custom]}), encoding="utf-8")

    ensure_user_config()
    ids = {item["id"] for item in json.loads(path.read_text(encoding="utf-8"))["tools"]}

    assert "custom" in ids
    assert "seguro-desemprego-organizador" in ids
    assert "distribuidor-documentos-rescisao" in ids


def test_existing_fgts_entries_are_updated_without_touching_others(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    reader = {"id": "leitor-pdf-poligonal", "name": "Leitor", "description": "x", "category": "FGTS", "kind": "html",
              "target": r"%USERPROFILE%\Desktop\GitHub\Leitor_PDF_Extrato_Mensal_Poligonal\index.html", "status": "Etapa 1 de 2"}
    custom = {"id": "custom", "name": "Personalizada", "description": "x", "category": "Outros", "kind": "url", "target": "https://example.com"}
    user_config_path().write_text(json.dumps({"tools": [reader, custom]}), encoding="utf-8")
    ensure_user_config()
    saved = {item["id"]: item for item in json.loads(user_config_path().read_text(encoding="utf-8"))["tools"]}
    assert saved["leitor-pdf-poligonal"]["target"].endswith("ABRIR_LEITOR_FGTS.bat")
    assert saved["leitor-pdf-poligonal"]["kind"] == "batch"
    assert saved["leitor-pdf-poligonal"]["status"] == "Testado e validado"
    assert saved["custom"] == custom

    project = {"id": "fgts-poligonal", "name": "FGTS", "summary": "x", "status": "ATIVO", "progress": 67,
               "last_update": "17/09/2026", "blocker": "antigo", "next_task": "antiga"}
    user_projects_path().write_text(json.dumps({"projects": [project]}), encoding="utf-8")
    ensure_projects_config()
    saved_project = json.loads(user_projects_path().read_text(encoding="utf-8"))["projects"][0]
    assert saved_project["status"] == "FINALIZADO"
    assert saved_project["progress"] == 100
    assert saved_project["blocker"] == ""


def test_recent_html_reader_catalog_migrates_to_integrated_launcher(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    target = r"%USERPROFILE%\Desktop\GitHub\Leitor_PDF_Extrato_Mensal_Poligonal\Leitor_FGTS.html"
    tool = {"id": "leitor-pdf-poligonal", "name": "Leitor", "description": "x", "category": "FGTS",
            "kind": "html", "target": target, "status": "Testado e validado"}
    user_config_path().write_text(json.dumps({"tools": [tool]}), encoding="utf-8")
    ensure_user_config()
    saved = json.loads(user_config_path().read_text(encoding="utf-8"))["tools"][0]
    assert saved["target"].endswith("ABRIR_LEITOR_FGTS.bat")
    assert saved["kind"] == "batch"

    project = {"id": "leitor-pdf-poligonal", "name": "Leitor", "summary": "x", "status": "FINALIZADO",
               "progress": 100, "launch_kind": "html", "launch_target": target}
    user_projects_path().write_text(json.dumps({"projects": [project]}), encoding="utf-8")
    ensure_projects_config()
    saved_project = json.loads(user_projects_path().read_text(encoding="utf-8"))["projects"][0]
    assert saved_project["launch_target"].endswith("ABRIR_LEITOR_FGTS.bat")
    assert saved_project["launch_kind"] == "batch"
