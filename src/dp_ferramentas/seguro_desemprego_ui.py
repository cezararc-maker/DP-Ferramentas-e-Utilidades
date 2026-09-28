from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .seguro_desemprego import AnalysisResult, ProcessingResult, analyze_pdfs, process_analysis


class PdfDropListWidget(QListWidget):
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setMinimumHeight(62)
        self.setMaximumHeight(76)
        self.setStyleSheet(
            """
            QListWidget {
                border: 1px dashed #4f6b84;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 3px 5px;
            }
            """
        )

    @staticmethod
    def _extract_pdf_paths(mime_data) -> list[str]:
        if not mime_data.hasUrls():
            return []

        paths: list[str] = []
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.casefold() == ".pdf":
                paths.append(str(path))
        return paths

    def dragEnterEvent(self, event) -> None:
        if self._extract_pdf_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self._extract_pdf_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        paths = self._extract_pdf_paths(event.mimeData())
        if not paths:
            event.ignore()
            return
        self.files_dropped.emit(paths)
        event.acceptProposedAction()


class SeguroDesempregoWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seguro-Desemprego — Organizar SD/CD")
        self.resize(1080, 760)
        self.setModal(False)

        self.input_paths: list[Path] = []
        self.analysis: AnalysisResult | None = None
        self.processing: ProcessingResult | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        title = QLabel("Organizador de Requerimento de Seguro-Desemprego")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        intro = QLabel(
            "Processamento 100% local. O PDF original não é alterado. "
            "A ferramenta identifica SD e CD pelo número do requerimento e valida nome e CPF "
            "antes de gerar um PDF por colaborador."
        )
        intro.setWordWrap(True)
        intro.setObjectName("description")
        layout.addWidget(intro)

        input_actions = QHBoxLayout()
        add = QPushButton("Adicionar PDF(s)")
        add.clicked.connect(self.select_files)
        clear = QPushButton("Limpar seleção")
        clear.setObjectName("secondary")
        clear.clicked.connect(self.clear_files)
        input_actions.addWidget(add)
        input_actions.addWidget(clear)
        input_actions.addStretch()
        layout.addLayout(input_actions)

        drop_hint = QLabel(
            "Arquivos selecionados — você também pode arrastar e soltar um ou mais PDFs aqui."
        )
        drop_hint.setObjectName("description")
        layout.addWidget(drop_hint)

        self.file_list = PdfDropListWidget()
        self.file_list.files_dropped.connect(self.add_dropped_files)
        layout.addWidget(self.file_list)

        output_row = QHBoxLayout()
        output_label = QLabel("Pasta de saída:")
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Selecione a pasta onde os PDFs organizados serão gravados")
        choose_output = QPushButton("Escolher pasta")
        choose_output.setObjectName("secondary")
        choose_output.clicked.connect(self.select_output)
        output_row.addWidget(output_label)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(choose_output)
        layout.addLayout(output_row)

        action_row = QHBoxLayout()
        self.analyze_button = QPushButton("1. Analisar documentos")
        self.analyze_button.clicked.connect(self.analyze)
        self.process_button = QPushButton("2. Gerar PDFs por colaborador")
        self.process_button.clicked.connect(self.process)
        self.process_button.setEnabled(False)
        action_row.addWidget(self.analyze_button)
        action_row.addWidget(self.process_button)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setMaximumHeight(24)
        layout.addWidget(self.progress)

        self.status = QLabel("Selecione ou arraste um ou mais PDFs emitidos pelo portal do MTE.")
        self.status.setObjectName("description")
        layout.addWidget(self.status)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Colaborador", "Requerimento", "SD", "CD", "Validação"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setMinimumHeight(260)
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setMinimumHeight(32)
        header.setMinimumSectionSize(48)
        header.setStretchLastSection(False)
        for column in range(self.table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.Interactive)
        header.setStyleSheet(
            """
            QHeaderView::section {
                background-color: #edf1f5;
                color: #000000;
                font-weight: 700;
                padding: 6px 8px;
                border: 1px solid #c4ccd4;
            }
            """
        )

        table_host = QWidget()
        table_layout = QVBoxLayout(table_host)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)
        table_layout.addWidget(self.table)

        notes_host = QWidget()
        notes_layout = QVBoxLayout(notes_host)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        notes_layout.setSpacing(4)

        notes_label = QLabel("Resultado / advertências")
        notes_label.setObjectName("projectMetaKey")
        notes_layout.addWidget(notes_label)

        self.notes = QTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setMinimumHeight(58)
        self.notes.setMaximumHeight(95)
        notes_layout.addWidget(self.notes)

        self.result_splitter = QSplitter(Qt.Vertical)
        self.result_splitter.setChildrenCollapsible(False)
        self.result_splitter.addWidget(table_host)
        self.result_splitter.addWidget(notes_host)
        self.result_splitter.setStretchFactor(0, 5)
        self.result_splitter.setStretchFactor(1, 1)
        self.result_splitter.setSizes([430, 82])
        layout.addWidget(self.result_splitter, 1)

        footer = QHBoxLayout()
        self.open_output_button = QPushButton("Abrir pasta de resultado")
        self.open_output_button.setObjectName("secondary")
        self.open_output_button.setEnabled(False)
        self.open_output_button.clicked.connect(self.open_output)
        self.open_warnings_button = QPushButton("Abrir advertências")
        self.open_warnings_button.setObjectName("secondary")
        self.open_warnings_button.setEnabled(False)
        self.open_warnings_button.clicked.connect(self.open_warnings)
        close = QPushButton("Fechar")
        close.setObjectName("secondary")
        close.clicked.connect(self.close)
        footer.addWidget(self.open_output_button)
        footer.addWidget(self.open_warnings_button)
        footer.addStretch()
        footer.addWidget(close)
        layout.addLayout(footer)

    def _add_files(self, raw_paths: list[str]) -> int:
        known = {path.resolve() for path in self.input_paths}
        added = 0
        for raw in raw_paths:
            path = Path(raw).resolve()
            if not path.is_file() or path.suffix.casefold() != ".pdf" or path in known:
                continue
            self.input_paths.append(path)
            known.add(path)
            added += 1

        if added:
            self._refresh_files()
            if self.input_paths and not self.output_edit.text().strip():
                default = self.input_paths[0].parent / "Seguro-Desemprego Organizado"
                self.output_edit.setText(str(default))
            self._reset_analysis()
            self.status.setText(
                f"{len(self.input_paths)} PDF(s) selecionado(s). Pronto para analisar."
            )
        return added

    def select_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecione os PDFs do Seguro-Desemprego",
            "",
            "Arquivos PDF (*.pdf)",
        )
        if files:
            self._add_files(files)

    def add_dropped_files(self, files: list[str]) -> None:
        added = self._add_files(files)
        if not added:
            self.status.setText(
                "Nenhum PDF novo foi adicionado. Arquivos duplicados ou não-PDF foram ignorados."
            )

    def clear_files(self) -> None:
        self.input_paths.clear()
        self.file_list.clear()
        self._reset_analysis()
        self.status.setText("Selecione ou arraste um ou mais PDFs emitidos pelo portal do MTE.")

    def _refresh_files(self) -> None:
        self.file_list.clear()
        for path in self.input_paths:
            self.file_list.addItem(str(path))

    def select_output(self) -> None:
        current = self.output_edit.text().strip()
        folder = QFileDialog.getExistingDirectory(
            self,
            "Selecione a pasta de saída",
            current or "",
        )
        if folder:
            self.output_edit.setText(folder)

    def _reset_analysis(self) -> None:
        self.analysis = None
        self.processing = None
        self.process_button.setEnabled(False)
        self.open_output_button.setEnabled(False)
        self.open_warnings_button.setEnabled(False)
        self.table.setRowCount(0)
        self.notes.clear()
        self.progress.setValue(0)

    def _progress(self, current: int, total: int, detail: str) -> None:
        total = max(total, 1)
        self.progress.setValue(int(current * 100 / total))
        self.status.setText(detail)
        QApplication.processEvents()

    def analyze(self) -> None:
        if not self.input_paths:
            QMessageBox.information(self, "Seguro-Desemprego", "Selecione pelo menos um PDF.")
            return

        self._reset_analysis()
        self.analyze_button.setEnabled(False)
        try:
            self.analysis = analyze_pdfs(self.input_paths, self._progress)
            self._show_analysis()
        except Exception as exc:
            QMessageBox.warning(self, "Falha na análise", str(exc))
            self.status.setText("A análise não pôde ser concluída.")
        finally:
            self.analyze_button.setEnabled(True)

    def _show_analysis(self) -> None:
        assert self.analysis is not None
        self.table.setRowCount(len(self.analysis.bundles))
        for row, bundle in enumerate(self.analysis.bundles):
            status = (
                "OK — pronto para gerar"
                if bundle.valid
                else "REVISAR — " + " ".join(bundle.issues)
            )
            values = [
                bundle.name or "Não identificado",
                bundle.request_number,
                str(len(bundle.sd_pages)),
                str(len(bundle.cd_pages)),
                status,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (2, 3):
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, column, item)

        self.table.resizeColumnsToContents()
        initial_widths = {
            0: 260,
            1: 125,
            2: 55,
            3: 55,
            4: 210,
        }
        for column, preferred in initial_widths.items():
            content_width = self.table.columnWidth(column)
            self.table.setColumnWidth(column, min(content_width, preferred))

        valid = len(self.analysis.valid_bundles)
        invalid = len(self.analysis.bundles) - valid
        issues = len(self.analysis.issues)
        self.process_button.setEnabled(valid > 0)
        self.progress.setValue(100)
        self.status.setText(
            f"Análise concluída: {self.analysis.total_pages} página(s), "
            f"{valid} conjunto(s) válido(s), {invalid} para revisão."
        )

        note_lines = [
            f"Conjuntos válidos: {valid}",
            f"Conjuntos para revisão: {invalid}",
            f"Advertências/erros encontrados: {issues}",
        ]
        for issue in self.analysis.issues[:12]:
            location = issue.source.name if issue.source else ""
            if issue.page_number:
                location += f" (página {issue.page_number})"
            prefix = f"[{issue.severity}]"
            note_lines.append(f"{prefix} {location + ': ' if location else ''}{issue.message}")
        if issues > 12:
            note_lines.append(f"... e mais {issues - 12} ocorrência(s).")
        self.notes.setPlainText("\n".join(note_lines))

    def process(self) -> None:
        if not self.analysis:
            QMessageBox.information(self, "Seguro-Desemprego", "Execute a análise primeiro.")
            return
        output_text = self.output_edit.text().strip()
        if not output_text:
            QMessageBox.information(self, "Seguro-Desemprego", "Escolha a pasta de saída.")
            return

        self.process_button.setEnabled(False)
        try:
            self.progress.setValue(0)
            self.processing = process_analysis(
                self.analysis,
                Path(output_text),
                self._progress,
            )
            self.progress.setValue(100)
            self.open_output_button.setEnabled(True)
            self.open_warnings_button.setEnabled(bool(self.processing.warnings_path))
            self.status.setText(
                f"Concluído: {len(self.processing.generated_files)} PDF(s) gerado(s)."
            )
            lines = [
                f"Arquivos gerados: {len(self.processing.generated_files)}",
                f"Log: {self.processing.log_path.name}",
            ]
            if self.processing.warnings_path:
                lines.append(f"Advertências: {self.processing.warnings_path.name}")
            else:
                lines.append("Nenhuma advertência registrada.")
            self.notes.setPlainText("\n".join(lines))
            QMessageBox.information(
                self,
                "Processamento concluído",
                f"{len(self.processing.generated_files)} PDF(s) foram gerados com sucesso.\n\n"
                "O arquivo original não foi alterado.",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Falha no processamento", str(exc))
            self.status.setText("Não foi possível concluir a geração dos PDFs.")
        finally:
            self.process_button.setEnabled(bool(self.analysis.valid_bundles))

    def open_output(self) -> None:
        folder = Path(self.output_edit.text().strip())
        if folder.exists():
            os.startfile(folder)

    def open_warnings(self) -> None:
        if self.processing and self.processing.warnings_path and self.processing.warnings_path.exists():
            os.startfile(self.processing.warnings_path)
