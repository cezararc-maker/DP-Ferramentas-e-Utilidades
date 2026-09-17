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
        availability = QLabel("Disponível neste computador" if target_exists(tool) else "Caminho ainda não localizado")
        availability.setObjectName("available" if target_exists(tool) else "missing")
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


class WorkflowPanel(QFrame):
    def __init__(self, tools: list[ToolDefinition], launch):
        super().__init__()
        self.setObjectName("workflow")
        box = QVBoxLayout(self)
        caption = QLabel("FLUXO INTEGRADO — FGTS POLIGONAL")
        caption.setObjectName("eyebrow")
        box.addWidget(caption)
        title = QLabel("Um processo, duas ferramentas vinculadas")
        title.setObjectName("workflowTitle")
        box.addWidget(title)
        note = QLabel("Primeiro gere a planilha XLSX no Leitor PDF. Depois importe essa planilha no FGTS por Obra / Poligonal.")
        note.setWordWrap(True)
        note.setObjectName("description")
        box.addWidget(note)
        row = QHBoxLayout()
        ordered = sorted(tools, key=lambda item: item.step or 0)
        for index, tool in enumerate(ordered):
            step = QPushButton(f"{tool.step}  {tool.name}")
            step.setObjectName("workflowButton")
            step.clicked.connect(lambda checked=False, current=tool: launch(current))
            row.addWidget(step)
            if index < len(ordered) - 1:
                arrow = QLabel("→  XLSX  →")
                arrow.setObjectName("flowArrow")
                row.addWidget(arrow)
        box.addLayout(row)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tools = load_tools()
        self.category = "Início"
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
        version = QLabel("Versão 0.1.0")
        version.setObjectName("muted")
        layout.addWidget(version)
        return sidebar

    def _content(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(34, 28, 34, 24)
        heading = QLabel("DP - Ferramentas & Utilidades")
        heading.setObjectName("heading")
        layout.addWidget(heading)
        subtitle = QLabel("Sua central de automações do Departamento Pessoal")
        subtitle.setObjectName("description")
        layout.addWidget(subtitle)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Pesquisar ferramenta...")
        self.search.textChanged.connect(self.refresh_cards)
        layout.addWidget(self.search)
        workflow_tools = [tool for tool in self.tools if tool.workflow == "fgts-poligonal"]
        if workflow_tools:
            layout.addWidget(WorkflowPanel(workflow_tools, self.launch))
        self.section_title = QLabel("Todas as ferramentas")
        self.section_title.setObjectName("sectionTitle")
        layout.addWidget(self.section_title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.card_host = QWidget()
        self.grid = QGridLayout(self.card_host)
        self.grid.setSpacing(16)
        scroll.setWidget(self.card_host)
        layout.addWidget(scroll, 1)
        return page

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
        self.grid.setRowStretch((len(visible) + 2) // 3, 1)

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


STYLE = """
QWidget { background: #07111f; color: #e7eef7; font-family: 'Segoe UI'; font-size: 13px; }
#sidebar { background: #0b1728; border-right: 1px solid #193047; }
#brand { color: #07111f; background: #29d3c2; border-radius: 12px; font-size: 22px; font-weight: 800; padding: 9px; max-width: 30px; }
#brandName { font-size: 19px; font-weight: 700; margin-top: 7px; }
#heading { font-size: 28px; font-weight: 750; }
#sectionTitle, #workflowTitle { font-size: 18px; font-weight: 700; }
#description, #muted { color: #9db0c4; }
#eyebrow { color: #48e1d1; font-size: 11px; font-weight: 700; }
QLineEdit { background: #0d1c2e; border: 1px solid #213b54; border-radius: 9px; padding: 11px; margin: 10px 0; }
#toolCard { background: #0c192a; border: 1px solid #1d344c; border-radius: 12px; min-width: 235px; min-height: 210px; }
#workflow { background: #10273b; border: 1px solid #28bcae; border-radius: 12px; padding: 9px; margin: 8px 0 10px 0; }
#cardTitle { font-size: 15px; font-weight: 700; }
#toolIcon { color: #48e1d1; font-weight: 800; background: #123049; border-radius: 8px; padding: 7px; }
#status { color: #8ddbd3; background: #12352f; border-radius: 8px; padding: 4px 7px; font-size: 11px; }
#available { color: #6dd6a7; font-size: 11px; }
#missing { color: #f1b56b; font-size: 11px; }
#flowArrow { color: #48e1d1; font-weight: 700; }
QPushButton { background: #24bfae; color: #041315; border: 0; border-radius: 8px; padding: 9px 12px; font-weight: 650; }
QPushButton:hover { background: #48e1d1; }
#secondary, #nav { background: transparent; color: #c9d6e4; border: 1px solid #27435e; text-align: left; }
#nav { border: 0; padding: 10px; }
#nav:hover, #secondary:hover { background: #14283d; color: white; }
#workflowButton { background: #17384d; color: #e7eef7; border: 1px solid #2b6271; text-align: left; }
QScrollArea { background: transparent; }
"""


def main() -> int:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_FOLDER)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    return app.exec()
