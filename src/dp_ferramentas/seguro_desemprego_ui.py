from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .seguro_desemprego import (
    AnalysisResult,
    EmployeeFolderDiagnostic,
    ProcessingResult,
    analyze_pdfs,
    diagnose_employee_folders,
    process_analysis,
)


class PdfDropListWidget(QListWidget):
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setMinimumHeight(48)
        self.setMaximumHeight(64)
        self.setStyleSheet(
            """
            QListWidget {
                border: 1px dashed #4f6b84;
                border-radius: 8px;
                padding: 3px;
            }
            QListWidget::item {
                padding: 2px 4px;
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
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowSystemMenuHint
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )
        self.setSizeGripEnabled(True)
        self.setMinimumSize(680, 480)
        self.setModal(False)

        self.input_paths: list[Path] = []
        self.analysis: AnalysisResult | None = None
        self.processing: ProcessingResult | None = None
        self.folder_diagnostics: dict[str, EmployeeFolderDiagnostic] = {}
        self._screen_signal_connected = False
        self._first_show = True

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        outer_layout.addWidget(self.scroll)

        page = QWidget()
        self.scroll.setWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(7)

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
        input_actions.setSpacing(6)
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
        output_row.setSpacing(6)
        output_label = QLabel("Pasta de saída / relatórios:")
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Selecione a pasta onde os PDFs organizados serão gravados")
        choose_output = QPushButton("Escolher pasta")
        choose_output.setObjectName("secondary")
        choose_output.clicked.connect(self.select_output)
        output_row.addWidget(output_label)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(choose_output)
        layout.addLayout(output_row)

        destination_title = QLabel("Destino dos PDFs separados")
        destination_title.setObjectName("projectMetaKey")
        layout.addWidget(destination_title)

        self.create_folders_radio = QRadioButton(
            "Criar uma pasta para cada colaborador na pasta de saída"
        )
        self.create_folders_radio.setChecked(True)
        self.create_folders_radio.toggled.connect(self._destination_mode_changed)
        layout.addWidget(self.create_folders_radio)

        self.direct_distribution_radio = QRadioButton(
            "Distribuir diretamente nas pastas existentes da pasta principal das rescisões"
        )
        self.direct_distribution_radio.toggled.connect(self._destination_mode_changed)
        layout.addWidget(self.direct_distribution_radio)

        rescisao_row = QHBoxLayout()
        rescisao_row.setSpacing(6)
        rescisao_label = QLabel("Pasta principal:")
        self.rescisao_edit = QLineEdit()
        self.rescisao_edit.setPlaceholderText(
            "Selecione a pasta que contém as pastas individuais das rescisões"
        )
        self.rescisao_edit.setEnabled(False)
        self.rescisao_edit.textChanged.connect(self._rescisao_path_changed)

        self.rescisao_button = QPushButton("Escolher pasta")
        self.rescisao_button.setObjectName("secondary")
        self.rescisao_button.setEnabled(False)
        self.rescisao_button.clicked.connect(self.select_rescisao_root)

        self.diagnose_button = QPushButton("Diagnosticar pastas")
        self.diagnose_button.setObjectName("secondary")
        self.diagnose_button.setEnabled(False)
        self.diagnose_button.clicked.connect(self.run_folder_diagnostic)

        rescisao_row.addWidget(rescisao_label)
        rescisao_row.addWidget(self.rescisao_edit, 1)
        rescisao_row.addWidget(self.rescisao_button)
        rescisao_row.addWidget(self.diagnose_button)
        layout.addLayout(rescisao_row)

        matching_hint = QLabel(
            "No modo direto, a ferramenta apenas diagnostica primeiro: procura o nome exato e, "
            "se necessário, compara novamente ignorando DE, DA, DO, DAS e DOS. "
            "Nenhuma pasta é criada nesse modo."
        )
        matching_hint.setWordWrap(True)
        matching_hint.setObjectName("description")
        layout.addWidget(matching_hint)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
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
        self.progress.setMaximumHeight(20)
        layout.addWidget(self.progress)

        self.status = QLabel("Selecione ou arraste um ou mais PDFs emitidos pelo portal do MTE.")
        self.status.setObjectName("description")
        layout.addWidget(self.status)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Colaborador", "Requerimento", "SD", "CD", "Validação", "Pasta da rescisão"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setMinimumHeight(220)
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setMinimumHeight(30)
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
                padding: 5px 7px;
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
        notes_layout.setSpacing(3)

        notes_label = QLabel("Resultado / advertências")
        notes_label.setObjectName("projectMetaKey")
        notes_layout.addWidget(notes_label)

        self.notes = QTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setMinimumHeight(52)
        self.notes.setMaximumHeight(90)
        notes_layout.addWidget(self.notes)

        self.result_splitter = QSplitter(Qt.Vertical)
        self.result_splitter.setChildrenCollapsible(False)
        self.result_splitter.addWidget(table_host)
        self.result_splitter.addWidget(notes_host)
        self.result_splitter.setStretchFactor(0, 5)
        self.result_splitter.setStretchFactor(1, 1)
        self.result_splitter.setSizes([360, 72])
        layout.addWidget(self.result_splitter, 1)

        footer = QHBoxLayout()
        footer.setSpacing(6)
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

    def showEvent(self, event) -> None:
        super().showEvent(event)
        handle = self.windowHandle()
        if handle is not None and not self._screen_signal_connected:
            handle.screenChanged.connect(self._adapt_to_screen)
            self._screen_signal_connected = True
        if self._first_show:
            self._adapt_to_screen(self.screen())
            self._first_show = False

    def _adapt_to_screen(self, screen) -> None:
        if screen is None or self.isMaximized():
            return
        geometry = screen.availableGeometry()
        target_width = min(1180, max(760, int(geometry.width() * 0.90)))
        target_height = min(780, max(520, int(geometry.height() * 0.82)))
        target_width = min(target_width, max(640, geometry.width() - 30))
        target_height = min(target_height, max(460, geometry.height() - 40))
        self.resize(target_width, target_height)

        frame = self.frameGeometry()
        frame.moveCenter(geometry.center())
        self.move(frame.topLeft())

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
            "Selecione a pasta de saída / relatórios",
            current or "",
        )
        if folder:
            self.output_edit.setText(folder)

    def _destination_mode_changed(self) -> None:
        direct = self.direct_distribution_radio.isChecked()
        self.rescisao_edit.setEnabled(direct)
        self.rescisao_button.setEnabled(direct)
        self.diagnose_button.setEnabled(direct and self.analysis is not None)
        self.folder_diagnostics.clear()
        if self.analysis is not None:
            self._show_analysis()
            if direct and self.rescisao_edit.text().strip():
                self.run_folder_diagnostic(show_messages=False)
        self._update_process_button()

    def _rescisao_path_changed(self) -> None:
        self.folder_diagnostics.clear()
        if self.analysis is not None:
            self._refresh_folder_column()
        self._update_process_button()

    def select_rescisao_root(self) -> None:
        current = self.rescisao_edit.text().strip()
        folder = QFileDialog.getExistingDirectory(
            self,
            "Selecione a pasta principal das rescisões",
            current or "",
        )
        if folder:
            self.rescisao_edit.setText(folder)
            if self.analysis is not None:
                self.run_folder_diagnostic(show_messages=False)

    def _reset_analysis(self) -> None:
        self.analysis = None
        self.processing = None
        self.folder_diagnostics.clear()
        self.process_button.setEnabled(False)
        self.diagnose_button.setEnabled(False)
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
            self.diagnose_button.setEnabled(self.direct_distribution_radio.isChecked())
            self._show_analysis()
            if (
                self.direct_distribution_radio.isChecked()
                and self.rescisao_edit.text().strip()
            ):
                self.run_folder_diagnostic(show_messages=False)
        except Exception as exc:
            QMessageBox.warning(self, "Falha na análise", str(exc))
            self.status.setText("A análise não pôde ser concluída.")
        finally:
            self.analyze_button.setEnabled(True)

    def _folder_status_text(self, request_number: str) -> tuple[str, str]:
        if not self.direct_distribution_radio.isChecked():
            return "Será criada na pasta de saída", ""

        diagnostic = self.folder_diagnostics.get(request_number)
        if diagnostic is None:
            return "Aguardando diagnóstico", ""

        if diagnostic.status == "exact" and diagnostic.folder is not None:
            return f"OK — {diagnostic.folder.name} (exata)", diagnostic.detail
        if diagnostic.status == "relaxed" and diagnostic.folder is not None:
            return f"OK — {diagnostic.folder.name} (sem preposição)", diagnostic.detail
        if diagnostic.status == "missing":
            return "NÃO ENCONTRADA", diagnostic.detail
        if diagnostic.status == "invalid_root":
            return "PASTA PRINCIPAL INVÁLIDA", diagnostic.detail
        if diagnostic.status == "ambiguous":
            names = " | ".join(path.name for path in diagnostic.candidates[:3])
            if len(diagnostic.candidates) > 3:
                names += f" | +{len(diagnostic.candidates) - 3}"
            return f"AMBÍGUA — {names}", diagnostic.detail
        return "REVISAR", diagnostic.detail

    def _show_analysis(self) -> None:
        assert self.analysis is not None
        self.table.setRowCount(len(self.analysis.bundles))
        for row, bundle in enumerate(self.analysis.bundles):
            status = (
                "OK — pronto para gerar"
                if bundle.valid
                else "REVISAR — " + " ".join(bundle.issues)
            )
            folder_text, folder_tip = self._folder_status_text(bundle.request_number)
            values = [
                bundle.name or "Não identificado",
                bundle.request_number,
                str(len(bundle.sd_pages)),
                str(len(bundle.cd_pages)),
                status,
                folder_text,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (2, 3):
                    item.setTextAlignment(Qt.AlignCenter)
                if column == 5 and folder_tip:
                    item.setToolTip(folder_tip)
                self.table.setItem(row, column, item)

        self.table.resizeColumnsToContents()
        initial_widths = {
            0: 240,
            1: 125,
            2: 55,
            3: 55,
            4: 200,
            5: 330,
        }
        for column, preferred in initial_widths.items():
            content_width = self.table.columnWidth(column)
            self.table.setColumnWidth(column, min(content_width, preferred))

        valid = len(self.analysis.valid_bundles)
        invalid = len(self.analysis.bundles) - valid
        self.progress.setValue(100)
        self.status.setText(
            f"Análise concluída: {self.analysis.total_pages} página(s), "
            f"{valid} conjunto(s) válido(s), {invalid} para revisão."
        )
        self._render_analysis_notes()
        self._update_process_button()

    def _refresh_folder_column(self) -> None:
        if self.analysis is None:
            return
        for row, bundle in enumerate(self.analysis.bundles):
            text, tip = self._folder_status_text(bundle.request_number)
            item = self.table.item(row, 5)
            if item is None:
                item = QTableWidgetItem()
                self.table.setItem(row, 5, item)
            item.setText(text)
            item.setToolTip(tip)
        self._render_analysis_notes()

    def _render_analysis_notes(self) -> None:
        if self.analysis is None:
            self.notes.clear()
            return

        valid = len(self.analysis.valid_bundles)
        invalid = len(self.analysis.bundles) - valid
        issues = len(self.analysis.issues)
        note_lines = [
            f"Conjuntos válidos: {valid}",
            f"Conjuntos para revisão: {invalid}",
            f"Advertências/erros encontrados: {issues}",
        ]

        if self.direct_distribution_radio.isChecked():
            diagnostics = list(self.folder_diagnostics.values())
            safe = sum(1 for item in diagnostics if item.safe)
            pending = sum(1 for item in diagnostics if not item.safe)
            note_lines.extend(
                [
                    f"Pastas diagnosticadas com segurança: {safe}",
                    f"Pastas pendentes: {pending}",
                    "O diagnóstico não cria pastas nem grava PDFs.",
                ]
            )

        for issue in self.analysis.issues[:8]:
            location = issue.source.name if issue.source else ""
            if issue.page_number:
                location += f" (página {issue.page_number})"
            prefix = f"[{issue.severity}]"
            note_lines.append(f"{prefix} {location + ': ' if location else ''}{issue.message}")
        if issues > 8:
            note_lines.append(f"... e mais {issues - 8} ocorrência(s).")
        self.notes.setPlainText("\n".join(note_lines))

    def run_folder_diagnostic(self, show_messages: bool = True) -> bool:
        if self.analysis is None:
            if show_messages:
                QMessageBox.information(
                    self,
                    "Diagnóstico das pastas",
                    "Analise os documentos antes de diagnosticar as pastas.",
                )
            return False

        if not self.direct_distribution_radio.isChecked():
            return True

        root_text = self.rescisao_edit.text().strip()
        if not root_text:
            if show_messages:
                QMessageBox.information(
                    self,
                    "Diagnóstico das pastas",
                    "Selecione a pasta principal das rescisões.",
                )
            return False

        root = Path(root_text)
        if not root.exists() or not root.is_dir():
            if show_messages:
                QMessageBox.warning(
                    self,
                    "Diagnóstico das pastas",
                    "A pasta principal das rescisões não foi encontrada.",
                )
            self.folder_diagnostics.clear()
            self._refresh_folder_column()
            self._update_process_button()
            return False

        self.folder_diagnostics = diagnose_employee_folders(self.analysis, root)
        self._refresh_folder_column()
        self._update_process_button()

        safe = sum(1 for item in self.folder_diagnostics.values() if item.safe)
        pending = sum(1 for item in self.folder_diagnostics.values() if not item.safe)
        self.status.setText(
            f"Diagnóstico concluído: {safe} pasta(s) encontrada(s), "
            f"{pending} pendência(s). Nenhum PDF foi gravado."
        )

        if show_messages:
            if pending:
                QMessageBox.warning(
                    self,
                    "Diagnóstico concluído",
                    f"{safe} pasta(s) foram encontradas com segurança e "
                    f"{pending} precisam de revisão.\n\n"
                    "A geração direta permanece bloqueada até que todas as pastas "
                    "tenham uma correspondência única.",
                )
            else:
                QMessageBox.information(
                    self,
                    "Diagnóstico concluído",
                    f"Todas as {safe} pastas foram encontradas com segurança.\n\n"
                    "Nenhum PDF foi gravado durante o diagnóstico.",
                )
        return pending == 0

    def _can_generate(self) -> bool:
        if self.analysis is None or not self.analysis.valid_bundles:
            return False
        if not self.direct_distribution_radio.isChecked():
            return True
        expected = len(self.analysis.valid_bundles)
        if len(self.folder_diagnostics) != expected:
            return False
        return all(item.safe for item in self.folder_diagnostics.values())

    def _update_process_button(self) -> None:
        self.process_button.setEnabled(self._can_generate())

    def process(self) -> None:
        if not self.analysis:
            QMessageBox.information(self, "Seguro-Desemprego", "Execute a análise primeiro.")
            return

        output_text = self.output_edit.text().strip()
        if not output_text:
            QMessageBox.information(
                self,
                "Seguro-Desemprego",
                "Escolha a pasta de saída / relatórios.",
            )
            return

        direct_mode = self.direct_distribution_radio.isChecked()
        rescisao_root: Path | None = None
        if direct_mode:
            if not self.run_folder_diagnostic(show_messages=False):
                QMessageBox.warning(
                    self,
                    "Geração bloqueada",
                    "Existem pastas de colaboradores não encontradas ou ambíguas. "
                    "Revise a coluna 'Pasta da rescisão'. Nenhum PDF foi gravado.",
                )
                return
            rescisao_root = Path(self.rescisao_edit.text().strip())

        self.process_button.setEnabled(False)
        try:
            self.progress.setValue(0)
            self.processing = process_analysis(
                self.analysis,
                Path(output_text),
                self._progress,
                create_employee_folders=self.create_folders_radio.isChecked(),
                rescisao_root=rescisao_root,
            )
            self.progress.setValue(100)
            self.open_output_button.setEnabled(True)
            self.open_warnings_button.setEnabled(bool(self.processing.warnings_path))

            generated = len(self.processing.generated_files)
            not_distributed = len(self.processing.distribution_issues)
            self.status.setText(
                f"Concluído: {generated} PDF(s) gerado(s), "
                f"{not_distributed} não distribuído(s)."
            )

            lines = [
                f"Arquivos gerados: {generated}",
                f"Não distribuídos: {not_distributed}",
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
                f"{generated} PDF(s) foram gerados com sucesso.\n\n"
                "O arquivo original não foi alterado.",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Falha no processamento", str(exc))
            self.status.setText("Não foi possível concluir a geração dos PDFs.")
        finally:
            self._update_process_button()

    def open_output(self) -> None:
        if self.direct_distribution_radio.isChecked():
            direct = Path(self.rescisao_edit.text().strip())
            if direct.exists():
                os.startfile(direct)
                return
        folder = Path(self.output_edit.text().strip())
        if folder.exists():
            os.startfile(folder)

    def open_warnings(self) -> None:
        if (
            self.processing
            and self.processing.warnings_path
            and self.processing.warnings_path.exists()
        ):
            os.startfile(self.processing.warnings_path)
