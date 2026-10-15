from __future__ import annotations

import json
import logging
from pathlib import Path
import re
from time import perf_counter
from typing import Any
from collections.abc import Callable
from urllib.parse import parse_qsl, urlsplit

import httpx

from database.db import SessionLocal
from database.models import ModuleHttpRequest
from repositories.module_http_request_repository import ModuleHttpRequestRepository
from services.module_manifest import (
    JSON_RESPONSE_PATH_PATTERN,
    ManifestHttpItem,
    ManifestHttpRequest,
    SENSITIVE_HTTP_NAME_PATTERN,
    SENSITIVE_HTTP_VALUE_PATTERN,
    SUPPORTED_HTTP_BODY_MODES,
    SUPPORTED_HTTP_METHODS,
    parse_module_manifest,
    is_vault_placeholder_value,
    validate_non_sensitive_http_content,
)
from services.vault_service import VaultService
from util.vault_names import (
    PLACEHOLDER_PATTERN,
    VAULT_NAME_PATTERN,
    http_url_for_validation,
    load_vault_names,
)
from util.vault_values import redact_vault_values


REQUEST_TIMEOUT_SECONDS = 30.0
MAX_RESPONSE_BODY_CHARACTERS = 100_000
TRUNCATED_BODY_SUFFIX = "\n\n[Resposta truncada pela IRIS.]"

# O histórico da IRIS já registra o resumo. HTTPX/Core em INFO/DEBUG podem
# registrar URLs ou cabeçalhos resolvidos; mantenha apenas diagnósticos de falha.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class HttpService:
    def request(
        self,
        method: str,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        body: object | None = None,
        *,
        body_mode: str = "none",
        vault: dict[str, str] | None = None,
        on_response: Callable[[httpx.Response, bool], None] | None = None,
    ) -> dict[str, object]:
        request_arguments: dict[str, object] = {
            "params": params or None,
            "headers": headers or None,
            "timeout": REQUEST_TIMEOUT_SECONDS,
            "follow_redirects": True,
        }
        if body_mode == "raw_json" and body is not None:
            request_arguments["json"] = body
        elif body_mode == "raw_text" and body is not None:
            request_arguments["content"] = body
        elif body_mode == "form_urlencoded" and body is not None:
            request_arguments["data"] = body

        started_at = perf_counter()
        try:
            response = httpx.request(
                method,
                url,
                **request_arguments,
            )
        except httpx.TimeoutException:
            return {
                "success": False,
                "message": "A requisição HTTP excedeu o limite de 30 segundos.",
                "status_code": None,
                "reason_phrase": "",
                "elapsed_ms": _elapsed_ms(started_at),
                "headers": {},
                "body": None,
            }
        except (httpx.InvalidURL, httpx.UnsupportedProtocol):
            return {
                "success": False,
                "message": "A URL configurada para o módulo é inválida.",
                "status_code": None,
                "reason_phrase": "",
                "elapsed_ms": _elapsed_ms(started_at),
                "headers": {},
                "body": None,
            }
        except httpx.RequestError:
            return {
                "success": False,
                "message": "Não foi possível conectar ao serviço HTTP configurado.",
                "status_code": None,
                "reason_phrase": "",
                "elapsed_ms": _elapsed_ms(started_at),
                "headers": {},
                "body": None,
            }

        elapsed_ms = _elapsed_ms(started_at)
        status_code = response.status_code
        success = 200 <= status_code <= 399
        if on_response is not None:
            on_response(response, success)
        message = (
            f"Requisição concluída com status {status_code}."
            if success
            else f"A requisição HTTP retornou status {status_code}."
        )
        return {
            "success": success,
            "message": message,
            "status_code": status_code,
            "reason_phrase": response.reason_phrase,
            "elapsed_ms": elapsed_ms,
            "headers": dict(response.headers),
            "body": _decode_response_body(response, vault),
        }

    def get(self, url: str, **kwargs):
        return httpx.get(url, **kwargs)

    def post(self, url: str, **kwargs):
        return httpx.post(url, **kwargs)


class ModuleHttpRequestService:
    def __init__(
        self,
        session_factory=SessionLocal,
        http_service: HttpService | None = None,
        vault_service: VaultService | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.http_service = http_service or HttpService()
        self.vault_service = vault_service or VaultService(session_factory)

    def execute(
        self,
        module_id: int,
        argument: str | None = None,
        *,
        persist_argument: bool = True,
    ) -> dict[str, object]:
        definition = self._load_and_persist_argument(
            module_id,
            argument,
            persist_argument=persist_argument,
        )
        effective_argument = (
            str(argument or "")
            if bool(definition["argument_enabled"])
            else ""
        )
        declared_names = set(definition["vault_keys"])
        vault: dict[str, str] = {}

        def resolve_vault(name: str) -> str:
            if not VAULT_NAME_PATTERN.fullmatch(name):
                raise ValueError("A requisição contém um placeholder de Vault Key inválido.")
            if name not in declared_names:
                raise ValueError(f"A Vault Key {name} não foi declarada em vault_keys pelo módulo.")
            if name not in vault:
                value = self.vault_service.get_value(name)
                if value is None:
                    raise ValueError(f"A Vault Key {name} não foi configurada.")
                vault[name] = value
            return vault[name]

        try:
            return self._execute_request(definition, effective_argument, resolve_vault, vault)
        except Exception as error:
            if vault:
                raise ValueError(str(redact_vault_values(str(error), vault))) from None
            raise

    def _execute_request(self, definition: dict[str, object], effective_argument: str,
                         resolve_vault: Callable[[str], str], vault: dict[str, str]) -> dict[str, object]:
        response_vault = definition["response_vault"]
        if response_vault is not None:
            self.vault_service.ensure_iris_update_allowed(str(response_vault["key"]))
        url = _replace_argument(str(definition["url"]), effective_argument, resolve_vault)
        params = _build_enabled_values(
            list(definition["params"]),
            effective_argument,
            resolve_vault,
        )
        headers = _build_enabled_values(
            list(definition["headers"]),
            effective_argument,
            resolve_vault,
        )
        body_mode = str(definition["body"]["mode"])
        body = _build_body(
            dict(definition["body"]),
            effective_argument,
            resolve_vault,
        )
        response_handler = None
        if response_vault is not None:
            response_handler = lambda response, success: self._capture_response_vault(
                response, dict(response_vault), vault, success,
            )
        result = self.http_service.request(
            str(definition["method"]),
            url,
            params=params,
            headers=headers,
            body=body,
            body_mode=body_mode,
            vault=vault,
            on_response=response_handler,
        )
        return redact_vault_values(result, vault, preserve_result_fields=True)

    def _capture_response_vault(
        self,
        response: httpx.Response,
        mapping: dict[str, str],
        vault: dict[str, str],
        success: bool,
    ) -> None:
        try:
            payload = response.json()
        except ValueError:
            if not success:
                return
            raise ValueError(
                "A resposta HTTP não contém JSON para salvar no Vault."
            ) from None
        value: object = payload
        for part in mapping["path"].split("."):
            if not isinstance(value, dict) or part not in value:
                if not success:
                    return
                raise ValueError(
                    "O caminho JSON configurado para o Vault não foi encontrado na resposta."
                )
            value = value[part]
        if not isinstance(value, str) or not value:
            if not success:
                return
            raise ValueError(
                "A resposta HTTP não contém um valor de texto válido para o Vault."
            )
        key = mapping["key"]
        if key in vault:
            vault[f"__previous_{key}"] = vault[key]
        vault[key] = value
        if success:
            self.vault_service.update_value_by_iris(key, value)

    def save_argument(self, module_id: int, argument: str) -> None:
        db = self.session_factory()
        try:
            request = ModuleHttpRequestRepository(db).get_by_module_id(module_id)
            if request is None:
                raise ValueError("O módulo não possui uma requisição HTTP configurada.")
            build_http_request_detail(request)
            if not request.argument_enabled:
                raise ValueError("Este módulo não utiliza argumento de execução.")
            normalized_argument = str(argument)
            validate_non_sensitive_argument(normalized_argument)
            request.argument = normalized_argument
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def save_definition(
        self,
        module_id: int,
        *,
        method: str,
        url: str,
        argument_enabled: bool,
        argument: str,
        params_json: str,
        authorization_json: str,
        headers_json: str,
        body_json: str,
        scripts_json: str,
        response_vault_json: str | None = None,
    ) -> dict[str, object]:
        if type(argument_enabled) is not bool:
            raise ValueError("O estado do argumento da execução deve ser booleano.")
        text_values = (
            method,
            url,
            argument,
            params_json,
            authorization_json,
            headers_json,
            body_json,
            scripts_json,
        )
        if not all(isinstance(value, str) for value in text_values):
            raise ValueError("Os campos da requisição HTTP devem conter texto.")
        if response_vault_json is not None and not isinstance(response_vault_json, str):
            raise ValueError("A configuração de resposta para o Vault deve conter texto.")
        validate_non_sensitive_argument(argument)

        db = self.session_factory()
        try:
            request = ModuleHttpRequestRepository(db).get_by_module_id(module_id)
            if request is None:
                raise ValueError("O módulo não possui uma requisição HTTP configurada.")
            request.method = method.strip().upper()
            request.url = url.strip()
            request.argument_enabled = argument_enabled
            request.argument = argument
            request.params_json = params_json
            request.authorization_json = authorization_json
            request.headers_json = headers_json
            request.body_json = body_json
            request.scripts_json = scripts_json
            if response_vault_json is not None:
                request.response_vault_json = response_vault_json
            request.is_customized = True
            detail = build_http_request_detail(request)
            request.params_json = _serialize_json_value(detail["params"])
            request.authorization_json = _serialize_json_value(
                detail["authorization"]
            )
            request.headers_json = _serialize_json_value(detail["headers"])
            request.body_json = _serialize_json_value(detail["body"])
            request.scripts_json = _serialize_json_value(detail["scripts"])
            request.response_vault_json = _serialize_json_value(detail["response_vault"])
            db.commit()
            return detail
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def reset_definition_from_manifest(
        self,
        module_id: int,
    ) -> dict[str, object]:
        db = self.session_factory()
        try:
            request = ModuleHttpRequestRepository(db).get_by_module_id(module_id)
            if request is None:
                raise ValueError("O módulo não possui uma requisição HTTP configurada.")
            module = request.module
            if module is None or not module.manifest_directory:
                raise ValueError("O módulo não possui um module.json de origem.")

            folder = Path(module.manifest_directory).resolve()
            manifest_path = (folder / "module.json").resolve()
            try:
                manifest_path.relative_to(folder)
            except ValueError as error:
                raise ValueError("O caminho do module.json é inválido.") from error
            if not manifest_path.is_file():
                raise ValueError("O arquivo module.json não foi encontrado.")
            try:
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                raise ValueError("O arquivo module.json contém JSON inválido.") from error

            manifest = parse_module_manifest(manifest_data, folder)
            if manifest.module_public_key != module.module_public_key:
                raise ValueError(
                    "A chave pública do module.json não corresponde ao módulo atual."
                )
            if manifest.http_request is None:
                raise ValueError("O module.json não possui uma requisição HTTP.")

            saved_argument = request.argument
            apply_manifest_http_request_definition(request, manifest.http_request)
            request.argument = saved_argument
            request.is_customized = False
            detail = build_http_request_detail(request)
            db.commit()
            return detail
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _load_and_persist_argument(
        self,
        module_id: int,
        argument: str | None,
        *,
        persist_argument: bool,
    ) -> dict[str, object]:
        db = self.session_factory()
        try:
            repository = ModuleHttpRequestRepository(db)
            request = repository.get_by_module_id(module_id)
            if request is None:
                raise ValueError("O módulo não possui uma requisição HTTP configurada.")
            definition = build_http_request_detail(request)
            definition["vault_keys"] = load_vault_names(request.module.vault_keys_json)
            if bool(request.argument_enabled):
                normalized_argument = str(argument or "")
                validate_non_sensitive_argument(normalized_argument)
                if persist_argument:
                    request.argument = normalized_argument
            if persist_argument:
                db.commit()
            return definition
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


def build_http_request_detail(request: ModuleHttpRequest) -> dict[str, object]:
    method = str(request.method or "").upper()
    if method not in SUPPORTED_HTTP_METHODS:
        raise ValueError("A configuração HTTP persistida possui um método inválido.")
    url = str(request.url or "").strip()
    validation_url = http_url_for_validation(url)
    if not validation_url.startswith(("http://", "https://")):
        raise ValueError("A configuração HTTP persistida possui uma URL inválida.")
    try:
        parsed_url = httpx.URL(validation_url)
    except httpx.InvalidURL as error:
        raise ValueError(
            "A configuração HTTP persistida possui uma URL inválida."
        ) from error
    if parsed_url.userinfo or SENSITIVE_HTTP_VALUE_PATTERN.search(url):
        raise ValueError(
            "A configuração HTTP persistida contém uma credencial não suportada."
        )
    for query_key, query_value in parse_qsl(
        urlsplit(url).query,
        keep_blank_values=True,
    ):
        _validate_no_sensitive_http_item(query_key, query_value)

    params = _load_http_items(request.params_json, "parâmetros")
    headers = _load_http_items(request.headers_json, "cabeçalhos")
    authorization = _load_json_mapping(
        request.authorization_json,
        "autorização",
    )
    if authorization != {"type": "none"}:
        raise ValueError(
            "A configuração HTTP persistida contém uma autorização não suportada."
        )
    body = _load_http_body(request.body_json)
    response_vault = _load_response_vault(
        request.response_vault_json,
        load_vault_names(request.module.vault_keys_json) if request.module else (),
    )
    scripts = _load_json_mapping(request.scripts_json, "scripts")
    if set(scripts) != {"pre_request", "post_response"} or not all(
        isinstance(scripts[key], str)
        for key in ("pre_request", "post_response")
    ):
        raise ValueError("A configuração de scripts HTTP persistida é inválida.")
    _validate_no_sensitive_values(params, headers, body)
    for script in (scripts["pre_request"], scripts["post_response"]):
        if _looks_like_credential(script):
            raise ValueError(
                "A configuração HTTP persistida contém uma credencial não suportada."
            )
    return {
        "id": request.id,
        "module_id": request.module_id,
        "method": method,
        "url": url,
        "argument_enabled": bool(request.argument_enabled),
        "argument": request.argument or "",
        "params": params,
        "authorization": authorization,
        "headers": headers,
        "body": body,
        "scripts": scripts,
        "response_vault": response_vault,
        "is_customized": bool(request.is_customized),
    }


def apply_manifest_http_request_definition(
    request: ModuleHttpRequest,
    definition: ManifestHttpRequest,
) -> None:
    request.method = definition.method
    request.url = definition.url
    request.argument_enabled = definition.argument_enabled
    request.params_json = _serialize_http_items(definition.params)
    request.authorization_json = json.dumps(
        {"type": definition.authorization_type},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    request.headers_json = _serialize_http_items(definition.headers)
    request.body_json = _serialize_http_body(definition)
    request.response_vault_json = _serialize_json_value(
        {
            "key": definition.response_vault.key,
            "path": definition.response_vault.path,
        } if definition.response_vault else None
    )
    request.scripts_json = json.dumps(
        {
            "pre_request": definition.scripts.pre_request,
            "post_response": definition.scripts.post_response,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _serialize_http_items(items: tuple[ManifestHttpItem, ...]) -> str:
    return json.dumps(
        [
            {
                "key": item.key,
                "value": item.value,
                "description": item.description,
                "enabled": item.enabled,
            }
            for item in items
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _serialize_json_value(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _serialize_http_body(definition: ManifestHttpRequest) -> str:
    content = definition.body.content
    if isinstance(content, tuple):
        serialized_content: object = [
            {
                "key": item.key,
                "value": item.value,
                "description": item.description,
                "enabled": item.enabled,
            }
            for item in content
        ]
    else:
        serialized_content = content
    return json.dumps(
        {
            "mode": definition.body.mode,
            "content": serialized_content,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _load_http_items(raw_value: str, label: str) -> list[dict[str, object]]:
    try:
        value = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError(
            f"A configuração de {label} HTTP contém JSON inválido."
        ) from error
    if not isinstance(value, list):
        raise ValueError(f"A configuração de {label} HTTP deve ser uma lista.")

    items: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "key",
            "value",
            "description",
            "enabled",
        }:
            raise ValueError(f"Um item de {label} HTTP é inválido.")
        if not all(isinstance(item[key], str) for key in ("key", "value", "description")):
            raise ValueError(f"Um item de {label} HTTP possui texto inválido.")
        if type(item["enabled"]) is not bool:
            raise ValueError(f"Um item de {label} HTTP possui estado inválido.")
        items.append(dict(item))
    return items


def _load_http_body(raw_value: str) -> dict[str, object]:
    body = _load_json_mapping(raw_value, "body")
    if set(body) != {"mode", "content"}:
        raise ValueError("A configuração do body HTTP é inválida.")
    mode = body["mode"]
    if not isinstance(mode, str) or mode not in SUPPORTED_HTTP_BODY_MODES:
        raise ValueError("A configuração do body HTTP possui um modo inválido.")
    content = body["content"]
    if mode == "form_urlencoded":
        content = _validate_loaded_http_items(content, "formulário")
    elif not isinstance(content, str):
        raise ValueError("O conteúdo do body HTTP deve ser texto.")
    return {"mode": mode, "content": content}


def _load_response_vault(
    raw_value: str | None,
    vault_keys: tuple[str, ...],
) -> dict[str, str] | None:
    try:
        value = json.loads(raw_value or "null")
    except (TypeError, json.JSONDecodeError):
        raise ValueError("A configuração de resposta para o Vault contém JSON inválido.") from None
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"key", "path"}:
        raise ValueError("A configuração de resposta para o Vault é inválida.")
    key = value["key"]
    path = value["path"]
    if not isinstance(key, str) or key not in vault_keys:
        raise ValueError("A Vault Key de destino da resposta não foi declarada.")
    if (not isinstance(path, str) or len(path) > 200
            or not JSON_RESPONSE_PATH_PATTERN.fullmatch(path)):
        raise ValueError("O caminho JSON da resposta para o Vault é inválido.")
    return {"key": key, "path": path}


def _load_json_mapping(raw_value: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError(
            f"A configuração de {label} HTTP contém JSON inválido."
        ) from error
    if not isinstance(value, dict):
        raise ValueError(f"A configuração de {label} HTTP deve ser um objeto.")
    return value


def _validate_loaded_http_items(
    value: object,
    label: str,
) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError(f"A configuração de {label} HTTP deve ser uma lista.")
    serialized = json.dumps(value, ensure_ascii=False)
    return _load_http_items(serialized, label)


def _build_enabled_values(
    items: list[dict[str, object]],
    argument: str,
    resolve_vault: Callable[[str], str] | None = None,
) -> dict[str, str] | None:
    values = {
        _replace_argument(str(item["key"]), argument, resolve_vault): _replace_argument(
            str(item["value"]),
            argument,
            resolve_vault,
        )
        for item in items
        if bool(item["enabled"]) and str(item["key"])
    }
    return values or None


def _build_body(body: dict[str, object], argument: str,
                resolve_vault: Callable[[str], str] | None = None) -> object | None:
    mode = str(body["mode"])
    content = body["content"]
    if mode == "none":
        return None
    if mode == "raw_text":
        return _replace_argument(str(content), argument, resolve_vault)
    if mode == "raw_json":
        replaced_content = _replace_argument(str(content), argument, resolve_vault, json_mode=True)
        try:
            return json.loads(replaced_content)
        except json.JSONDecodeError as error:
            raise ValueError(
                "O body raw_json ficou com JSON inválido após substituir o argumento."
            ) from None
    if mode == "form_urlencoded":
        return _build_enabled_values(list(content), argument, resolve_vault)
    raise ValueError(f"Modo de body HTTP não suportado: {mode}")


def _replace_argument(value: str, argument: str,
                      resolve_vault: Callable[[str], str] | None = None,
                      *, json_mode: bool = False) -> str:
    def replace(match: re.Match) -> str:
        placeholder = match.group(1)
        if placeholder == "argument":
            return _replace_vault_references(
                argument,
                resolve_vault,
                json_mode=json_mode,
            )
        if not placeholder.startswith("vk."):
            raise ValueError(
                "O placeholder HTTP é inválido. Use {{argument}} ou {{vk.NOME_DA_CHAVE}}."
            )
        if resolve_vault is None:
            raise ValueError("A requisição contém uma Vault Key sem resolução configurada.")
        name = placeholder[3:]
        resolved = resolve_vault(name)
        return json.dumps(resolved, ensure_ascii=False)[1:-1] if json_mode else resolved
    return PLACEHOLDER_PATTERN.sub(replace, value)


def _replace_vault_references(
    value: str,
    resolve_vault: Callable[[str], str] | None,
    *,
    json_mode: bool = False,
) -> str:
    def replace(match: re.Match) -> str:
        placeholder = match.group(1)
        if not placeholder.startswith("vk."):
            return match.group(0)
        if resolve_vault is None:
            raise ValueError("A requisição contém uma Vault Key sem resolução configurada.")
        name = placeholder[3:]
        resolved = resolve_vault(name)
        return json.dumps(resolved, ensure_ascii=False)[1:-1] if json_mode else resolved

    return PLACEHOLDER_PATTERN.sub(replace, value)


def _validate_no_sensitive_values(
    params: list[dict[str, object]],
    headers: list[dict[str, object]],
    body: dict[str, object],
) -> None:
    items = [*params, *headers]
    if body["mode"] == "form_urlencoded":
        items.extend(list(body["content"]))
    for item in items:
        key = str(item["key"])
        value = str(item["value"])
        _validate_no_sensitive_http_item(key, value)
    if isinstance(body["content"], str):
        validate_non_sensitive_http_content(str(body["content"]))


def _validate_no_sensitive_http_item(key: str, value: str) -> None:
    if is_vault_placeholder_value(value):
        return
    if (
        SENSITIVE_HTTP_NAME_PATTERN.search(key)
        or SENSITIVE_HTTP_VALUE_PATTERN.search(value)
    ):
        raise ValueError(
            "A configuração HTTP persistida contém uma credencial não suportada."
        )


def _looks_like_credential(value: str) -> bool:
    return bool(
        SENSITIVE_HTTP_VALUE_PATTERN.search(value)
        or re.search(
            r"(?:api[._\- ]*key|authorization|credential|password|secret|senha|token)"
            r"\s*[:=]\s*\S+",
            value,
            re.IGNORECASE,
        )
    )


def validate_non_sensitive_argument(value: str | None) -> None:
    """Impede persistência aparente de credenciais em argumentos de texto."""
    normalized_value = str(value or "")
    if normalized_value and _looks_like_credential(normalized_value):
        raise ValueError(
            "O argumento parece conter uma credencial e não pode ser salvo."
        )


def _decode_response_body(response: httpx.Response, vault: dict[str, str] | None = None) -> object:
    body_text = str(redact_vault_values(response.text, vault or {}))
    if len(body_text) > MAX_RESPONSE_BODY_CHARACTERS:
        return body_text[:MAX_RESPONSE_BODY_CHARACTERS] + TRUNCATED_BODY_SUFFIX
    if not body_text:
        return ""
    try:
        return redact_vault_values(response.json(), vault or {})
    except ValueError:
        return body_text


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))
