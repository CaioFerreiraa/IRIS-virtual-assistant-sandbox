from __future__ import annotations

import hashlib
import importlib
import importlib.util
import sys
from threading import RLock
from pathlib import Path
from types import ModuleType


_MODULE_CACHE: dict[tuple[str, int], ModuleType] = {}
_CACHE_LOCK = RLock()


def load_python_entrypoint(
    entrypoint: str | Path,
    module_public_key: str = "module",
) -> ModuleType:
    """Carrega entry point por arquivo ou mantém compatibilidade com imports legados."""
    entrypoint_path = Path(entrypoint)
    if entrypoint_path.is_file():
        resolved_path = entrypoint_path.resolve()
        cache_key = (str(resolved_path), resolved_path.stat().st_mtime_ns)
        with _CACHE_LOCK:
            cached_module = _MODULE_CACHE.get(cache_key)
            if cached_module is not None:
                return cached_module
        path_digest = hashlib.sha256(str(resolved_path).encode("utf-8")).hexdigest()[:16]
        safe_key = module_public_key.replace(".", "_").replace("-", "_")
        import_name = f"iris_installed_{safe_key}_{path_digest}"
        spec = importlib.util.spec_from_file_location(import_name, resolved_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Não foi possível preparar o entry point: {resolved_path}")

        sys.modules.pop(import_name, None)
        loaded_module = importlib.util.module_from_spec(spec)
        sys.modules[import_name] = loaded_module
        try:
            spec.loader.exec_module(loaded_module)
        except Exception:
            sys.modules.pop(import_name, None)
            raise
        with _CACHE_LOCK:
            stale_keys = [key for key in _MODULE_CACHE if key[0] == str(resolved_path)]
            for stale_key in stale_keys:
                _MODULE_CACHE.pop(stale_key, None)
            _MODULE_CACHE[cache_key] = loaded_module
        return loaded_module

    module_path = str(entrypoint)
    module_path = module_path[:-3] if module_path.endswith(".py") else module_path
    module_path = module_path.replace("\\", ".").replace("/", ".")
    return importlib.import_module(module_path)
