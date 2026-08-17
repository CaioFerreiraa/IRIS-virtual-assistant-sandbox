import webbrowser

from core.logger_service import LoggerService
from core.module_runner import PYTHON_REQUEST_METHOD, ModuleRunner
from repositories.log_repository import LogRepository
from repositories.module_repository import ModuleRepository
from services.module_service import get_effective_module_variables
from services.module_manifest import MATERIAL_ICON_PATTERN, PUBLIC_KEY_PATTERN


class CommandProcessor:
    def __init__(self, module_repository: ModuleRepository):
        self.module_repository = module_repository
        self.module_runner = ModuleRunner()
        self.logger_service = LoggerService(LogRepository(module_repository.db))

    def create_module(
        self,
        module_public_key: str,
        name: str,
        call_name: str | None = None,
        custom_call_name: str | None = None,
        description: str = "",
        icon: str = "extension",
        parent_module_id: int | None = None,
    ):
        module_public_key = module_public_key.strip()
        if not module_public_key:
            raise ValueError("Informe a chave pública do módulo.")
        if not PUBLIC_KEY_PATTERN.fullmatch(module_public_key):
            raise ValueError(
                "A chave pública aceita somente letras minúsculas, números, pontos, hífens e underscores."
            )
        if not name:
            raise ValueError("Informe o nome do módulo.")
        icon = icon.strip()
        if not icon or len(icon) > 100 or not MATERIAL_ICON_PATTERN.fullmatch(icon):
            raise ValueError("Informe um nome válido do Material Icons.")
        if self.module_repository.get_by_public_key(module_public_key) is not None:
            raise ValueError("A chave pública informada já está registrada.")
        if (
            parent_module_id is not None
            and self.module_repository.get_by_id(parent_module_id) is None
        ):
            raise ValueError("O módulo pai informado não existe.")

        return self.module_repository.create_module(
            module_public_key=module_public_key,
            name=name,
            call_name=call_name or name,
            custom_call_name=custom_call_name,
            description=description,
            icon=icon,
            parent_module_id=parent_module_id,
        )

    def module_has_argument_search(self, module_path: str) -> bool:
        module = self.module_repository.find_by_path(module_path)
        return self._module_has_argument_search(module)

    def module_has_argument_search_by_id(self, module_id: int) -> bool:
        module = self.module_repository.get_by_id(module_id)
        return self._module_has_argument_search(module)

    def _module_has_argument_search(self, module) -> bool:
        if module is None:
            return False

        if not module.is_available:
            return False
        if (module.request_method or "").upper() != PYTHON_REQUEST_METHOD:
            return False

        return self.module_runner.has_argument_search(
            module.request_url,
            module.module_public_key,
        )

    def search_module_arguments(self, module_path: str, query: str = "") -> list[dict[str, str]]:
        module = self.module_repository.find_by_path(module_path)
        return self._search_module_arguments(module, query)

    def search_module_arguments_by_id(
        self,
        module_id: int,
        query: str = "",
    ) -> list[dict[str, str]]:
        module = self.module_repository.get_by_id(module_id)
        return self._search_module_arguments(module, query)

    def _search_module_arguments(self, module, query: str) -> list[dict[str, str]]:
        if module is None:
            return []

        if not module.is_available:
            return []
        if (module.request_method or "").upper() != PYTHON_REQUEST_METHOD:
            return []

        return self.module_runner.search_arguments(
            module.request_url,
            query,
            module.module_public_key,
        )

    def execute_module_path(self, module_path: str, argument: str | None = None) -> dict:
        module = self.module_repository.find_by_path(module_path)

        if module is None:
            raise ValueError(
                f"Módulo não encontrado: {module_path}"
            )

        return self._execute_and_log(module, module_path, argument)

    def execute_module_id(self, module_id: int, argument: str | None = None) -> dict:
        module = self.module_repository.get_by_id(module_id)
        if module is None:
            raise ValueError(f"Módulo não encontrado: {module_id}")
        return self._execute_and_log(
            module,
            self.module_repository.get_module_path(module),
            argument,
        )

    def _execute_and_log(self, module, module_path: str, argument: str | None) -> dict:
        try:
            result = self._execute_module(module, module_path, argument)
        except Exception as error:
            self._create_execution_log(module.id, "error", str(error))
            raise

        status = "success" if result.get("success", True) else "error"
        self._create_execution_log(module.id, status, self._build_log_message(result))
        return result

    def _execute_module(self, module, module_path: str, argument: str | None = None) -> dict:
        if not module.is_available:
            raise ValueError(
                f"O módulo '{module_path}' está indisponível e não pode ser executado."
            )
        if not module.is_executable:
            raise ValueError(
                f"O módulo '{module_path}' não possui execução configurada."
            )

        if not module.request_url:
            raise ValueError(
                f"O módulo '{module_path}' não possui destino configurado."
            )

        request_method = (module.request_method or "").upper()

        if request_method == PYTHON_REQUEST_METHOD:
            variables = get_effective_module_variables(
                self.module_repository.db,
                module.id,
            )
            return self.module_runner.run_entrypoint(
                module.request_url,
                argument,
                variables,
                module.module_public_key,
            )

        if request_method == "GET":
            opened = webbrowser.open(module.request_url)

            if not opened:
                raise RuntimeError(
                    f"Não foi possível abrir a URL: {module.request_url}"
                )

            return {
                "success": True,
                "opened": module.request_url,
            }

        raise ValueError(
            f"Método de execução não suportado: {request_method}"
        )

    def _create_execution_log(self, module_id: int, status: str, message: str = "") -> None:
        self.logger_service.create_log(
            module_id=module_id,
            status=status,
            message=message,
        )

    def _build_log_message(self, result: dict) -> str:
        if "message" in result:
            return str(result["message"])
        if "result" in result:
            return str(result["result"])
        if "opened" in result:
            return f"URL aberta: {result['opened']}"
        return ""
