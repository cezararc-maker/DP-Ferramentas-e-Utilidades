import csv
from pathlib import Path

import pytest

from dp_ferramentas import distribuidor_documentos as module
from dp_ferramentas.distribuidor_documentos import (
    analyze_distribution,
    analyze_file,
    move_distribution,
)


def test_identifies_fgts_pdf(monkeypatch, tmp_path):
    source = tmp_path / "arquivo.pdf"
    source.write_bytes(b"%PDF")
    monkeypatch.setattr(
        module,
        "_pdf_text",
        lambda path: (
            "Extrato de Conta do Fundo de Garantia - FGTS\n"
            "Nome: RODRIGO BENITES PIS/PASEP/NIT: 123"
        ),
    )

    item = analyze_file(source)

    assert item.document_type == "Extrato FGTS"
    assert item.employee_name == "RODRIGO BENITES"
    assert not item.error


def test_identifies_consignado_pdf(monkeypatch, tmp_path):
    source = tmp_path / "consulta.pdf"
    source.write_bytes(b"%PDF")
    monkeypatch.setattr(
        module,
        "_pdf_text",
        lambda path: (
            "Consultar garantias de verbas rescisórias\n"
            "Resultado da consulta\n"
            "123.456.789-00\n"
            "IVANILDO ANTONIO SOARES PAREDE\n"
            "12345"
        ),
    )

    item = analyze_file(source)

    assert item.document_type == "Consulta Consignado (PDF)"
    assert item.employee_name == "IVANILDO ANTONIO SOARES PAREDE"


def test_identifies_consignado_csv(tmp_path):
    source = tmp_path / "consulta.csv"
    with source.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["cpfTrabalhador", "nomeTrabalhador"],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerow(
            {
                "cpfTrabalhador": "12345678900",
                "nomeTrabalhador": "RODRIGO BENITES",
            }
        )

    item = analyze_file(source)

    assert item.document_type == "Consulta Consignado (CSV)"
    assert item.employee_name == "RODRIGO BENITES"


def test_distribution_is_all_or_nothing(monkeypatch, tmp_path):
    root = tmp_path / "rescisoes"
    root.mkdir()
    (root / "RODRIGO BENITES").mkdir()
    first = tmp_path / "RODRIGO BENITES - Extrato FGTS BASE MS.pdf"
    second = tmp_path / "OUTRO - Extrato FGTS BASE MS.pdf"
    first.write_bytes(b"%PDF")
    second.write_bytes(b"%PDF")

    def fake_pdf(path):
        if path == first.resolve():
            return "Extrato de Conta do Fundo de Garantia - FGTS\nNome: RODRIGO BENITES PIS: 1"
        return "Extrato de Conta do Fundo de Garantia - FGTS\nNome: OUTRO PIS: 2"

    monkeypatch.setattr(module, "_pdf_text", fake_pdf)
    analysis = analyze_distribution([first, second], root)

    assert not analysis.ready
    with pytest.raises(ValueError, match="destino seguro"):
        move_distribution(analysis)
    assert first.exists()
    assert second.exists()


def test_moves_files_and_preserves_existing_names(tmp_path):
    root = tmp_path / "rescisoes"
    employee = root / "RODRIGO BENITES"
    employee.mkdir(parents=True)
    existing = employee / "Consulta Consignado - RODRIGO BENITES.csv"
    existing.write_text("anterior", encoding="utf-8")
    source = tmp_path / existing.name
    source.write_text("nomeTrabalhador\nRODRIGO BENITES\n", encoding="utf-8")

    analysis = analyze_distribution([source], root)
    moved = move_distribution(analysis)

    assert moved[0].name == "Consulta Consignado - RODRIGO BENITES (2).csv"
    assert moved[0].exists()
    assert existing.read_text(encoding="utf-8") == "anterior"


def test_matches_folder_ignoring_name_prepositions(tmp_path):
    root = tmp_path / "rescisoes"
    target = root / "JOAO DA SILVA"
    target.mkdir(parents=True)
    source = tmp_path / "Consulta Consignado - JOAO SILVA.csv"
    source.write_text("nomeTrabalhador\nJOAO SILVA\n", encoding="utf-8")

    analysis = analyze_distribution([source], root)

    assert analysis.ready
    assert analysis.items[0].destination.parent == target.resolve()
