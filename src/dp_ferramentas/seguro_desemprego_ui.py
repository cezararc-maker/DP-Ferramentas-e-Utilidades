from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from .seguro_desemprego import AnalysisResult, ProcessingResult, analyze_pdfs, process_analysis


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
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

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

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(120)
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
        layout.addWidget(self.progress)

        self.status = QLabel("Selecione um ou mais PDFs emitidos pelo portal do MTE.")
        self.status.setObjectName("description")
        layout.addWidget(self.status)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Colaborador", "Requerimento", "SD", "CD", "Validação"]
        )
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in (1, 2, 3, 4):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 1)

        notes_label = QLabel("Resultado / advertências")
        notes_label.setObjectName("projectMetaKey")
        layout.addWidget(notes_label)
        self.notes = QTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setMaximumHeight(120)
        layout.addWidget(self.notes)

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

    def select_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecione os PDFs do Seguro-Desemprego",
            "",
            "Arquivos PDF (*.pdf)",
        )
        if not files:
            return
        known = {path.resolve() for path in self.input_paths}
        for raw in files:
            path = Path(raw).resolve()
            if path not in known:
                self.input_paths.append(path)
                known.add(path)
        self._refresh_files()
        if self.input_paths and not self.output_edit.text().strip():
            default = self.input_paths[0].parent / "Seguro-Desemprego Organizado"
            self.output_edit.setText(str(default))
        self._reset_analysis()

    def clear_files(self) -> None:
        self.input_paths.clear()
        self.file_list.clear()
        self._reset_analysis()
        self.status.setText("Selecione um ou mais PDFs emitidos pelo portal do MTE.")

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
            status = "OK — pronto para gerar" if bundle.valid else "REVISAR — " + " ".join(bundle.issues)
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
