from __future__ import annotations

import json
from pathlib import Path
import re
from time import perf_counter
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import httpx

from database.db import SessionLocal
from database.models import ModuleHttpRequest
from repositories.module_http_request_repository import ModuleHttpRequestRepository
from services.module_manifest import (
    ManifestHttpItem,
    ManifestHttpRequest,
    SENSITIVE_HTTP_NAME_PATTERN,
    SENSITIVE_HTTP_VALUE_PATTERN,
    SUPPORTED_HTTP_BODY_MODES,
    SUPPORTED_HTTP_METHODS,
    parse_module_manifest,
)


REQUEST_TIMEOUT_SECONDS = 30.0
MAX_RESPONSE_BODY_CHARACTERS = 100_000
TRUNCATED_BODY_SUFFIX = "\n\n[Resposta truncada pela IRIS.]"


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
            "body": _decode_response_body(response),
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
    ) -> None:
        self.session_factory = session_factory
        self.http_service = http_service or HttpService()

    def execute(
        self,
        module_id: int,
        argument: str | None = None,
    ) -> dict[str, object]:
        definition = self._load_and_persist_argument(module_id, argument)
        effective_argument = (
            str(argument or "")
            if bool(definition["argument_enabled"])
            else ""
        )
        url = _replace_argument(str(definition["url"]), effective_argument)
        params = _build_enabled_values(
            list(definition["params"]),
            effective_argument,
        )
        headers = _build_enabled_values(
            list(definition["headers"]),
            effective_argument,
        )
        body_mode = str(definition["body"]["mode"])
        body = _build_body(
            dict(definition["body"]),
            effective_argument,
        )
        return self.http_service.request(
            str(definition["method"]),
            url,
            params=params,
            headers=headers,
            body=body,
            body_mode=body_mode,
        )

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
            if _looks_like_credential(normalized_argument):
                raise ValueError(
                    "O argumento parece conter uma credencial e não pode ser salvo."
                )
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
        if argument and _looks_like_credential(argument):
            raise ValueError(
                "O argumento parece conter uma credencial e não pode ser salvo."
            )

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
            request.is_customized = True
            detail = build_http_request_detail(request)
            request.params_json = _serialize_json_value(detail["params"])
            request.authorization_json = _serialize_json_value(
                detail["authorization"]
            )
            request.headers_json = _serialize_json_value(detail["headers"])
            request.body_json = _serialize_json_value(detail["body"])
            request.scripts_json = _serialize_json_value(detail["scripts"])
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
    ) -> dict[str, object]:
        db = self.session_factory()
        try:
            repository = ModuleHttpRequestRepository(db)
            request = repository.get_by_module_id(module_id)
            if request is None:
                raise ValueError("O módulo não possui uma requisição HTTP configurada.")
            definition = build_http_request_detail(request)
            if bool(request.argument_enabled):
                normalized_argument = str(argument or "")
                if _looks_like_credential(normalized_argument):
                    raise ValueError(
                        "O argumento parece conter uma credencial e não pode ser salvo."
                    )
                request.argument = normalized_argument
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
    if not url.startswith(("http://", "https://")):
        raise ValueError("A configuração HTTP persistida possui uma URL inválida.")
    try:
        parsed_url = httpx.URL(url)
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
) -> dict[str, str] | None:
    values = {
        _replace_argument(str(item["key"]), argument): _replace_argument(
            str(item["value"]),
            argument,
        )
        for item in items
        if bool(item["enabled"]) and str(item["key"])
    }
    return values or None


def _build_body(body: dict[str, object], argument: str) -> object | None:
    mode = str(body["mode"])
    content = body["content"]
    if mode == "none":
        return None
    if mode == "raw_text":
        return _replace_argument(str(content), argument)
    if mode == "raw_json":
        replaced_content = _replace_argument(str(content), argument)
        try:
            return json.loads(replaced_content)
        except json.JSONDecodeError as error:
            raise ValueError(
                "O body raw_json ficou com JSON inválido após substituir o argumento."
            ) from error
    if mode == "form_urlencoded":
        return _build_enabled_values(list(content), argument)
    raise ValueError(f"Modo de body HTTP não suportado: {mode}")


def _replace_argument(value: str, argument: str) -> str:
    return value.replace("{{argument}}", argument)


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
    if isinstance(body["content"], str) and SENSITIVE_HTTP_VALUE_PATTERN.search(
        str(body["content"])
    ):
        raise ValueError(
            "A configuração HTTP persistida contém uma credencial não suportada."
        )
    if isinstance(body["content"], str) and re.search(
        r"[\"']?(?:api[._\- ]*key|authorization|credential|password|secret|senha|token)"
        r"[\"']?\s*[:=]",
        str(body["content"]),
        re.IGNORECASE,
    ):
        raise ValueError(
            "A configuração HTTP persistida contém uma credencial não suportada."
        )


def _validate_no_sensitive_http_item(key: str, value: str) -> None:
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


def _decode_response_body(response: httpx.Response) -> object:
    body_text = response.text
    if len(body_text) > MAX_RESPONSE_BODY_CHARACTERS:
        return body_text[:MAX_RESPONSE_BODY_CHARACTERS] + TRUNCATED_BODY_SUFFIX
    if not body_text:
        return ""
    try:
        return response.json()
    except ValueError:
        return body_text


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))
