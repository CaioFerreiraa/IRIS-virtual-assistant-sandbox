from collections.abc import Iterator
from contextlib import contextmanager
import hashlib
import sys


VAULT_SERVICE_NAME = "IRIS.Vault"
VAULT_USERNAME = "master-key-v1"


class WindowsVaultKeyStore:
    """Acessa somente a chave mestra, no contexto do usuário do Windows."""

    @staticmethod
    def _require_windows() -> None:
        if sys.platform != "win32":
            raise ValueError(
                "A criptografia das Vault Keys está indisponível neste sistema. "
                "Use a IRIS no Windows com o usuário que possui a chave mestra."
            )

    def _backend(self):
        self._require_windows()
        from keyring.backends.Windows import WinVaultKeyring

        backend = WinVaultKeyring()
        backend.persist = "local machine"
        return backend

    def read(self) -> str | None:
        self._require_windows()
        try:
            return self._backend().get_password(VAULT_SERVICE_NAME, VAULT_USERNAME)
        except Exception:
            raise ValueError(
                "Não foi possível ler a chave mestra no Windows Credential Manager. "
                "Verifique a instalação do keyring e o acesso do usuário do Windows."
            ) from None

    def write(self, key: str) -> None:
        self._require_windows()
        try:
            self._backend().set_password(VAULT_SERVICE_NAME, VAULT_USERNAME, key)
        except Exception:
            raise ValueError(
                "Não foi possível gravar a chave mestra no Windows Credential Manager. "
                "Verifique o acesso do usuário do Windows e tente novamente."
            ) from None

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Serializa instâncias da IRIS, inclusive em sessões do mesmo usuário."""
        self._require_windows()
        # Imports nativos e handles existem apenas durante uma operação criptográfica.
        import ctypes
        from ctypes import wintypes

        handle = None
        acquired = False
        try:
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
            kernel.CreateMutexW.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel.WaitForSingleObject.restype = wintypes.DWORD
            kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
            kernel.ReleaseMutex.restype = wintypes.BOOL
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle.restype = wintypes.BOOL
            security = ctypes.WinDLL("secur32", use_last_error=True)
            security.GetUserNameExW.argtypes = [ctypes.c_int, wintypes.LPWSTR,
                                               ctypes.POINTER(wintypes.ULONG)]
            security.GetUserNameExW.restype = wintypes.BOOLEAN
            account = ctypes.create_unicode_buffer(1024)
            size = wintypes.ULONG(len(account))
            if not security.GetUserNameExW(2, account, ctypes.byref(size)):
                raise OSError
            # NameSamCompatible (2) identifica DOMÍNIO\\usuário, sem depender do cwd.
            identity = hashlib.sha256(account.value.casefold().encode("utf-8")).hexdigest()
            name = f"Global\\{VAULT_SERVICE_NAME}.{VAULT_USERNAME}.{identity}"
            handle = kernel.CreateMutexW(None, False, name)
            if not handle:
                raise OSError
            # WAIT_ABANDONED também concede posse após a interrupção de outro processo.
            acquired = kernel.WaitForSingleObject(handle, 5000) in (0, 0x80)
            if not acquired:
                raise OSError
        except Exception:
            if handle:
                kernel.CloseHandle(handle)
            raise ValueError(
                "Não foi possível obter acesso exclusivo à chave mestra do Vault. "
                "Aguarde outras operações da IRIS e tente novamente."
            ) from None
        try:
            yield
        finally:
            if acquired:
                kernel.ReleaseMutex(handle)
            kernel.CloseHandle(handle)
