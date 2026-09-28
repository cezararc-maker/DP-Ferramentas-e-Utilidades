from pathlib import Path

from pypdf import PdfReader, PdfWriter

from dp_ferramentas.seguro_desemprego import (
    AnalysisResult,
    DocumentBundle,
    PageRecord,
    _bundle_records,
    diagnose_employee_folders,
    find_employee_folder,
    normalize_employee_folder_name,
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
    assert first.generated_files[0].parent == output / "MARIA EXEMPLO"
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


def test_normalize_employee_folder_name_ignores_requested_prepositions():
    assert normalize_employee_folder_name("JOÃO DA SILVA", ignore_prepositions=True) == "joao silva"
    assert normalize_employee_folder_name("MARIA DOS SANTOS", ignore_prepositions=True) == "maria santos"
    assert normalize_employee_folder_name("PEDRO DE SOUZA", ignore_prepositions=True) == "pedro souza"


def test_find_employee_folder_matches_name_without_preposition(tmp_path):
    root = tmp_path / "Rescisoes"
    root.mkdir()
    target = root / "JOAO SILVA"
    target.mkdir()

    found, mode = find_employee_folder(root, "JOÃO DA SILVA")

    assert found == target.resolve()
    assert "ignorando" in mode


def test_find_employee_folder_prefers_exact_match(tmp_path):
    root = tmp_path / "Rescisoes"
    root.mkdir()
    exact = root / "JOAO DA SILVA"
    relaxed = root / "JOAO SILVA"
    exact.mkdir()
    relaxed.mkdir()

    found, mode = find_employee_folder(root, "JOÃO DA SILVA")

    assert found == exact.resolve()
    assert mode == "nome exato"


def test_find_employee_folder_rejects_ambiguous_relaxed_match(tmp_path):
    root = tmp_path / "Rescisoes"
    root.mkdir()
    (root / "JOAO DA SILVA").mkdir()
    (root / "JOAO DE SILVA").mkdir()

    found, message = find_employee_folder(root, "JOAO DO SILVA")

    assert found is None
    assert "mais de uma pasta possível" in message


def test_process_analysis_distributes_into_existing_rescisao_folder(tmp_path):
    source = tmp_path / "origem.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=300)
    writer.add_blank_page(width=200, height=300)
    with source.open("wb") as handle:
        writer.write(handle)

    sd = PageRecord(source, 0, "SD", "7000000002", "JOAO DA SILVA", "111.222.333-44")
    cd = PageRecord(source, 1, "CD", "7000000002", "JOAO DA SILVA", "111.222.333-44")
    analysis = AnalysisResult(
        bundles=[
            DocumentBundle(
                request_number="7000000002",
                name="JOAO DA SILVA",
                cpf="111.222.333-44",
                sd_pages=[sd],
                cd_pages=[cd],
            )
        ],
        issues=[],
        total_pages=2,
    )

    output = tmp_path / "relatorios"
    rescisao_root = tmp_path / "Rescisoes"
    destination = rescisao_root / "JOAO SILVA"
    destination.mkdir(parents=True)

    result = process_analysis(
        analysis,
        output,
        rescisao_root=rescisao_root,
    )

    assert result.generated_files == [destination / "SD - JOAO DA SILVA.pdf"]
    assert result.distribution_issues == []
    assert result.warnings_path is None


def test_process_analysis_blocks_before_writing_when_rescisao_folder_is_missing(tmp_path):
    source = tmp_path / "origem.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=300)
    writer.add_blank_page(width=200, height=300)
    with source.open("wb") as handle:
        writer.write(handle)

    sd = PageRecord(source, 0, "SD", "7000000003", "ANA DAS FLORES", "111.222.333-44")
    cd = PageRecord(source, 1, "CD", "7000000003", "ANA DAS FLORES", "111.222.333-44")
    analysis = AnalysisResult(
        bundles=[
            DocumentBundle(
                request_number="7000000003",
                name="ANA DAS FLORES",
                cpf="111.222.333-44",
                sd_pages=[sd],
                cd_pages=[cd],
            )
        ],
        issues=[],
        total_pages=2,
    )

    output = tmp_path / "relatorios"
    rescisao_root = tmp_path / "Rescisoes"
    rescisao_root.mkdir()

    import pytest

    with pytest.raises(ValueError, match="Nenhum PDF foi gravado"):
        process_analysis(
            analysis,
            output,
            rescisao_root=rescisao_root,
        )

    assert list(rescisao_root.rglob("*.pdf")) == []



def test_diagnose_employee_folders_reports_exact_relaxed_and_missing(tmp_path):
    root = tmp_path / "Rescisoes"
    root.mkdir()
    (root / "MARIA EXEMPLO").mkdir()
    (root / "JOAO SILVA").mkdir()

    source = tmp_path / "origem.pdf"
    bundles = [
        DocumentBundle(request_number="1", name="MARIA EXEMPLO"),
        DocumentBundle(request_number="2", name="JOAO DA SILVA"),
        DocumentBundle(request_number="3", name="ANA DOS SANTOS"),
    ]
    for bundle in bundles:
        bundle.sd_pages.append(PageRecord(source, 0, "SD", bundle.request_number, bundle.name, "1"))
        bundle.cd_pages.append(PageRecord(source, 1, "CD", bundle.request_number, bundle.name, "1"))

    analysis = AnalysisResult(bundles=bundles, issues=[], total_pages=6)
    diagnostics = diagnose_employee_folders(analysis, root)

    assert diagnostics["1"].status == "exact"
    assert diagnostics["1"].safe
    assert diagnostics["2"].status == "relaxed"
    assert diagnostics["2"].safe
    assert diagnostics["3"].status == "missing"
    assert not diagnostics["3"].safe


def test_diagnose_employee_folders_reports_ambiguous_without_selecting_folder(tmp_path):
    root = tmp_path / "Rescisoes"
    root.mkdir()
    (root / "JOAO DA SILVA").mkdir()
    (root / "JOAO DE SILVA").mkdir()

    source = tmp_path / "origem.pdf"
    bundle = DocumentBundle(
        request_number="7000000004",
        name="JOAO DO SILVA",
        sd_pages=[PageRecord(source, 0, "SD", "7000000004", "JOAO DO SILVA", "1")],
        cd_pages=[PageRecord(source, 1, "CD", "7000000004", "JOAO DO SILVA", "1")],
    )
    analysis = AnalysisResult(bundles=[bundle], issues=[], total_pages=2)

    diagnostic = diagnose_employee_folders(analysis, root)["7000000004"]

    assert diagnostic.status == "ambiguous"
    assert diagnostic.folder is None
    assert len(diagnostic.candidates) == 2
    assert not diagnostic.safe


def test_direct_distribution_is_all_or_nothing_when_one_folder_is_missing(tmp_path):
    source = tmp_path / "origem.pdf"
    writer = PdfWriter()
    for _ in range(4):
        writer.add_blank_page(width=200, height=300)
    with source.open("wb") as handle:
        writer.write(handle)

    found_bundle = DocumentBundle(
        request_number="7000000100",
        name="MARIA EXEMPLO",
        sd_pages=[PageRecord(source, 0, "SD", "7000000100", "MARIA EXEMPLO", "1")],
        cd_pages=[PageRecord(source, 1, "CD", "7000000100", "MARIA EXEMPLO", "1")],
    )
    missing_bundle = DocumentBundle(
        request_number="7000000101",
        name="ANA DAS FLORES",
        sd_pages=[PageRecord(source, 2, "SD", "7000000101", "ANA DAS FLORES", "2")],
        cd_pages=[PageRecord(source, 3, "CD", "7000000101", "ANA DAS FLORES", "2")],
    )
    analysis = AnalysisResult(
        bundles=[found_bundle, missing_bundle],
        issues=[],
        total_pages=4,
    )

    root = tmp_path / "Rescisoes"
    destination = root / "MARIA EXEMPLO"
    destination.mkdir(parents=True)

    import pytest

    with pytest.raises(ValueError, match="Nenhum PDF foi gravado"):
        process_analysis(
            analysis,
            tmp_path / "relatorios",
            rescisao_root=root,
        )

    assert list(destination.glob("*.pdf")) == []
