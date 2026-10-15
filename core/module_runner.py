import inspect
from collections.abc import Callable

from modules.installed_modules import get_installed_modules
from services.module_loader import load_python_entrypoint
from util.vault_values import redact_vault_values


PYTHON_REQUEST_METHOD = "PYTHON"

ARGUMENT_SEARCH_FUNCTION_NAMES = (
    "search_arguments",
    "searchArguments",
)
ARGUMENT_REQUEST_FUNCTION_NAMES = (
    "should_request_argument",
    "shouldRequestArgument",
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

    def should_request_argument(
        self,
        entrypoint: str | None,
        variables: dict[str, str] | None = None,
        module_public_key: str = "module",
    ) -> bool:
        if not entrypoint:
            return False

        module = self._load_entrypoint(entrypoint, module_public_key)
        if self._get_argument_search(module) is None:
            return False

        for function_name in ARGUMENT_REQUEST_FUNCTION_NAMES:
            function = getattr(module, function_name, None)
            if callable(function):
                return bool(self._call_with_optional_variables(function, variables or {}))
        return True

    def run_entrypoint(
        self,
        entrypoint: str,
        argument: str | None = None,
        variables: dict[str, str] | None = None,
        module_public_key: str = "module",
        vault: dict[str, str] | None = None,
        redact_result: bool = True,
    ) -> dict:
        module = self._load_entrypoint(entrypoint, module_public_key)

        for function_name in ("execute", "run", "main"):
            function = getattr(module, function_name, None)
            if callable(function):
                try:
                    result = self._call_entrypoint(function, argument, variables or {}, vault or {})
                except Exception as error:
                    if vault:
                        raise RuntimeError(str(redact_vault_values(str(error), vault))) from None
                    raise
                result = result if isinstance(result, dict) else {"success": True, "result": result}
                if redact_result:
                    return redact_vault_values(result, vault or {}, preserve_result_fields=True)
                return result

        raise ValueError(f"Módulo sem função executável: {entrypoint}")

    def _load_entrypoint(self, entrypoint: str, module_public_key: str = "module"):
        return load_python_entrypoint(entrypoint, module_public_key)

    def _call_entrypoint(
        self,
        function: Callable,
        argument: str | None,
        variables: dict[str, str],
        vault: dict[str, str] | None = None,
    ):
        signature = inspect.signature(function)
        parameters = signature.parameters
        accepts_keywords = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        available = {"argument": argument, "variables": variables, "vault": dict(vault or {})}
        keyword_arguments = {}
        positional_arguments = []
        for parameter in parameters.values():
            if parameter.kind == inspect.Parameter.POSITIONAL_ONLY:
                if parameter.name in available:
                    positional_arguments.append(available[parameter.name])
                elif not positional_arguments and argument is not None:
                    positional_arguments.append(argument)
                elif parameter.default is not inspect.Parameter.empty:
                    positional_arguments.append(parameter.default)
            elif parameter.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
                if parameter.name in available:
                    keyword_arguments[parameter.name] = available[parameter.name]
                elif not positional_arguments and "argument" not in parameters and not accepts_keywords and argument is not None:
                    positional_arguments.append(argument)
            elif parameter.kind == inspect.Parameter.KEYWORD_ONLY and parameter.name in available:
                keyword_arguments[parameter.name] = available[parameter.name]
        if accepts_keywords:
            for name, value in available.items():
                if name not in parameters:
                    keyword_arguments[name] = value
        elif not parameters.keys() & available.keys() and argument is not None and any(
            parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in parameters.values()
        ):
            positional_arguments.append(argument)
        return function(*positional_arguments, **keyword_arguments)

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

    def _call_with_optional_variables(
        self,
        function: Callable,
        variables: dict[str, str],
    ):
        signature = inspect.signature(function)
        parameters = signature.parameters
        if "variables" in parameters or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        ):
            return function(variables=variables)
        if any(
            parameter.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.VAR_POSITIONAL,
            )
            for parameter in parameters.values()
        ):
            return function(variables)
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
