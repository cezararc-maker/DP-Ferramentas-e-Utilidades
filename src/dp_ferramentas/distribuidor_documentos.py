from __future__ import annotations

import csv
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from .seguro_desemprego import EmployeeFolderDiagnostic, diagnose_employee_folder

SUPPORTED_SUFFIXES = {".pdf", ".csv"}
_CPF = r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}"
_NAME = r"[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ][A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ ]{2,}"


@dataclass
class DistributionItem:
    source: Path
    document_type: str = ""
    employee_name: str = ""
    diagnostic: EmployeeFolderDiagnostic | None = None
    destination: Path | None = None
    error: str = ""

    @property
    def ready(self) -> bool:
        return not self.error and self.destination is not None


@dataclass
class DistributionAnalysis:
    items: list[DistributionItem] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return bool(self.items) and all(item.ready for item in self.items)


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).upper()


def _clean_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" -_;,.")
    return value.upper()


def _pdf_text(path: Path) -> str:
    return "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)


def _extract_fgts_name(text: str) -> str:
    match = re.search(
        r"\bNome\s*:\s*(.+?)(?=\s+(?:PIS|PASEP|NIT)\s*[:\-])",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    return _clean_name(match.group(1)) if match else ""


def _extract_consignado_pdf_name(text: str) -> str:
    upper = _plain(text)
    for pattern in (
        rf"(?:CPF\s*)?{_CPF}\s*\n\s*({_NAME})\s*\n",
        rf"(?:CPF\s*)?{_CPF}\s+({_NAME})(?=\s+(?:MATR[IÍ]CULA|\d{{3,}}))",
    ):
        match = re.search(pattern, upper, re.MULTILINE)
        if match:
            return _clean_name(match.group(1))
    return ""


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as stream:
                sample = stream.read(4096)
                stream.seek(0)
                dialect = csv.Sniffer().sniff(sample, delimiters=";,")
                return list(csv.DictReader(stream, dialect=dialect))
        except (UnicodeDecodeError, csv.Error):
            continue
    return []


def _extract_consignado_csv_name(path: Path) -> str:
    names: set[str] = set()
    for row in _read_csv_rows(path):
        for key, value in row.items():
            normalized_key = re.sub(r"[^a-z]", "", _plain(key or "").lower())
            if normalized_key in {"nometrabalhador", "nomecolaborador", "nome"} and value:
                names.add(_clean_name(value))
    return names.pop() if len(names) == 1 else ""


def _name_from_filename(path: Path) -> str:
    stem = path.stem
    patterns = (
        r"^Consulta\s+Consignado\s*-\s*(.+)$",
        r"^(.+?)\s*-\s*Extrato\s+FGTS(?:\s+BASE\s+\w+)?$",
    )
    for pattern in patterns:
        match = re.match(pattern, stem, re.IGNORECASE)
        if match:
            return _clean_name(match.group(1))
    return ""


def analyze_file(path: Path) -> DistributionItem:
    source = Path(path).resolve()
    item = DistributionItem(source=source)
    if not source.is_file():
        item.error = "Arquivo não encontrado."
        return item
    if source.suffix.lower() not in SUPPORTED_SUFFIXES:
        item.error = "Formato não aceito. Use PDF ou CSV."
        return item
    try:
        if source.suffix.lower() == ".csv":
            item.document_type = "Consulta Consignado (CSV)"
            item.employee_name = _extract_consignado_csv_name(source)
        else:
            text = _pdf_text(source)
            plain = _plain(text)
            if "EXTRATO DE CONTA DO FUNDO DE GARANTIA" in plain:
                item.document_type = "Extrato FGTS"
                item.employee_name = _extract_fgts_name(text)
            elif (
                "CONSULTAR GARANTIAS DE VERBAS RESCISORIAS" in plain
                or "RESULTADO DA CONSULTA" in plain
            ):
                item.document_type = "Consulta Consignado (PDF)"
                item.employee_name = _extract_consignado_pdf_name(text)
            else:
                item.error = "Tipo de documento não reconhecido."
                return item
        if not item.employee_name:
            item.employee_name = _name_from_filename(source)
        if not item.employee_name:
            item.error = "Nome do colaborador não identificado."
    except Exception as exc:  # noqa: BLE001
        item.error = f"Falha ao ler o arquivo: {exc}"
    return item


def _unique_destination(folder: Path, filename: str, reserved: set[Path]) -> Path:
    candidate = folder / filename
    counter = 2
    while candidate.exists() or candidate in reserved:
        candidate = folder / f"{Path(filename).stem} ({counter}){Path(filename).suffix}"
        counter += 1
    return candidate


def analyze_distribution(paths: list[Path], employee_root: Path) -> DistributionAnalysis:
    root = Path(employee_root).resolve()
    reserved: set[Path] = set()
    items: list[DistributionItem] = []
    for path in paths:
        item = analyze_file(path)
        if not item.error:
            item.diagnostic = diagnose_employee_folder(root, item.employee_name)
            if item.diagnostic.safe and item.diagnostic.folder:
                item.destination = _unique_destination(
                    item.diagnostic.folder, item.source.name, reserved
                )
                reserved.add(item.destination)
            else:
                item.error = item.diagnostic.detail
        items.append(item)
    return DistributionAnalysis(items)


def move_distribution(analysis: DistributionAnalysis) -> list[Path]:
    if not analysis.ready:
        raise ValueError("Existem arquivos sem destino seguro. Revise o diagnóstico.")
    moved: list[tuple[Path, Path]] = []
    try:
        for item in analysis.items:
            assert item.destination is not None
            item.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item.source), str(item.destination))
            moved.append((item.source, item.destination))
        return [destination for _, destination in moved]
    except Exception:
        for source, destination in reversed(moved):
            if destination.exists() and not source.exists():
                shutil.move(str(destination), str(source))
        raise
