from argparse import Namespace
from pathlib import Path

from dp_ferramentas.distribuir_documentos_cli import collect_source_files, run


def _write_consignado(path: Path, name: str) -> None:
    path.write_text(
        f"cpfTrabalhador;nomeTrabalhador\n12345678900;{name}\n",
        encoding="utf-8",
    )


def test_collects_only_pdf_and_csv_from_source_folder(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF")
    (tmp_path / "b.csv").write_text("x", encoding="utf-8")
    (tmp_path / "ignorar.txt").write_text("x", encoding="utf-8")
    nested = tmp_path / "subpasta"
    nested.mkdir()
    (nested / "c.pdf").write_bytes(b"%PDF")

    assert [path.name for path in collect_source_files(tmp_path)] == ["a.pdf", "b.csv"]
    assert [path.name for path in collect_source_files(tmp_path, recursive=True)] == [
        "a.pdf",
        "b.csv",
        "c.pdf",
    ]


def test_cli_moves_multiple_files_and_treats_name_prepositions(tmp_path):
    source = tmp_path / "documentos"
    source.mkdir()
    first = source / "Consulta Consignado - JOAO SILVA.csv"
    second = source / "Consulta Consignado - MARIA DE SOUZA.csv"
    _write_consignado(first, "JOAO SILVA")
    _write_consignado(second, "MARIA DE SOUZA")

    root = tmp_path / "rescisoes"
    (root / "JOAO DA SILVA").mkdir(parents=True)
    (root / "MARIA SOUZA").mkdir()

    result = run(
        Namespace(
            origem=source,
            destino=root,
            incluir_subpastas=False,
            confirmar=True,
        )
    )

    assert result == 0
    assert (root / "JOAO DA SILVA" / first.name).exists()
    assert (root / "MARIA SOUZA" / second.name).exists()
    assert not first.exists()
    assert not second.exists()


def test_cli_blocks_all_files_when_one_employee_folder_is_missing(tmp_path):
    source = tmp_path / "documentos"
    source.mkdir()
    first = source / "Consulta Consignado - JOAO SILVA.csv"
    second = source / "Consulta Consignado - COLABORADOR AUSENTE.csv"
    _write_consignado(first, "JOAO SILVA")
    _write_consignado(second, "COLABORADOR AUSENTE")

    root = tmp_path / "rescisoes"
    (root / "JOAO SILVA").mkdir(parents=True)

    result = run(
        Namespace(
            origem=source,
            destino=root,
            incluir_subpastas=False,
            confirmar=True,
        )
    )

    assert result == 1
    assert first.exists()
    assert second.exists()
    assert not (root / "JOAO SILVA" / first.name).exists()
