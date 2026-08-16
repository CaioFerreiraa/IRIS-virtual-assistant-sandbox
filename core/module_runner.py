import inspect
from collections.abc import Callable

from modules.installed_modules import get_installed_modules
from services.module_loader import load_python_entrypoint


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
            return {"success": False, "message": "Módulo não encontrado."}
        return module.run(call_name=action_call_name, payload=payload or {})

    def has_argument_search(
        self,
        entrypoint: str | None,
        module_public_key: str = "module",
    ) -> bool:
        if not entrypoint:
            return False

        module = self._load_entrypoint(entrypoint, module_public_key)
        return self._get_argument_search(module) is not None

    def search_arguments(
        self,
        entrypoint: str | None,
        query: str = "",
        module_public_key: str = "module",
    ) -> list[dict[str, str]]:
        if not entrypoint:
            return []

        module = self._load_entrypoint(entrypoint, module_public_key)
        search_arguments = self._get_argument_search(module)
        if not callable(search_arguments):
            return []

        return self._normalize_argument_results(self._call_with_optional_query(search_arguments, query))

    def run_entrypoint(
        self,
        entrypoint: str,
        argument: str | None = None,
        variables: dict[str, str] | None = None,
        module_public_key: str = "module",
    ) -> dict:
        module = self._load_entrypoint(entrypoint, module_public_key)

        for function_name in ("execute", "run", "main"):
            function = getattr(module, function_name, None)
            if callable(function):
                result = self._call_entrypoint(function, argument, variables or {})
                return result if isinstance(result, dict) else {"success": True, "result": result}

        raise ValueError(f"Módulo sem função executável: {entrypoint}")

    def _load_entrypoint(self, entrypoint: str, module_public_key: str = "module"):
        return load_python_entrypoint(entrypoint, module_public_key)

    def _call_entrypoint(
        self,
        function: Callable,
        argument: str | None,
        variables: dict[str, str],
    ):
        signature = inspect.signature(function)
        parameters = signature.parameters
        accepts_keywords = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        keyword_arguments = {}
        if "argument" in parameters or accepts_keywords:
            keyword_arguments["argument"] = argument
        if "variables" in parameters or accepts_keywords:
            keyword_arguments["variables"] = variables
        if keyword_arguments:
            return function(**keyword_arguments)

        if argument is not None and any(
            parameter.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.VAR_POSITIONAL,
            )
            for parameter in parameters.values()
        ):
            return function(argument)
        return function()

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
