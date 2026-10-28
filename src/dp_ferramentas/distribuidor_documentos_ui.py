from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .distribuidor_documentos import (
    SUPPORTED_SUFFIXES,
    DistributionAnalysis,
    analyze_distribution,
    move_distribution,
)


class FileDropList(QListWidget):
    files_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setMinimumHeight(120)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.isLocalFile()
            and Path(url.toLocalFile()).suffix.lower() in SUPPORTED_SUFFIXES
        ]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class DistribuidorDocumentosWindow(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.paths: list[Path] = []
        self.employee_root: Path | None = None
        self.analysis: DistributionAnalysis | None = None

        self.setWindowTitle("Distribuir documentos nas pastas de rescisão")
        self.resize(1280, 760)
        self.setMinimumSize(980, 640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("Extratos FGTS e consultas do Consignado")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(
            QLabel(
                "Arraste PDFs e CSVs. O programa identifica o colaborador e mostra "
                "todos os destinos antes de mover qualquer arquivo."
            )
        )

        self.file_list = FileDropList()
        self.file_list.files_dropped.connect(self.add_paths)
        layout.addWidget(self.file_list)

        file_buttons = QHBoxLayout()
        add_button = QPushButton("Adicionar arquivos")
        add_button.clicked.connect(self.choose_files)
        file_buttons.addWidget(add_button)
        remove_button = QPushButton("Remover selecionados")
        remove_button.clicked.connect(self.remove_selected)
        file_buttons.addWidget(remove_button)
        clear_button = QPushButton("Limpar")
        clear_button.clicked.connect(self.clear_files)
        file_buttons.addWidget(clear_button)
        file_buttons.addStretch()
        layout.addLayout(file_buttons)

        folder_row = QHBoxLayout()
        self.folder_label = QLabel("Pasta principal das rescisões: não selecionada")
        self.folder_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        folder_row.addWidget(self.folder_label, 1)
        folder_button = QPushButton("Escolher pasta")
        folder_button.clicked.connect(self.choose_folder)
        folder_row.addWidget(folder_button)
        layout.addLayout(folder_row)

        column_help = QLabel(
            "<b>Arquivo de origem:</b> documento que será movido &nbsp;|&nbsp; "
            "<b>Tipo identificado:</b> classificação encontrada &nbsp;|&nbsp; "
            "<b>Colaborador identificado:</b> nome lido no documento &nbsp;|&nbsp; "
            "<b>Destino completo:</b> pasta e nome final do arquivo"
        )
        column_help.setWordWrap(True)
        layout.addWidget(column_help)

        self.table = QTableWidget(0, 5)
        headers = [
            ("Arquivo de origem", "Nome do arquivo selecionado que será movido."),
            ("Tipo identificado", "Tipo de documento reconhecido pelo programa."),
            (
                "Colaborador identificado",
                "Nome completo do colaborador lido no conteúdo ou no nome do arquivo.",
            ),
            (
                "Destino completo",
                "Caminho completo, incluindo a pasta do colaborador e o nome final do arquivo.",
            ),
            ("Resultado da análise", "Informa se o destino está pronto ou qual correção é necessária."),
        ]
        self.table.setHorizontalHeaderLabels([title for title, _ in headers])
        for column, (_, description) in enumerate(headers):
            self.table.horizontalHeaderItem(column).setToolTip(description)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 270)
        self.table.setColumnWidth(1, 190)
        self.table.setColumnWidth(2, 260)
        self.table.setColumnWidth(3, 430)
        layout.addWidget(self.table, 1)

        self.status_label = QLabel("Adicione os arquivos e escolha a pasta principal.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        actions = QHBoxLayout()
        self.analyze_button = QPushButton("Analisar destinos")
        self.analyze_button.clicked.connect(self.analyze)
        actions.addWidget(self.analyze_button)
        self.move_button = QPushButton("Mover arquivos")
        self.move_button.clicked.connect(self.move_files)
        self.move_button.setEnabled(False)
        actions.addWidget(self.move_button)
        actions.addStretch()
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.close)
        actions.addWidget(close_button)
        layout.addLayout(actions)

    def choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar documentos",
            "",
            "Documentos (*.pdf *.csv);;PDF (*.pdf);;CSV (*.csv)",
        )
        self.add_paths([Path(file) for file in files])

    def add_paths(self, paths: list[Path]) -> None:
        existing = {path.resolve() for path in self.paths}
        for path in paths:
            resolved = Path(path).resolve()
            if (
                resolved.is_file()
                and resolved.suffix.lower() in SUPPORTED_SUFFIXES
                and resolved not in existing
            ):
                self.paths.append(resolved)
                existing.add(resolved)
        self._refresh_file_list()
        self._invalidate_analysis()

    def _refresh_file_list(self) -> None:
        self.file_list.clear()
        self.file_list.addItems([str(path) for path in self.paths])

    def remove_selected(self) -> None:
        rows = sorted({index.row() for index in self.file_list.selectedIndexes()}, reverse=True)
        for row in rows:
            self.paths.pop(row)
        self._refresh_file_list()
        self._invalidate_analysis()

    def clear_files(self) -> None:
        self.paths.clear()
        self._refresh_file_list()
        self._invalidate_analysis()

    def choose_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Pasta principal das rescisões")
        if selected:
            self.employee_root = Path(selected).resolve()
            self.folder_label.setText(
                f"Pasta principal das rescisões: {self.employee_root}"
            )
            self._invalidate_analysis()

    def _invalidate_analysis(self) -> None:
        self.analysis = None
        self.table.setRowCount(0)
        self.move_button.setEnabled(False)
        self.status_label.setText("Clique em “Analisar destinos” antes de mover.")

    def analyze(self) -> None:
        if not self.paths:
            QMessageBox.information(self, "Analisar", "Adicione pelo menos um PDF ou CSV.")
            return
        if self.employee_root is None:
            QMessageBox.information(self, "Analisar", "Escolha a pasta principal das rescisões.")
            return

        self.analysis = analyze_distribution(self.paths, self.employee_root)
        self.table.setRowCount(len(self.analysis.items))
        problems = 0
        for row, item in enumerate(self.analysis.items):
            destination = str(item.destination) if item.destination else ""
            status = "Pronto" if item.ready else item.error
            if not item.ready:
                problems += 1
            values = [
                item.source.name,
                item.document_type,
                item.employee_name,
                destination,
                status,
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value or item.error)
                self.table.setItem(row, column, cell)

        self.move_button.setEnabled(self.analysis.ready)
        if self.analysis.ready:
            self.status_label.setText(
                f"{len(self.analysis.items)} arquivo(s) identificado(s). "
                "Todos os destinos estão prontos para revisão."
            )
        else:
            self.status_label.setText(
                f"{problems} arquivo(s) precisam de correção. "
                "Nenhum arquivo será movido enquanto houver pendências."
            )

    def move_files(self) -> None:
        if not self.analysis or not self.analysis.ready:
            QMessageBox.warning(self, "Mover arquivos", "Analise e corrija os destinos primeiro.")
            return
        total = len(self.analysis.items)
        if (
            QMessageBox.question(
                self,
                "Confirmar movimentação",
                f"Mover {total} arquivo(s) para as pastas exibidas?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return
        try:
            moved = move_distribution(self.analysis)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Falha ao mover", str(exc))
            return

        QMessageBox.information(
            self,
            "Movimentação concluída",
            f"{len(moved)} arquivo(s) movido(s) com sucesso.",
        )
        self.paths.clear()
        self._refresh_file_list()
        self.analysis = None
        self.table.setRowCount(0)
        self.move_button.setEnabled(False)
        self.status_label.setText("Movimentação concluída com sucesso.")
