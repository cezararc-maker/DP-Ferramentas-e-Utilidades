from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .catalog import APP_FOLDER, load_projects, load_tools, user_config_path, user_projects_path
from .launcher import (
    local_git_snapshot,
    open_documentation,
    open_project_folder,
    open_project_repository,
    open_tool,
    project_folder_exists,
    run_project,
    target_exists,
)
from .models import ProjectDefinition, ToolDefinition
from .seguro_desemprego_ui import SeguroDesempregoWindow

CATEGORIES = ["Início", "Projetos", "FGTS", "Folha", "Fiscal", "Documentos"]
PROJECT_STATUSES = ["Todos", "ATIVO", "BLOQUEADO", "PAUSADO", "PLANEJADO", "FINALIZADO"]
STATUS_OBJECT = {
    "ATIVO": "projectStatusActive",
    "BLOQUEADO": "projectStatusBlocked",
    "PAUSADO": "projectStatusPaused",
    "PLANEJADO": "projectStatusPlanned",
    "FINALIZADO": "projectStatusDone",
}


def configure_logging() -> None:
    log_dir = user_config_path().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "aplicativo.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler],
        format="%(asctime)s %(levelname)s %(message)s",
    )


class ToolCard(QFrame):
    def __init__(self, tool: ToolDefinition, launch, documentation):
        super().__init__()
        self.setObjectName("toolCard")
        layout = QVBoxLayout(self)
        layout.setSpacing(9)
        header = QHBoxLayout()
        icon = QLabel(tool.icon)
        icon.setObjectName("toolIcon")
        status = QLabel(tool.status)
        status.setObjectName("status")
        header.addWidget(icon)
        header.addStretch()
        header.addWidget(status)
        layout.addLayout(header)
        title = QLabel(tool.name)
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        layout.addWidget(title)
        description = QLabel(tool.description)
        description.setObjectName("description")
        description.setWordWrap(True)
        layout.addWidget(description)
        layout.addStretch()
        available = target_exists(tool)
        availability = QLabel(
            "Disponível neste computador" if available else "Caminho ainda não localizado"
        )
        availability.setObjectName("available" if available else "missing")
        layout.addWidget(availability)
        actions = QHBoxLayout()
        doc = QPushButton("Documentação")
        doc.setObjectName("secondary")
        doc.setEnabled(bool(tool.documentation))
        doc.clicked.connect(lambda: documentation(tool))
        run = QPushButton("Abrir")
        run.clicked.connect(lambda: launch(tool))
        actions.addWidget(doc)
        actions.addWidget(run)
        layout.addLayout(actions)


class ProjectCard(QFrame):
    def __init__(self, project: ProjectDefinition, open_folder, open_repo, run):
        super().__init__()
        self.setObjectName("projectCard")
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        header = QHBoxLayout()
        icon = QLabel(project.icon)
        icon.setObjectName("toolIcon")
        status = QLabel(project.status)
        status.setObjectName(STATUS_OBJECT.get(project.status.upper(), "projectStatusPlanned"))
        header.addWidget(icon)
        header.addStretch()
        header.addWidget(status)
        layout.addLayout(header)

        title = QLabel(project.name)
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        summary = QLabel(project.summary)
        summary.setObjectName("description")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        progress_row = QHBoxLayout()
        progress_label = QLabel(f"Progresso estimado: {project.progress}%")
        progress_label.setObjectName("projectMeta")
        progress_row.addWidget(progress_label)
        progress_row.addStretch()
        layout.addLayout(progress_row)
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(project.progress)
        progress.setTextVisible(False)
        progress.setObjectName("projectProgress")
        layout.addWidget(progress)

        details = QGridLayout()
        details.setHorizontalSpacing(10)
        details.setVerticalSpacing(5)
        self._detail(details, 0, "Área", project.category or "Geral")
        self._detail(details, 1, "Última atualização", project.last_update or "Não informada")
        self._detail(details, 2, "Último commit", local_git_snapshot(project))
        deps = ", ".join(project.dependencies) if project.dependencies else "Nenhuma dependência registrada"
        self._detail(details, 3, "Dependências", deps)
        layout.addLayout(details)

        if project.blocker:
            blocker = QLabel(f"Bloqueio atual: {project.blocker}")
            blocker.setObjectName("projectBlocker")
            blocker.setWordWrap(True)
            layout.addWidget(blocker)

        next_task = QLabel(f"Próxima tarefa: {project.next_task or 'Revisar e definir próxima ação.'}")
        next_task.setObjectName("projectNext")
        next_task.setWordWrap(True)
        layout.addWidget(next_task)
        layout.addStretch()

        available = project_folder_exists(project)
        availability = QLabel(
            "Pasta local localizada" if available else "Pasta local não localizada/cadastrada"
        )
        availability.setObjectName("available" if available else "missing")
        layout.addWidget(availability)

        actions = QHBoxLayout()
        folder = QPushButton("Abrir projeto")
        folder.setObjectName("secondary")
        folder.setEnabled(bool(project.local_path))
        folder.clicked.connect(lambda: open_folder(project))
        repo = QPushButton("GitHub")
        repo.setObjectName("secondary")
        repo.setEnabled(bool(project.repository))
        repo.clicked.connect(lambda: open_repo(project))
        execute = QPushButton("Executar")
        execute.setEnabled(bool(project.launch_kind and project.launch_target))
        execute.clicked.connect(lambda: run(project))
        actions.addWidget(folder)
        actions.addWidget(repo)
        actions.addWidget(execute)
        layout.addLayout(actions)

    @staticmethod
    def _detail(grid: QGridLayout, row: int, label: str, value: str) -> None:
        key = QLabel(f"{label}:")
        key.setObjectName("projectMetaKey")
        val = QLabel(value)
        val.setObjectName("projectMeta")
        val.setWordWrap(True)
        grid.addWidget(key, row, 0, alignment=Qt.AlignTop)
        grid.addWidget(val, row, 1)


class ProjectSummary(QFrame):
    def __init__(self, projects: list[ProjectDefinition]):
        super().__init__()
        self.setObjectName("projectSummary")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        for status in PROJECT_STATUSES[1:]:
            count = sum(1 for project in projects if project.status.upper() == status)
            card = QVBoxLayout()
            number = QLabel(str(count))
            number.setObjectName("summaryNumber")
            number.setAlignment(Qt.AlignCenter)
            text = QLabel(status.title())
            text.setObjectName("summaryLabel")
            text.setAlignment(Qt.AlignCenter)
            card.addWidget(number)
            card.addWidget(text)
            layout.addLayout(card)


class WorkflowSuggestion(QFrame):
    def __init__(self, tools: list[ToolDefinition], launch):
        super().__init__()
        self.setObjectName("workflow")
        layout = QVBoxLayout(self)
        summary = QHBoxLayout()
        labels = QVBoxLayout()
        eyebrow = QLabel("SUGESTÃO DE FLUXO")
        eyebrow.setObjectName("eyebrow")
        labels.addWidget(eyebrow)
        title = QLabel("FGTS Poligonal: use as duas ferramentas em sequência")
        title.setObjectName("workflowTitle")
        labels.addWidget(title)
        summary.addLayout(labels, 1)
        self.toggle = QPushButton("Ver etapas  ▼")
        self.toggle.setObjectName("secondary")
        self.toggle.clicked.connect(self.toggle_details)
        summary.addWidget(self.toggle)
        layout.addLayout(summary)
        self.details = QWidget()
        detail_layout = QVBoxLayout(self.details)
        detail_layout.setContentsMargins(0, 8, 0, 0)
        note = QLabel(
            "Gere primeiro a planilha XLSX no Leitor PDF e depois importe-a no FGTS por Obra / Poligonal."
        )
        note.setWordWrap(True)
        note.setObjectName("description")
        detail_layout.addWidget(note)
        steps = QHBoxLayout()
        ordered = sorted(tools, key=lambda item: item.step or 0)
        for index, tool in enumerate(ordered):
            step = QPushButton(f"{tool.step}  {tool.name}")
            step.setObjectName("workflowButton")
            step.clicked.connect(lambda checked=False, current=tool: launch(current))
            steps.addWidget(step)
            if index < len(ordered) - 1:
                arrow = QLabel("→  XLSX  →")
                arrow.setObjectName("flowArrow")
                steps.addWidget(arrow)
        detail_layout.addLayout(steps)
        self.details.setVisible(False)
        layout.addWidget(self.details)

    def toggle_details(self) -> None:
        visible = not self.details.isVisible()
        self.details.setVisible(visible)
        self.toggle.setText("Ocultar etapas  ▲" if visible else "Ver etapas  ▼")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tools = load_tools()
        self.projects = load_projects()
        self.category = "Início"
        self.dark_theme = True
        self.seguro_desemprego_window: SeguroDesempregoWindow | None = None
        self.setWindowTitle("DP - Ferramentas & Utilidades")
        self.resize(1240, 800)
        root = QWidget()
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self._sidebar())
        shell.addWidget(self._content(), 1)
        self._apply_view_state()

    def _sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(245)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(22, 26, 22, 22)
        brand = QLabel("DP")
        brand.setObjectName("brand")
        brand.setFixedSize(58, 58)
        brand.setAlignment(Qt.AlignCenter)
        layout.addWidget(brand)
        name = QLabel("Ferramentas\n& Utilidades")
        name.setObjectName("brandName")
        layout.addWidget(name)
        layout.addSpacing(26)
        for category in CATEGORIES:
            button = QPushButton(category)
            button.setObjectName("nav")
            button.clicked.connect(
                lambda checked=False, value=category: self.select_category(value)
            )
            layout.addWidget(button)
        layout.addStretch()
        config = QPushButton("Config. ferramentas")
        config.setObjectName("secondary")
        config.clicked.connect(lambda: self.open_path(user_config_path()))
        layout.addWidget(config)
        projects = QPushButton("Config. projetos")
        projects.setObjectName("secondary")
        projects.clicked.connect(lambda: self.open_path(user_projects_path()))
        layout.addWidget(projects)
        version = QLabel("Versão 0.4.0")
        version.setObjectName("muted")
        layout.addWidget(version)
        return sidebar

    def _content(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(34, 28, 34, 24)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        heading = QLabel("DP - Ferramentas & Utilidades")
        heading.setObjectName("heading")
        titles.addWidget(heading)
        self.subtitle = QLabel("Sua central de automações do Departamento Pessoal")
        self.subtitle.setObjectName("description")
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)
        self.theme_button = QPushButton("☀  Tema claro")
        self.theme_button.setObjectName("themeButton")
        self.theme_button.clicked.connect(self.toggle_theme)
        header.addWidget(self.theme_button)
        layout.addLayout(header)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Pesquisar ferramenta...")
        self.search.textChanged.connect(self.refresh_current_view)
        filters.addWidget(self.search, 1)
        self.status_filter = QComboBox()
        self.status_filter.addItems(PROJECT_STATUSES)
        self.status_filter.currentTextChanged.connect(self.refresh_projects)
        self.status_filter.setVisible(False)
        filters.addWidget(self.status_filter)
        layout.addLayout(filters)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(0, 4, 8, 8)

        workflow_tools = [tool for tool in self.tools if tool.workflow == "fgts-poligonal"]
        self.workflow_widget = WorkflowSuggestion(workflow_tools, self.launch) if workflow_tools else None
        if self.workflow_widget:
            self.scroll_layout.addWidget(self.workflow_widget)

        self.project_summary = ProjectSummary(self.projects)
        self.project_summary.setVisible(False)
        self.scroll_layout.addWidget(self.project_summary)

        self.section_title = QLabel("Todas as ferramentas")
        self.section_title.setObjectName("sectionTitle")
        self.scroll_layout.addWidget(self.section_title)

        self.card_host = QWidget()
        self.grid = QGridLayout(self.card_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(16)
        self.scroll_layout.addWidget(self.card_host)

        self.project_host = QWidget()
        self.project_grid = QGridLayout(self.project_host)
        self.project_grid.setContentsMargins(0, 0, 0, 0)
        self.project_grid.setSpacing(16)
        self.project_host.setVisible(False)
        self.scroll_layout.addWidget(self.project_host)

        self.scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)
        return page

    def toggle_theme(self) -> None:
        self.dark_theme = not self.dark_theme
        app = QApplication.instance()
        app.setStyleSheet(DARK_STYLE if self.dark_theme else LIGHT_STYLE)
        self.theme_button.setText("☀  Tema claro" if self.dark_theme else "☾  Tema escuro")

    def select_category(self, category: str) -> None:
        self.category = category
        self._apply_view_state()

    def _apply_view_state(self) -> None:
        project_mode = self.category == "Projetos"
        self.card_host.setVisible(not project_mode)
        self.project_host.setVisible(project_mode)
        self.project_summary.setVisible(project_mode)
        self.status_filter.setVisible(project_mode)
        if self.workflow_widget:
            self.workflow_widget.setVisible(self.category == "Início")

        if project_mode:
            self.section_title.setText("Painel oficial de projetos")
            self.subtitle.setText("Status, progresso, bloqueios e próximos passos em um único lugar")
            self.search.setPlaceholderText("Pesquisar projeto...")
            self.refresh_projects()
        else:
            self.section_title.setText("Todas as ferramentas" if self.category == "Início" else self.category)
            self.subtitle.setText("Sua central de automações do Departamento Pessoal")
            self.search.setPlaceholderText("Pesquisar ferramenta...")
            self.refresh_cards()

    def refresh_current_view(self) -> None:
        if self.category == "Projetos":
            self.refresh_projects()
        else:
            self.refresh_cards()

    @staticmethod
    def _clear_grid(grid: QGridLayout) -> None:
        while grid.count():
            item = grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh_cards(self) -> None:
        self._clear_grid(self.grid)
        query = self.search.text().casefold().strip()
        visible = [
            tool
            for tool in self.tools
            if (self.category == "Início" or tool.category == self.category)
            and (not query or query in (tool.name + " " + tool.description).casefold())
        ]
        for index, tool in enumerate(visible):
            self.grid.addWidget(
                ToolCard(tool, self.launch, self.documentation), index // 3, index % 3
            )

    def refresh_projects(self) -> None:
        self._clear_grid(self.project_grid)
        query = self.search.text().casefold().strip()
        selected_status = self.status_filter.currentText()
        visible = []
        for project in self.projects:
            haystack = " ".join(
                [
                    project.name,
                    project.summary,
                    project.category,
                    project.status,
                    project.blocker,
                    project.next_task,
                    " ".join(project.dependencies),
                ]
            ).casefold()
            if query and query not in haystack:
                continue
            if selected_status != "Todos" and project.status.upper() != selected_status:
                continue
            visible.append(project)
        for index, project in enumerate(visible):
            self.project_grid.addWidget(
                ProjectCard(
                    project,
                    self.open_project_folder_action,
                    self.open_project_repository_action,
                    self.run_project_action,
                ),
                index // 2,
                index % 2,
            )

    def launch(self, tool: ToolDefinition) -> None:
        try:
            if tool.kind == "internal":
                if tool.target != "seguro-desemprego":
                    raise ValueError(f"Ferramenta interna não suportada: {tool.target}")
                if self.seguro_desemprego_window is None:
                    self.seguro_desemprego_window = SeguroDesempregoWindow(self)
                    self.seguro_desemprego_window.destroyed.connect(
                        lambda: setattr(self, "seguro_desemprego_window", None)
                    )
                self.seguro_desemprego_window.show()
                self.seguro_desemprego_window.raise_()
                self.seguro_desemprego_window.activateWindow()
                return
            if not target_exists(tool):
                raise FileNotFoundError(f"Não encontrei o caminho configurado:\n{tool.expanded_target}")
            open_tool(tool)
        except Exception as exc:
            logging.exception("Falha ao abrir %s", tool.name)
            QMessageBox.warning(self, "Não foi possível abrir", str(exc))

    def documentation(self, tool: ToolDefinition) -> None:
        try:
            open_documentation(tool)
        except Exception as exc:
            QMessageBox.information(self, "Documentação", str(exc))

    def open_project_folder_action(self, project: ProjectDefinition) -> None:
        try:
            open_project_folder(project)
        except Exception as exc:
            QMessageBox.warning(self, "Abrir projeto", str(exc))

    def open_project_repository_action(self, project: ProjectDefinition) -> None:
        try:
            open_project_repository(project)
        except Exception as exc:
            QMessageBox.information(self, "GitHub", str(exc))

    def run_project_action(self, project: ProjectDefinition) -> None:
        try:
            run_project(project)
        except Exception as exc:
            logging.exception("Falha ao executar projeto %s", project.name)
            QMessageBox.warning(self, "Executar projeto", str(exc))

    def open_path(self, path: Path) -> None:
        import os
        os.startfile(path)


DARK_STYLE = """
QWidget { background: #07111f; color: #e7eef7; font-family: 'Segoe UI'; font-size: 13px; }
#sidebar { background: #0b1728; border-right: 1px solid #193047; }
#brand { color: #07111f; background: #29d3c2; border-radius: 14px; font-size: 21px; font-weight: 800; }
#brandName { font-size: 19px; font-weight: 700; margin-top: 7px; }
#heading { font-size: 28px; font-weight: 750; }
#sectionTitle, #workflowTitle { font-size: 18px; font-weight: 700; }
#description, #muted, #projectMeta { color: #9db0c4; }
#projectMetaKey { color: #c4d2df; font-weight: 700; }
#eyebrow { color: #48e1d1; font-size: 11px; font-weight: 700; }
QLineEdit, QComboBox { background: #0d1c2e; border: 1px solid #213b54; border-radius: 9px; padding: 10px; margin: 10px 0; }
#toolCard, #projectCard { background: #0c192a; border: 1px solid #1d344c; border-radius: 12px; min-width: 235px; }
#toolCard { min-height: 210px; }
#projectCard { min-height: 430px; }
#workflow { background: #10273b; border: 1px solid #28bcae; border-radius: 12px; padding: 7px; margin: 4px 0 10px 0; }
#projectSummary { background: #0d1c2e; border: 1px solid #213b54; border-radius: 12px; }
#summaryNumber { font-size: 22px; font-weight: 800; color: #48e1d1; }
#summaryLabel { font-size: 10px; color: #9db0c4; }
#cardTitle { font-size: 15px; font-weight: 700; }
#toolIcon { color: #48e1d1; font-weight: 800; background: #123049; border-radius: 8px; padding: 7px; }
#status, #projectStatusActive, #projectStatusBlocked, #projectStatusPaused, #projectStatusPlanned, #projectStatusDone { border-radius: 8px; padding: 4px 7px; font-size: 11px; font-weight: 700; }
#status, #projectStatusActive { color: #8ddbd3; background: #12352f; }
#projectStatusBlocked { color: #ffc3bd; background: #4b2222; }
#projectStatusPaused { color: #f3d7a1; background: #4a3719; }
#projectStatusPlanned { color: #c6d4ff; background: #24365b; }
#projectStatusDone { color: #b8efc8; background: #173d29; }
#projectBlocker { color: #ffc3bd; background: #321b22; border-radius: 8px; padding: 8px; }
#projectNext { color: #dce8f4; background: #10243a; border-radius: 8px; padding: 8px; }
#projectProgress { background: #14283d; border: 0; border-radius: 4px; height: 8px; }
#projectProgress::chunk { background: #29d3c2; border-radius: 4px; }
#available { color: #6dd6a7; font-size: 11px; }
#missing { color: #f1b56b; font-size: 11px; }
#flowArrow { color: #48e1d1; font-weight: 700; }
QPushButton { background: #24bfae; color: #041315; border: 0; border-radius: 8px; padding: 9px 12px; font-weight: 650; }
QPushButton:hover { background: #48e1d1; }
QPushButton:disabled { background: #233345; color: #6f8092; }
#secondary, #nav, #themeButton { background: transparent; color: #c9d6e4; border: 1px solid #27435e; text-align: left; }
#nav { border: 0; padding: 10px; }
#nav:hover, #secondary:hover, #themeButton:hover { background: #14283d; color: white; }
#workflowButton { background: #17384d; color: #e7eef7; border: 1px solid #2b6271; text-align: left; }
QScrollArea { background: transparent; }
"""

LIGHT_STYLE = """
QWidget { background: #f4f7fa; color: #172333; font-family: 'Segoe UI'; font-size: 13px; }
#sidebar { background: #ffffff; border-right: 1px solid #d9e2ea; }
#brand { color: #ffffff; background: #087f73; border-radius: 14px; font-size: 21px; font-weight: 800; }
#brandName { font-size: 19px; font-weight: 700; margin-top: 7px; }
#heading { font-size: 28px; font-weight: 750; }
#sectionTitle, #workflowTitle { font-size: 18px; font-weight: 700; }
#description, #muted, #projectMeta { color: #5d6d7e; }
#projectMetaKey { color: #33475b; font-weight: 700; }
#eyebrow { color: #087f73; font-size: 11px; font-weight: 700; }
QLineEdit, QComboBox { background: #ffffff; border: 1px solid #c7d3df; border-radius: 9px; padding: 10px; margin: 10px 0; }
#toolCard, #projectCard { background: #ffffff; border: 1px solid #d7e0e8; border-radius: 12px; min-width: 235px; }
#toolCard { min-height: 210px; }
#projectCard { min-height: 430px; }
#workflow { background: #e9f7f5; border: 1px solid #45a99e; border-radius: 12px; padding: 7px; margin: 4px 0 10px 0; }
#projectSummary { background: #ffffff; border: 1px solid #d7e0e8; border-radius: 12px; }
#summaryNumber { font-size: 22px; font-weight: 800; color: #087f73; }
#summaryLabel { font-size: 10px; color: #5d6d7e; }
#cardTitle { font-size: 15px; font-weight: 700; }
#toolIcon { color: #087f73; font-weight: 800; background: #dff3f0; border-radius: 8px; padding: 7px; }
#status, #projectStatusActive, #projectStatusBlocked, #projectStatusPaused, #projectStatusPlanned, #projectStatusDone { border-radius: 8px; padding: 4px 7px; font-size: 11px; font-weight: 700; }
#status, #projectStatusActive { color: #17695f; background: #d9f0e8; }
#projectStatusBlocked { color: #8a2d24; background: #fbe0dc; }
#projectStatusPaused { color: #80550d; background: #f8ecd0; }
#projectStatusPlanned { color: #334f91; background: #e1e8fb; }
#projectStatusDone { color: #23623b; background: #def3e5; }
#projectBlocker { color: #8a2d24; background: #fff0ee; border-radius: 8px; padding: 8px; }
#projectNext { color: #29445d; background: #eef4f8; border-radius: 8px; padding: 8px; }
#projectProgress { background: #e6edf3; border: 0; border-radius: 4px; height: 8px; }
#projectProgress::chunk { background: #087f73; border-radius: 4px; }
#available { color: #23805c; font-size: 11px; }
#missing { color: #a86514; font-size: 11px; }
#flowArrow { color: #087f73; font-weight: 700; }
QPushButton { background: #087f73; color: white; border: 0; border-radius: 8px; padding: 9px 12px; font-weight: 650; }
QPushButton:hover { background: #0a9b8d; }
QPushButton:disabled { background: #dce4ea; color: #8a98a5; }
#secondary, #nav, #themeButton { background: transparent; color: #33475b; border: 1px solid #c5d1dc; text-align: left; }
#nav { border: 0; padding: 10px; }
#nav:hover, #secondary:hover, #themeButton:hover { background: #e5edf3; color: #111827; }
#workflowButton { background: #ffffff; color: #1f3847; border: 1px solid #8fbeb8; text-align: left; }
QScrollArea { background: transparent; }
"""


def main() -> int:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_FOLDER)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(DARK_STYLE)
    window = MainWindow()
    window.show()
    return app.exec()
