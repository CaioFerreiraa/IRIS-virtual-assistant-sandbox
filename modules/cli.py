from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from services.module_development_service import (
    ModuleDevelopmentService,
    ModuleScaffoldError,
    ModuleValidationReport,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m modules",
        description="Cria e valida módulos locais da IRIS.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser(
        "new",
        help="Cria um módulo a partir de um exemplo oficial.",
    )
    new_parser.add_argument("module_public_key", help="Chave pública única do módulo.")
    new_parser.add_argument("--name", required=True, help="Nome exibido na IRIS.")
    new_parser.add_argument(
        "--kind",
        choices=("python", "http"),
        default="python",
        help="Tipo do módulo criado. O padrão é python.",
    )
    new_parser.add_argument(
        "--output",
        type=Path,
        help="Pasta de destino. O padrão é modules/installed/<chave>.",
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help="Valida o manifesto e os arquivos sem importar código Python.",
    )
    _add_validation_arguments(validate_parser)

    check_parser = subparsers.add_parser(
        "check",
        help="Valida e importa o entry point para conferir o contrato Python.",
    )
    _add_validation_arguments(check_parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    service = ModuleDevelopmentService()

    if arguments.command == "new":
        try:
            path = service.create_module(
                arguments.module_public_key,
                arguments.name,
                kind=arguments.kind,
                output_path=arguments.output,
            )
        except (ModuleScaffoldError, OSError, ValueError) as error:
            print(f"Erro: {error}", file=sys.stderr)
            return 1
        print(f"Módulo criado em {path}")
        print(f"Valide com: python -m modules check \"{path}\"")
        return 0

    check_runtime = arguments.command == "check"
    report = service.validate_module(
        arguments.folder,
        check_runtime=check_runtime,
    )
    if arguments.json:
        print(_report_as_json(report))
    else:
        _print_report(report)
    return 0 if report.is_valid else 1


def _add_validation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("folder", type=Path, help="Pasta que contém module.json.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Escreve o resultado em JSON para automações.",
    )


def _print_report(report: ModuleValidationReport) -> None:
    status = "Válido" if report.is_valid else "Inválido"
    print(f"{status}: {report.folder}")
    if report.module_public_key:
        print(f"Chave pública: {report.module_public_key}")
    print(f"Etapa: {report.stage}")
    print(report.message)


def _report_as_json(report: ModuleValidationReport) -> str:
    return json.dumps(
        {
            "folder": str(report.folder),
            "is_valid": report.is_valid,
            "checked_runtime": report.checked_runtime,
            "stage": report.stage,
            "message": report.message,
            "module_public_key": report.module_public_key,
            "name": report.name,
            "runtime_type": report.runtime_type,
            "is_executable": report.is_executable,
        },
        ensure_ascii=False,
        indent=2,
    )


if __name__ == "__main__":
    raise SystemExit(main())
