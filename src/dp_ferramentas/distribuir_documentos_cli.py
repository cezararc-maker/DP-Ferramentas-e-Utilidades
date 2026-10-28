from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .distribuidor_documentos import (
    SUPPORTED_SUFFIXES,
    DistributionAnalysis,
    analyze_distribution,
    move_distribution,
)


def collect_source_files(source: Path, recursive: bool = False) -> list[Path]:
    source = Path(source).expanduser().resolve()
    if source.is_file():
        return [source] if source.suffix.lower() in SUPPORTED_SUFFIXES else []
    if not source.is_dir():
        return []
    iterator = source.rglob("*") if recursive else source.iterdir()
    return sorted(
        (
            item.resolve()
            for item in iterator
            if item.is_file() and item.suffix.lower() in SUPPORTED_SUFFIXES
        ),
        key=lambda item: item.name.casefold(),
    )


def print_analysis(analysis: DistributionAnalysis) -> None:
    print()
    print("=" * 78)
    print("CONFERÊNCIA DOS DESTINOS")
    print("=" * 78)
    for index, item in enumerate(analysis.items, start=1):
        print(f"\n[{index}] Arquivo: {item.source.name}")
        print(f"    Tipo: {item.document_type or 'NÃO IDENTIFICADO'}")
        print(f"    Colaborador: {item.employee_name or 'NÃO IDENTIFICADO'}")
        if item.destination:
            print(f"    Destino: {item.destination}")
            print("    Situação: PRONTO")
        else:
            print("    Destino: NÃO DEFINIDO")
            print(f"    Situação: {item.error}")
            if item.diagnostic and item.diagnostic.candidates:
                print("    Pastas possíveis:")
                for candidate in item.diagnostic.candidates:
                    print(f"      - {candidate}")
    print()
    print("=" * 78)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Identifica Extratos FGTS e Consultas do Consignado e os move "
            "para a pasta de cada colaborador."
        )
    )
    parser.add_argument("--origem", required=True, type=Path)
    parser.add_argument("--destino", required=True, type=Path)
    parser.add_argument(
        "--incluir-subpastas",
        action="store_true",
        help="Também procura documentos dentro das subpastas da origem.",
    )
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="Move sem solicitar a confirmação digitada. Use somente em automações.",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    source = args.origem.expanduser().resolve()
    destination_root = args.destino.expanduser().resolve()

    if not source.exists():
        print(f"ERRO: a origem não existe: {source}")
        return 2
    if not destination_root.is_dir():
        print(f"ERRO: a pasta principal das rescisões não existe: {destination_root}")
        return 2

    files = collect_source_files(source, args.incluir_subpastas)
    if not files:
        print("ERRO: nenhum PDF ou CSV foi encontrado na origem informada.")
        return 2

    print(f"Arquivos encontrados: {len(files)}")
    print(f"Pasta principal das rescisões: {destination_root}")
    analysis = analyze_distribution(files, destination_root)
    print_analysis(analysis)

    if not analysis.ready:
        problems = sum(not item.ready for item in analysis.items)
        print(
            f"MOVIMENTAÇÃO BLOQUEADA: {problems} arquivo(s) possuem pendências. "
            "Nenhum arquivo foi movido."
        )
        return 1

    if not args.confirmar:
        answer = input(
            f"Digite MOVER para confirmar a movimentação dos {len(files)} arquivo(s): "
        ).strip()
        if answer != "MOVER":
            print("Operação cancelada. Nenhum arquivo foi movido.")
            return 1

    moved = move_distribution(analysis)
    print()
    print(f"CONCLUÍDO: {len(moved)} arquivo(s) movido(s) com sucesso.")
    for path in moved:
        print(f"  - {path}")
    return 0


def main() -> int:
    parser = build_parser()
    return run(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
