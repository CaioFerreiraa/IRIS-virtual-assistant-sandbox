from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil

from services.module_manifest import PUBLIC_KEY_PATTERN
from services.module_validation import (
    ModuleFolderValidationError,
    validate_module_folder,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INSTALLED_MODULES_DIR = PROJECT_ROOT / "modules" / "installed"
DEFAULT_EXAMPLES_DIR = PROJECT_ROOT / "modules" / "examples"
SUPPORTED_SCAFFOLD_KINDS = ("python", "http")


@dataclass(frozen=True)
class ModuleValidationReport:
    folder: Path
    is_valid: bool
    checked_runtime: bool
    stage: str
    message: str
    module_public_key: str | None = None
    name: str | None = None
    runtime_type: str | None = None
    is_executable: bool | None = None


class ModuleScaffoldError(ValueError):
    pass


class ModuleDevelopmentService:
    def __init__(
        self,
        installed_modules_dir: Path = DEFAULT_INSTALLED_MODULES_DIR,
        examples_dir: Path = DEFAULT_EXAMPLES_DIR,
    ) -> None:
        self.installed_modules_dir = installed_modules_dir.resolve()
        self.examples_dir = examples_dir.resolve()

    def create_module(
        self,
        module_public_key: str,
        name: str,
        *,
        kind: str = "python",
        output_path: Path | None = None,
    ) -> Path:
        normalized_key = module_public_key.strip()
        normalized_name = name.strip()
        if not PUBLIC_KEY_PATTERN.fullmatch(normalized_key):
            raise ModuleScaffoldError(
                "A chave pública aceita somente letras minúsculas, números, pontos, hífens e underscores."
            )
        if len(normalized_key) > 120:
            raise ModuleScaffoldError("A chave pública deve ter no máximo 120 caracteres.")
        if not normalized_name:
            raise ModuleScaffoldError("Informe o nome exibido do módulo.")
        if len(normalized_name) > 100:
            raise ModuleScaffoldError("O nome exibido deve ter no máximo 100 caracteres.")
        if kind not in SUPPORTED_SCAFFOLD_KINDS:
            raise ModuleScaffoldError(
                f"O tipo '{kind}' não é suportado. Use python ou http."
            )

        target_path = (
            output_path.resolve()
            if output_path is not None
            else self.installed_modules_dir / _folder_name(normalized_key)
        )
        if target_path.exists():
            raise ModuleScaffoldError(
                f"O destino já existe e não foi alterado: {target_path}"
            )
        existing_folder = self._find_installed_public_key(normalized_key)
        if existing_folder is not None:
            raise ModuleScaffoldError(
                f"A chave pública '{normalized_key}' já existe em {existing_folder}."
            )

        template_name = "minimal" if kind == "python" else "http_minimal"
        template_path = self.examples_dir / template_name
        if not template_path.is_dir():
            raise ModuleScaffoldError(
                f"O template '{template_name}' não foi encontrado em {self.examples_dir}."
            )

        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(template_path, target_path)
        try:
            self._customize_scaffold(
                target_path,
                normalized_key,
                normalized_name,
                kind,
            )
        except Exception:
            shutil.rmtree(target_path)
            raise
        return target_path

    def validate_module(
        self,
        folder: Path,
        *,
        check_runtime: bool = False,
    ) -> ModuleValidationReport:
        resolved_folder = folder.resolve()
        try:
            candidate = validate_module_folder(
                resolved_folder,
                check_runtime=check_runtime,
            )
        except ModuleFolderValidationError as error:
            return ModuleValidationReport(
                folder=resolved_folder,
                is_valid=False,
                checked_runtime=check_runtime,
                stage=error.stage,
                message=str(error),
                module_public_key=error.module_public_key,
            )

        manifest = candidate.manifest
        message = (
            "Manifesto, arquivos e contrato Python válidos."
            if check_runtime and manifest.runtime_type == "python"
            else "Manifesto e arquivos válidos."
        )
        return ModuleValidationReport(
            folder=resolved_folder,
            is_valid=True,
            checked_runtime=check_runtime,
            stage="concluído",
            message=message,
            module_public_key=manifest.module_public_key,
            name=manifest.name,
            runtime_type=manifest.runtime_type,
            is_executable=manifest.is_executable,
        )

    def list_installed_modules(self) -> tuple[ModuleValidationReport, ...]:
        if not self.installed_modules_dir.is_dir():
            return ()
        return tuple(
            self.validate_module(folder)
            for folder in sorted(
                self.installed_modules_dir.iterdir(),
                key=lambda path: path.name.casefold(),
            )
            if folder.is_dir()
        )

    def _customize_scaffold(
        self,
        target_path: Path,
        module_public_key: str,
        name: str,
        kind: str,
    ) -> None:
        manifest_path = target_path / "module.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        module_data = manifest["module"]
        module_data["module_public_key"] = module_public_key
        module_data["name"] = name
        module_data["call_name"] = _default_call_name(module_public_key)
        module_data["description"] = (
            f"Módulo Python {name}."
            if kind == "python"
            else f"Módulo HTTP {name}."
        )
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )
        (target_path / "README.md").write_text(
            _build_scaffold_readme(name, kind),
            encoding="utf-8",
        )

    def _find_installed_public_key(self, module_public_key: str) -> Path | None:
        if not self.installed_modules_dir.is_dir():
            return None
        for folder in self.installed_modules_dir.iterdir():
            if not folder.is_dir():
                continue
            try:
                candidate = validate_module_folder(folder)
            except ModuleFolderValidationError:
                continue
            if candidate.manifest.module_public_key == module_public_key:
                return folder.resolve()
        return None


def _folder_name(module_public_key: str) -> str:
    return re.sub(r"[.-]+", "_", module_public_key)


def _default_call_name(module_public_key: str) -> str:
    leaf = module_public_key.rsplit(".", 1)[-1]
    return re.sub(r"[-_]+", " ", leaf).strip()


def _build_scaffold_readme(name: str, kind: str) -> str:
    execution = (
        "A função `execute(argument, variables)` em `main.py` contém a ação do módulo."
        if kind == "python"
        else "A seção `http_request` de `module.json` contém a requisição declarativa."
    )
    return f"""# {name}

Descreva a finalidade deste módulo e o resultado esperado.

## Como usar

Explique o comando, o argumento e as configurações disponíveis.

{execution}

## Dependências e permissões

Liste rede, arquivos, programas, portas e bibliotecas utilizados. Não inclua
credenciais, tokens ou senhas.

## Limitações

Registre falhas conhecidas e condições em que o módulo não deve ser executado.
"""
