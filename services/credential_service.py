import os


class CredentialService:
    def get(self, name: str, default: str | None = None) -> str | None:
        return os.getenv(name, default)
