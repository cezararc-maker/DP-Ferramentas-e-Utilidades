from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from pypdf import PdfReader, PdfWriter

DOC_SD = "SD"
DOC_CD = "CD"
ProgressCallback = Callable[[int, int, str], None]
_NAME_PREPOSITIONS = {"de", "da", "do", "das", "dos"}

_REQUEST_PATTERNS = (
    re.compile(
        r"Requerimento de Seguro-Desemprego\s*-\s*SD\s*[\r\n ]+(\d{8,14})",
        re.IGNORECASE,
    ),
    re.compile(
        r"Comunica(?:ção|cao) de Dispensa\s*-\s*CD\s*[\r\n ]+(\d{8,14})",
        re.IGNORECASE,
    ),
)
_NAME_PATTERN = re.compile(r"(?:^|\n)\s*2\s+([^\n]+?)\s*\n\s*NOME\b", re.IGNORECASE)
_CPF_PATTERN = re.compile(r"\b(\d{3}\.\d{3}\.\d{3}-\d{2})\b")
_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True, slots=True)
class PageRecord:
    source: Path
    page_index: int
    document_type: str
    request_number: str
    name: str
    cpf: str

    @property
    def page_number(self) -> int:
        return self.page_index + 1


@dataclass(frozen=True, slots=True)
class AnalysisIssue:
    severity: str
    message: str
    source: Path | None = None
    page_number: int | None = None
    request_number: str = ""


@dataclass(slots=True)
class DocumentBundle:
    request_number: str
    name: str = ""
    cpf: str = ""
    sd_pages: list[PageRecord] = field(default_factory=list)
    cd_pages: list[PageRecord] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.issues and len(self.sd_pages) == 1 and len(self.cd_pages) == 1


@dataclass(slots=True)
class AnalysisResult:
    bundles: list[DocumentBundle]
    issues: list[AnalysisIssue]
    total_pages: int

    @property
    def valid_bundles(self) -> list[DocumentBundle]:
        return [bundle for bundle in self.bundles if bundle.valid]


@dataclass(slots=True)
class ProcessingResult:
    generated_files: list[Path]
    log_path: Path
    warnings_path: Path | None
    distribution_issues: list[AnalysisIssue] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class EmployeeFolderDiagnostic:
    request_number: str
    employee_name: str
    status: str
    folder: Path | None
    detail: str
    candidates: tuple[Path, ...] = ()

    @property
    def safe(self) -> bool:
        return self.status in {"exact", "relaxed"} and self.folder is not None


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold()


def _clean_text(text: str) -> str:
    return text.replace("\r", "\n").replace("\xa0", " ").replace("\u200b", "")


def _normalize_name(value: str) -> str:
    return " ".join(value.split()).strip().upper()


def _normalize_cpf(value: str) -> str:
    return re.sub(r"\D", "", value)


def detect_document_type(text: str) -> str | None:
    plain = _plain(text)
    if "requerimento de seguro-desemprego - sd" in plain:
        return DOC_SD
    if "comunicacao de dispensa - cd" in plain:
        return DOC_CD
    return None


def extract_request_number(text: str) -> str:
    for pattern in _REQUEST_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return ""


def extract_name(text: str) -> str:
    match = _NAME_PATTERN.search(text)
    if match:
        return _normalize_name(match.group(1))
    return ""


def extract_cpf(text: str) -> str:
    match = _CPF_PATTERN.search(text)
    return match.group(1) if match else ""


def parse_page_text(text: str, source: Path, page_index: int) -> tuple[PageRecord | None, list[AnalysisIssue]]:
    text = _clean_text(text)
    document_type = detect_document_type(text)
    if not document_type:
        return None, [
            AnalysisIssue(
                "AVISO",
                "Página ignorada: não foi identificada como Requerimento SD nem Comunicação de Dispensa CD.",
                source,
                page_index + 1,
            )
        ]

    request_number = extract_request_number(text)
    name = extract_name(text)
    cpf = extract_cpf(text)
    issues: list[AnalysisIssue] = []

    if not request_number:
        issues.append(
            AnalysisIssue(
                "ERRO",
                "Número do requerimento não localizado.",
                source,
                page_index + 1,
            )
        )
    if not name:
        issues.append(
            AnalysisIssue("ERRO", "Nome do colaborador não localizado.", source, page_index + 1)
        )
    if not cpf:
        issues.append(AnalysisIssue("ERRO", "CPF não localizado.", source, page_index + 1))

    if issues:
        return None, issues

    return (
        PageRecord(
            source=source,
            page_index=page_index,
            document_type=document_type,
            request_number=request_number,
            name=name,
            cpf=cpf,
        ),
        [],
    )


def _bundle_records(records: list[PageRecord]) -> list[DocumentBundle]:
    by_request: dict[str, DocumentBundle] = {}
    for record in records:
        bundle = by_request.setdefault(
            record.request_number,
            DocumentBundle(request_number=record.request_number),
        )
        if record.document_type == DOC_SD:
            bundle.sd_pages.append(record)
        else:
            bundle.cd_pages.append(record)

    for bundle in by_request.values():
        all_pages = bundle.sd_pages + bundle.cd_pages
        if all_pages:
            bundle.name = all_pages[0].name
            bundle.cpf = all_pages[0].cpf

        if len(bundle.sd_pages) != 1:
            bundle.issues.append(
                f"Esperado 1 Requerimento SD; encontrado(s) {len(bundle.sd_pages)}."
            )
        if len(bundle.cd_pages) != 1:
            bundle.issues.append(
                f"Esperada 1 Comunicação de Dispensa CD; encontrada(s) {len(bundle.cd_pages)}."
            )

        names = {_plain(record.name) for record in all_pages}
        cpfs = {_normalize_cpf(record.cpf) for record in all_pages}
        if len(names) > 1:
            bundle.issues.append("Nome divergente entre as páginas do mesmo requerimento.")
        if len(cpfs) > 1:
            bundle.issues.append("CPF divergente entre as páginas do mesmo requerimento.")

    return sorted(by_request.values(), key=lambda item: (item.name, item.request_number))


def analyze_pdfs(
    paths: list[Path],
    progress: ProgressCallback | None = None,
) -> AnalysisResult:
    unique_paths = list(dict.fromkeys(Path(path).resolve() for path in paths))
    if not unique_paths:
        raise ValueError("Selecione pelo menos um arquivo PDF.")

    readers: list[tuple[Path, PdfReader]] = []
    issues: list[AnalysisIssue] = []
    total_pages = 0

    for path in unique_paths:
        if not path.exists():
            issues.append(AnalysisIssue("ERRO", "Arquivo não encontrado.", path))
            continue
        if path.suffix.casefold() != ".pdf":
            issues.append(AnalysisIssue("AVISO", "Arquivo ignorado por não ser PDF.", path))
            continue
        try:
            reader = PdfReader(str(path))
            if reader.is_encrypted:
                issues.append(
                    AnalysisIssue(
                        "ERRO",
                        "PDF protegido por senha. Remova a proteção antes de processar.",
                        path,
                    )
                )
                continue
            readers.append((path, reader))
            total_pages += len(reader.pages)
        except Exception as exc:
            issues.append(AnalysisIssue("ERRO", f"Falha ao abrir PDF: {exc}", path))

    records: list[PageRecord] = []
    current = 0
    for path, reader in readers:
        for page_index, page in enumerate(reader.pages):
            current += 1
            if progress:
                progress(current, max(total_pages, 1), f"Lendo {path.name} — página {page_index + 1}")
            try:
                text = page.extract_text() or ""
                record, page_issues = parse_page_text(text, path, page_index)
                issues.extend(page_issues)
                if record:
                    records.append(record)
            except Exception as exc:
                issues.append(
                    AnalysisIssue(
                        "ERRO",
                        f"Falha ao ler a página: {exc}",
                        path,
                        page_index + 1,
                    )
                )

    bundles = _bundle_records(records)
    for bundle in bundles:
        for message in bundle.issues:
            issues.append(
                AnalysisIssue(
                    "ERRO",
                    message,
                    request_number=bundle.request_number,
                )
            )

    return AnalysisResult(bundles=bundles, issues=issues, total_pages=total_pages)


def safe_employee_filename(name: str) -> str:
    value = _INVALID_FILENAME.sub("_", _normalize_name(name))
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value or "COLABORADOR"


def normalize_employee_folder_name(name: str, ignore_prepositions: bool = False) -> str:
    value = _plain(name)
    tokens = re.sub(r"[^a-z0-9]+", " ", value).split()
    if ignore_prepositions:
        tokens = [token for token in tokens if token not in _NAME_PREPOSITIONS]
    return " ".join(tokens)


def diagnose_employee_folder(
    root: Path,
    employee_name: str,
    request_number: str = "",
) -> EmployeeFolderDiagnostic:
    root = Path(root).resolve()
    if not root.exists() or not root.is_dir():
        return EmployeeFolderDiagnostic(
            request_number=request_number,
            employee_name=employee_name,
            status="invalid_root",
            folder=None,
            detail="A pasta principal das rescisões não existe ou não é uma pasta.",
        )

    folders = [item.resolve() for item in root.iterdir() if item.is_dir()]
    exact_key = normalize_employee_folder_name(employee_name)
    exact = tuple(
        folder
        for folder in folders
        if normalize_employee_folder_name(folder.name) == exact_key
    )
    if len(exact) == 1:
        return EmployeeFolderDiagnostic(
            request_number=request_number,
            employee_name=employee_name,
            status="exact",
            folder=exact[0],
            detail="Pasta encontrada por nome exato.",
            candidates=exact,
        )
    if len(exact) > 1:
        return EmployeeFolderDiagnostic(
            request_number=request_number,
            employee_name=employee_name,
            status="ambiguous",
            folder=None,
            detail="Há mais de uma pasta com correspondência exata para o colaborador.",
            candidates=exact,
        )

    relaxed_key = normalize_employee_folder_name(employee_name, ignore_prepositions=True)
    relaxed = tuple(
        folder
        for folder in folders
        if normalize_employee_folder_name(folder.name, ignore_prepositions=True) == relaxed_key
    )
    if len(relaxed) == 1:
        return EmployeeFolderDiagnostic(
            request_number=request_number,
            employee_name=employee_name,
            status="relaxed",
            folder=relaxed[0],
            detail="Pasta encontrada ignorando DE, DA, DO, DAS e DOS.",
            candidates=relaxed,
        )
    if len(relaxed) > 1:
        return EmployeeFolderDiagnostic(
            request_number=request_number,
            employee_name=employee_name,
            status="ambiguous",
            folder=None,
            detail=(
                "Há mais de uma pasta possível quando são ignoradas as preposições "
                "DE, DA, DO, DAS e DOS."
            ),
            candidates=relaxed,
        )

    return EmployeeFolderDiagnostic(
        request_number=request_number,
        employee_name=employee_name,
        status="missing",
        folder=None,
        detail="Nenhuma pasta correspondente ao nome do colaborador foi encontrada.",
    )


def diagnose_employee_folders(
    analysis: AnalysisResult,
    root: Path,
) -> dict[str, EmployeeFolderDiagnostic]:
    return {
        bundle.request_number: diagnose_employee_folder(
            root,
            bundle.name,
            bundle.request_number,
        )
        for bundle in analysis.valid_bundles
    }


def find_employee_folder(root: Path, employee_name: str) -> tuple[Path | None, str]:
    diagnostic = diagnose_employee_folder(root, employee_name)
    if diagnostic.safe:
        mode = (
            "nome exato"
            if diagnostic.status == "exact"
            else "nome equivalente ignorando de/da/do/das/dos"
        )
        return diagnostic.folder, mode
    return None, diagnostic.detail


def _unique_output_path(output_dir: Path, bundle: DocumentBundle) -> Path:
    base = output_dir / f"SD - {safe_employee_filename(bundle.name)}.pdf"
    if not base.exists():
        return base
    by_request = output_dir / (
        f"SD - {safe_employee_filename(bundle.name)} - {bundle.request_number}.pdf"
    )
    if not by_request.exists():
        return by_request
    counter = 2
    while True:
        candidate = output_dir / (
            f"SD - {safe_employee_filename(bundle.name)} - {bundle.request_number} ({counter}).pdf"
        )
        if not candidate.exists():
            return candidate
        counter += 1


def _issue_line(issue: AnalysisIssue) -> str:
    location = ""
    if issue.source:
        location = issue.source.name
        if issue.page_number:
            location += f" | página {issue.page_number}"
    if issue.request_number:
        location = f"{location} | " if location else ""
        location += f"requerimento {issue.request_number}"
    prefix = f"[{issue.severity}]"
    return f"{prefix} {location + ' | ' if location else ''}{issue.message}"


def process_analysis(
    analysis: AnalysisResult,
    output_dir: Path,
    progress: ProgressCallback | None = None,
    create_employee_folders: bool = True,
    rescisao_root: Path | None = None,
) -> ProcessingResult:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    valid = analysis.valid_bundles
    if not valid:
        raise ValueError("Nenhum conjunto válido (1 SD + 1 CD) foi encontrado para gerar.")

    direct_root = Path(rescisao_root).resolve() if rescisao_root else None
    if direct_root is not None and (not direct_root.exists() or not direct_root.is_dir()):
        raise ValueError("A pasta principal das rescisões não existe ou não é uma pasta.")

    direct_diagnostics: dict[str, EmployeeFolderDiagnostic] = {}
    distribution_issues: list[AnalysisIssue] = []
    if direct_root is not None:
        direct_diagnostics = diagnose_employee_folders(analysis, direct_root)
        unsafe = [item for item in direct_diagnostics.values() if not item.safe]
        if unsafe:
            details = "; ".join(
                f"{item.employee_name}: {item.detail}"
                for item in unsafe[:5]
            )
            if len(unsafe) > 5:
                details += f"; e mais {len(unsafe) - 5} pendência(s)"
            raise ValueError(
                "Diagnóstico das pastas de rescisão possui pendências. "
                "Nenhum PDF foi gravado nas pastas originais. "
                + details
            )

    readers: dict[Path, PdfReader] = {}
    generated: list[Path] = []

    for index, bundle in enumerate(valid, start=1):
        if progress:
            progress(index, len(valid), f"Preparando {bundle.name}")

        target_dir = output_dir
        if direct_root is not None:
            target_dir = direct_diagnostics[bundle.request_number].folder
            if target_dir is None:
                raise RuntimeError(
                    "Diagnóstico inconsistente: pasta de destino não disponível."
                )
        elif create_employee_folders:
            target_dir = output_dir / safe_employee_filename(bundle.name)
            target_dir.mkdir(parents=True, exist_ok=True)

        writer = PdfWriter()
        for record in (bundle.sd_pages[0], bundle.cd_pages[0]):
            reader = readers.get(record.source)
            if reader is None:
                reader = PdfReader(str(record.source))
                readers[record.source] = reader
            writer.add_page(reader.pages[record.page_index])

        target = _unique_output_path(target_dir, bundle)
        with target.open("wb") as handle:
            writer.write(handle)
        generated.append(target)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = output_dir / f"processamento_sd_{stamp}.txt"
    all_issues = [*analysis.issues, *distribution_issues]
    destination_mode = (
        f"Distribuição direta em pastas existentes: {direct_root}"
        if direct_root is not None
        else (
            "Uma pasta por colaborador"
            if create_employee_folders
            else "Arquivos diretamente na pasta de saída"
        )
    )
    lines = [
        "DP - Ferramentas & Utilidades",
        "Organizador de Seguro-Desemprego",
        "=" * 52,
        f"Executado em: {datetime.now().isoformat(timespec='seconds')}",
        f"Modo de destino: {destination_mode}",
        f"Páginas analisadas: {analysis.total_pages}",
        f"Conjuntos identificados: {len(analysis.bundles)}",
        f"Conjuntos válidos gerados: {len(generated)}",
        f"Não distribuídos: {len(distribution_issues)}",
        f"Advertências/erros: {len(all_issues)}",
        "",
        "Arquivos gerados:",
    ]
    lines.extend(f"- {path}" for path in generated)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    warnings_path: Path | None = None
    if all_issues:
        warnings_path = output_dir / f"advertencias_sd_{stamp}.txt"
        warning_lines = [
            "ADVERTÊNCIAS - ORGANIZADOR DE SEGURO-DESEMPREGO",
            "=" * 52,
            "Nenhum CPF é gravado neste relatório.",
            "",
        ]
        warning_lines.extend(_issue_line(issue) for issue in all_issues)
        warnings_path.write_text("\n".join(warning_lines) + "\n", encoding="utf-8")

    return ProcessingResult(
        generated_files=generated,
        log_path=log_path,
        warnings_path=warnings_path,
        distribution_issues=distribution_issues,
    )
