import importlib
import inspect
from collections.abc import Callable

from modules.installed_modules import get_installed_modules


PYTHON_REQUEST_METHOD = "PYTHON"

ARGUMENT_SEARCH_FUNCTION_NAMES = (
    "search_arguments",
    "searchArguments",
)

class ModuleRunner:
    def __init__(self):
        self.modules = get_installed_modules()

    def run(self, module_call_name: str, action_call_name: str, payload: dict | None = None) -> dict:
        module = self.modules.get(module_call_name)
        if module is None:
            return {"success": False, "message": "Modulo nao encontrado."}
        return module.run(call_name=action_call_name, payload=payload or {})

    def has_argument_search(self, entrypoint: str | None) -> bool:
        if not entrypoint:
            return False

        module = self._load_entrypoint(entrypoint)
        return self._get_argument_search(module) is not None

    def search_arguments(self, entrypoint: str | None, query: str = "") -> list[dict[str, str]]:
        if not entrypoint:
            return []

        module = self._load_entrypoint(entrypoint)
        search_arguments = self._get_argument_search(module)
        if not callable(search_arguments):
            return []

        return self._normalize_argument_results(self._call_with_optional_query(search_arguments, query))

    def run_entrypoint(self, entrypoint: str, argument: str | None = None) -> dict:
        module = self._load_entrypoint(entrypoint)

        for function_name in ("execute", "run", "main"):
            function = getattr(module, function_name, None)
            if callable(function):
                result = function(argument) if argument is not None else function()
                return result if isinstance(result, dict) else {"success": True, "result": result}

        raise ValueError(f"Modulo sem funcao executavel: {entrypoint}")

    def _load_entrypoint(self, entrypoint: str):
        module_path = entrypoint[:-3] if entrypoint.endswith(".py") else entrypoint
        module_path = module_path.replace("\\", ".").replace("/", ".")
        return importlib.import_module(module_path)

    def _call_with_optional_query(self, function: Callable, query: str):
        signature = inspect.signature(function)
        accepts_positional_argument = any(
            parameter.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.VAR_POSITIONAL,
            )
            for parameter in signature.parameters.values()
        )

        if accepts_positional_argument:
            return function(query)

        return function()

    def _normalize_argument_results(self, results) -> list[dict[str, str]]:
        normalized_results: list[dict[str, str]] = []

        for result in results or []:
            if isinstance(result, dict):
                value = str(result.get("value", result.get("label", "")))
                label = str(result.get("label", value))
                description = str(result.get("description", ""))
            else:
                value = str(result)
                label = value
                description = ""

            if value:
                normalized_results.append(
                    {
                        "label": label,
                        "value": value,
                        "description": description,
                    }
                )

        return normalized_results

    def _get_argument_search(self, module) -> Callable | None:
        for function_name in ARGUMENT_SEARCH_FUNCTION_NAMES:
            function = getattr(module, function_name, None)

            if callable(function):
                return function

        return None