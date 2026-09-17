from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from .catalog import APP_FOLDER, load_tools, user_config_path
from .launcher import open_documentation, open_tool, target_exists
from .models import ToolDefinition

CATEGORIES = ["Início", "FGTS", "Folha", "Fiscal", "Documentos"]


def configure_logging() -> None:
    log_dir = user_config_path().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_dir / "aplicativo.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s")


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
        availability = QLabel("Disponível neste computador" if available else "Caminho ainda não localizado")
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
        note = QLabel("Gere primeiro a planilha XLSX no Leitor PDF e depois importe-a no FGTS por Obra / Poligonal.")
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
        self.category = "Início"
        self.dark_theme = True
        self.setWindowTitle("DP - Ferramentas & Utilidades")
        self.resize(1180, 760)
        root = QWidget()
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self._sidebar())
        shell.addWidget(self._content(), 1)
        self.refresh_cards()

    def _sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(235)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(22, 26, 22, 22)
        brand = QLabel("DP")
        brand.setObjectName("brand")
        brand.setFixedSize(52, 52)
        brand.setAlignment(Qt.AlignCenter)
        layout.addWidget(brand)
        name = QLabel("Ferramentas\n& Utilidades")
        name.setObjectName("brandName")
        layout.addWidget(name)
        layout.addSpacing(26)
        for category in CATEGORIES:
            button = QPushButton(category)
            button.setObjectName("nav")
            button.clicked.connect(lambda checked=False, value=category: self.select_category(value))
            layout.addWidget(button)
        layout.addStretch()
        config = QPushButton("Abrir configuração")
        config.setObjectName("secondary")
        config.clicked.connect(lambda: self.open_path(user_config_path()))
        layout.addWidget(config)
        version = QLabel("Versão 0.2.0")
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
        subtitle = QLabel("Sua central de automações do Departamento Pessoal")
        subtitle.setObjectName("description")
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        self.theme_button = QPushButton("☀  Tema claro")
        self.theme_button.setObjectName("themeButton")
        self.theme_button.clicked.connect(self.toggle_theme)
        header.addWidget(self.theme_button)
        layout.addLayout(header)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Pesquisar ferramenta...")
        self.search.textChanged.connect(self.refresh_cards)
        layout.addWidget(self.search)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(0, 4, 8, 8)
        workflow_tools = [tool for tool in self.tools if tool.workflow == "fgts-poligonal"]
        if workflow_tools:
            self.scroll_layout.addWidget(WorkflowSuggestion(workflow_tools, self.launch))
        self.section_title = QLabel("Todas as ferramentas")
        self.section_title.setObjectName("sectionTitle")
        self.scroll_layout.addWidget(self.section_title)
        self.card_host = QWidget()
        self.grid = QGridLayout(self.card_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(16)
        self.scroll_layout.addWidget(self.card_host)
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
        self.section_title.setText("Todas as ferramentas" if category == "Início" else category)
        self.refresh_cards()

    def refresh_cards(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        query = self.search.text().casefold().strip()
        visible = [tool for tool in self.tools if (self.category == "Início" or tool.category == self.category) and (not query or query in (tool.name + " " + tool.description).casefold())]
        for index, tool in enumerate(visible):
            self.grid.addWidget(ToolCard(tool, self.launch, self.documentation), index // 3, index % 3)

    def launch(self, tool: ToolDefinition) -> None:
        try:
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

    def open_path(self, path: Path) -> None:
        import os
        os.startfile(path)


DARK_STYLE = """
QWidget { background: #07111f; color: #e7eef7; font-family: 'Segoe UI'; font-size: 13px; }
#sidebar { background: #0b1728; border-right: 1px solid #193047; }
#brand { color: #07111f; background: #29d3c2; border-radius: 13px; font-size: 20px; font-weight: 800; }
#brandName { font-size: 19px; font-weight: 700; margin-top: 7px; }
#heading { font-size: 28px; font-weight: 750; }
#sectionTitle, #workflowTitle { font-size: 18px; font-weight: 700; }
#description, #muted { color: #9db0c4; }
#eyebrow { color: #48e1d1; font-size: 11px; font-weight: 700; }
QLineEdit { background: #0d1c2e; border: 1px solid #213b54; border-radius: 9px; padding: 11px; margin: 10px 0; }
#toolCard { background: #0c192a; border: 1px solid #1d344c; border-radius: 12px; min-width: 235px; min-height: 210px; }
#workflow { background: #10273b; border: 1px solid #28bcae; border-radius: 12px; padding: 7px; margin: 4px 0 10px 0; }
#cardTitle { font-size: 15px; font-weight: 700; }
#toolIcon { color: #48e1d1; font-weight: 800; background: #123049; border-radius: 8px; padding: 7px; }
#status { color: #8ddbd3; background: #12352f; border-radius: 8px; padding: 4px 7px; font-size: 11px; }
#available { color: #6dd6a7; font-size: 11px; }
#missing { color: #f1b56b; font-size: 11px; }
#flowArrow { color: #48e1d1; font-weight: 700; }
QPushButton { background: #24bfae; color: #041315; border: 0; border-radius: 8px; padding: 9px 12px; font-weight: 650; }
QPushButton:hover { background: #48e1d1; }
#secondary, #nav, #themeButton { background: transparent; color: #c9d6e4; border: 1px solid #27435e; text-align: left; }
#nav { border: 0; padding: 10px; }
#nav:hover, #secondary:hover, #themeButton:hover { background: #14283d; color: white; }
#workflowButton { background: #17384d; color: #e7eef7; border: 1px solid #2b6271; text-align: left; }
QScrollArea { background: transparent; }
"""

LIGHT_STYLE = """
QWidget { background: #f4f7fa; color: #172333; font-family: 'Segoe UI'; font-size: 13px; }
#sidebar { background: #ffffff; border-right: 1px solid #d9e2ea; }
#brand { color: #ffffff; background: #087f73; border-radius: 13px; font-size: 20px; font-weight: 800; }
#brandName { font-size: 19px; font-weight: 700; margin-top: 7px; }
#heading { font-size: 28px; font-weight: 750; }
#sectionTitle, #workflowTitle { font-size: 18px; font-weight: 700; }
#description, #muted { color: #5d6d7e; }
#eyebrow { color: #087f73; font-size: 11px; font-weight: 700; }
QLineEdit { background: #ffffff; border: 1px solid #c7d3df; border-radius: 9px; padding: 11px; margin: 10px 0; }
#toolCard { background: #ffffff; border: 1px solid #d7e0e8; border-radius: 12px; min-width: 235px; min-height: 210px; }
#workflow { background: #e9f7f5; border: 1px solid #45a99e; border-radius: 12px; padding: 7px; margin: 4px 0 10px 0; }
#cardTitle { font-size: 15px; font-weight: 700; }
#toolIcon { color: #087f73; font-weight: 800; background: #dff3f0; border-radius: 8px; padding: 7px; }
#status { color: #17695f; background: #d9f0e8; border-radius: 8px; padding: 4px 7px; font-size: 11px; }
#available { color: #23805c; font-size: 11px; }
#missing { color: #a86514; font-size: 11px; }
#flowArrow { color: #087f73; font-weight: 700; }
QPushButton { background: #087f73; color: white; border: 0; border-radius: 8px; padding: 9px 12px; font-weight: 650; }
QPushButton:hover { background: #0a9b8d; }
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
