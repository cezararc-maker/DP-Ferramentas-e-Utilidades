from pathlib import Path

from pypdf import PdfReader, PdfWriter

from dp_ferramentas.seguro_desemprego import (
    AnalysisResult,
    DocumentBundle,
    PageRecord,
    _bundle_records,
    parse_page_text,
    process_analysis,
    safe_employee_filename,
)


def _sd_text(number: str = "7000000001", name: str = "MARIA EXEMPLO DA SILVA", cpf: str = "111.222.333-44") -> str:
    return f"""MINISTÉRIO DO TRABALHO E EMPREGO
Requerimento de Seguro-Desemprego - SD
{number}
2 {name}
NOME
3 NOME DA MÃE EXEMPLO
NOME DA MÃE
7 {cpf}
CPF
"""


def _cd_text(number: str = "7000000001", name: str = "MARIA EXEMPLO DA SILVA", cpf: str = "111.222.333-44") -> str:
    return f"""MINISTÉRIO DO TRABALHO E EMPREGO
Comunicação de Dispensa - CD
{number}
2 {name}
NOME
3 NOME DA MÃE
7 {cpf}
CPF
"""


def test_parse_sd_extracts_key_fields(tmp_path):
    source = tmp_path / "entrada.pdf"
    record, issues = parse_page_text(_sd_text(), source, 0)

    assert issues == []
    assert record is not None
    assert record.document_type == "SD"
    assert record.request_number == "7000000001"
    assert record.name == "MARIA EXEMPLO DA SILVA"
    assert record.cpf == "111.222.333-44"


def test_parse_cd_extracts_key_fields(tmp_path):
    source = tmp_path / "entrada.pdf"
    record, issues = parse_page_text(_cd_text(), source, 4)

    assert issues == []
    assert record is not None
    assert record.document_type == "CD"
    assert record.page_number == 5


def test_bundle_matches_by_request_number_even_out_of_order(tmp_path):
    source = tmp_path / "entrada.pdf"
    sd, _ = parse_page_text(_sd_text(), source, 0)
    cd, _ = parse_page_text(_cd_text(), source, 8)

    bundles = _bundle_records([cd, sd])

    assert len(bundles) == 1
    assert bundles[0].valid
    assert bundles[0].sd_pages[0].page_number == 1
    assert bundles[0].cd_pages[0].page_number == 9


def test_bundle_rejects_divergent_cpf(tmp_path):
    source = tmp_path / "entrada.pdf"
    sd, _ = parse_page_text(_sd_text(), source, 0)
    cd, _ = parse_page_text(_cd_text(cpf="999.888.777-66"), source, 1)

    bundle = _bundle_records([sd, cd])[0]

    assert not bundle.valid
    assert any("CPF divergente" in issue for issue in bundle.issues)


def test_safe_filename_removes_windows_invalid_characters():
    assert safe_employee_filename('JOÃO: TESTE / "RH"?') == "JOÃO_ TESTE _ _RH__"


def test_process_analysis_generates_sd_then_cd_and_never_overwrites(tmp_path):
    source = tmp_path / "origem.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=300)
    writer.add_blank_page(width=200, height=300)
    with source.open("wb") as handle:
        writer.write(handle)

    sd = PageRecord(source, 0, "SD", "7000000001", "MARIA EXEMPLO", "111.222.333-44")
    cd = PageRecord(source, 1, "CD", "7000000001", "MARIA EXEMPLO", "111.222.333-44")
    analysis = AnalysisResult(
        bundles=[
            DocumentBundle(
                request_number="7000000001",
                name="MARIA EXEMPLO",
                cpf="111.222.333-44",
                sd_pages=[sd],
                cd_pages=[cd],
            )
        ],
        issues=[],
        total_pages=2,
    )

    output = tmp_path / "saida"
    first = process_analysis(analysis, output)
    second = process_analysis(analysis, output)

    assert source.exists()
    assert first.generated_files[0].name == "SD - MARIA EXEMPLO.pdf"
    assert second.generated_files[0].name == "SD - MARIA EXEMPLO - 7000000001.pdf"
    assert len(PdfReader(str(first.generated_files[0])).pages) == 2
    assert first.log_path.exists()
    assert first.warnings_path is None


def test_parse_cd_accepts_header_without_accents(tmp_path):
    source = tmp_path / "entrada.pdf"
    text = _cd_text().replace("Comunicação", "Comunicacao")

    record, issues = parse_page_text(text, source, 0)

    assert issues == []
    assert record is not None
    assert record.document_type == "CD"
