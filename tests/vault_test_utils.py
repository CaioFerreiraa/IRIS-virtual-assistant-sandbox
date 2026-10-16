from contextlib import nullcontext

from services.vault_key_store import WindowsVaultKeyStore


class MemoryKeyStore(WindowsVaultKeyStore):
    """Armazenamento isolado: nunca acessa credenciais do Windows."""

    def __init__(self):
        self.key = None
        self.writes = 0

    def read(self):
        return self.key

    def write(self, key):
        self.writes += 1
        self.key = key

    def locked(self):
        return nullcontext()
