from pathlib import Path
from threading import Lock

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from database.db import SessionLocal
from database.models import VaultKey
from repositories.vault_repository import VaultRepository
from services.vault_key_store import WindowsVaultKeyStore
from util.vault_names import normalize_vault_name


VAULT_KEY_PATH = Path(__file__).resolve().parents[1] / ".iris_vault.key"
_MASTER_KEY_LOCK = Lock()


class VaultService:
    def __init__(self, session_factory=SessionLocal, key_path: Path | None = None,
                 *, key_store: WindowsVaultKeyStore | None = None) -> None:
        self.session_factory = session_factory
        # key_path aponta exclusivamente para o arquivo legado a ser migrado.
        self.key_path = Path(key_path) if key_path is not None else VAULT_KEY_PATH
        self.key_store = key_store if key_store is not None else WindowsVaultKeyStore()

    def create(self, name: str, value: str | None, description: str | None = None,
               allow_iris_update: bool = False) -> None:
        name = normalize_vault_name(name)
        self._validate_fields(value, description, allow_iris_update, allow_empty=True)
        with self.session_factory() as db:
            repository = VaultRepository(db)
            if repository.get_by_name(name) is not None:
                raise ValueError(f"A Vault Key {name} já está cadastrada.")
            encrypted_value = (
                self._encrypt(value, allow_create=not repository.has_encrypted_values())
                if value else None
            )
            try:
                repository.save(VaultKey(name=name, description=description or "",
                                         encrypted_value=encrypted_value,
                                         allow_iris_update=allow_iris_update))
            except IntegrityError:
                db.rollback()
                raise ValueError(f"A Vault Key {name} já está cadastrada.") from None
            except SQLAlchemyError:
                db.rollback()
                raise ValueError("Não foi possível salvar a Vault Key.") from None

    def list_metadata(self) -> list[dict[str, object]]:
        with self.session_factory() as db:
            repository = VaultRepository(db)
            keys = repository.list_metadata()
            for key in keys:
                key["modules"] = repository.modules_using(str(key["name"]))
            return keys

    def update(self, key_id: int, *, description: str | None = None,
               new_value: str | None = None, allow_iris_update: bool = False,
               keep_existing_value: bool = False) -> None:
        self._validate_fields(new_value, description, allow_iris_update, allow_empty=True)
        with self.session_factory() as db:
            record = self._require_record(VaultRepository(db).get_by_id(key_id))
            record.description = description or ""
            record.allow_iris_update = allow_iris_update
            if not keep_existing_value:
                record.encrypted_value = (
                    self._encrypt(
                        new_value,
                        allow_create=not VaultRepository(db).has_encrypted_values(),
                    )
                    if new_value else None
                )
            self._save(db, record)

    def delete(self, key_id: int) -> None:
        with self.session_factory() as db:
            repository = VaultRepository(db)
            record = self._require_record(repository.get_by_id(key_id))
            try:
                repository.delete(record)
            except SQLAlchemyError:
                db.rollback()
                raise ValueError("Não foi possível excluir a Vault Key.") from None

    def get_value(self, name: str) -> str | None:
        name = normalize_vault_name(name)
        with self.session_factory() as db:
            record = VaultRepository(db).get_by_name(name)
            return self._decrypt(record) if record is not None and record.encrypted_value else None

    def declared_names(self, module_id: int) -> tuple[str, ...]:
        with self.session_factory() as db:
            return VaultRepository(db).declared_names(module_id)

    def available_names(self, module_id: int) -> tuple[str, ...]:
        """Lista referências configuradas sem descriptografar seus valores."""
        with self.session_factory() as db:
            return VaultRepository(db).available_names(module_id)

    def resolve_module_keys(self, module_id: int) -> dict[str, str]:
        with self.session_factory() as db:
            repository = VaultRepository(db)
            values = {}
            for name in repository.declared_names(module_id):
                record = repository.get_by_name(name)
                if record is not None and record.encrypted_value:
                    values[name] = self._decrypt(record)
            return values

    def modules_using(self, name: str) -> list[dict[str, object]]:
        with self.session_factory() as db:
            return VaultRepository(db).modules_using(normalize_vault_name(name))

    def update_value_by_iris(self, name: str, new_value: str) -> None:
        name = normalize_vault_name(name)
        self._validate_fields(new_value, None, False)
        with self.session_factory() as db:
            record = self._require_record(VaultRepository(db).get_by_name(name))
            if not record.allow_iris_update:
                raise ValueError(f"A IRIS não tem permissão para alterar a Vault Key {name}.")
            record.encrypted_value = self._encrypt(
                new_value,
                allow_create=not VaultRepository(db).has_encrypted_values(),
            )
            self._save(db, record)

    def ensure_iris_update_allowed(self, name: str) -> None:
        name = normalize_vault_name(name)
        with self.session_factory() as db:
            record = VaultRepository(db).get_by_name(name)
            if record is None:
                raise ValueError(f"Cadastre a Vault Key {name} antes de executar o módulo.")
            if not record.allow_iris_update:
                raise ValueError(f"Ative 'IRIS pode alterar' na Vault Key {name}.")

    def _fernet(self, *, allow_create: bool = False) -> Fernet:
        with _MASTER_KEY_LOCK, self.key_store.locked():
            stored_key = self.key_store.read()
            cipher = self._validate_master_key(stored_key) if stored_key is not None else None
            legacy_key = self._read_legacy_key()
            if legacy_key is not None:
                legacy_cipher = self._validate_master_key(legacy_key, legacy=True)
                if stored_key is not None and stored_key != legacy_key:
                    raise ValueError(
                        "Há conflito entre a chave mestra do Windows Credential Manager "
                        "e .iris_vault.key. Nenhuma chave foi substituída ou removida. "
                        "Verifique a origem do banco e das chaves antes de tentar novamente."
                    )
                self._validate_legacy_values(legacy_cipher)
                if stored_key is None:
                    self.key_store.write(legacy_key)
                self._confirm_master_key(legacy_key)
                try:
                    self.key_path.unlink()
                except OSError:
                    raise ValueError(
                        "A chave mestra foi confirmada no Windows Credential Manager, "
                        "mas não foi possível remover .iris_vault.key. "
                        "Verifique as permissões do arquivo e tente novamente."
                    ) from None
                return legacy_cipher
            if cipher is not None:
                return cipher
            # Consulte novamente sob o bloqueio: allow_create pode vir de outra thread.
            with self.session_factory() as db:
                has_values = VaultRepository(db).has_encrypted_values()
            if not allow_create or has_values:
                raise ValueError(
                    "A chave mestra do Vault está indisponível. Use o usuário do Windows "
                    "que possui a credencial original ou restaure a chave legada original "
                    "para migração. Uma nova chave não recupera os valores existentes."
                )
            key = Fernet.generate_key().decode("ascii")
            self.key_store.write(key)
            self._confirm_master_key(key)
            return Fernet(key)

    def _read_legacy_key(self) -> str | None:
        try:
            return self.key_path.read_bytes().decode("ascii")
        except FileNotFoundError:
            return None
        except OSError:
            raise ValueError("Não foi possível acessar .iris_vault.key para migração. Verifique as permissões do arquivo.") from None
        except UnicodeError:
            raise ValueError("O arquivo legado .iris_vault.key é inválido. Restaure a chave original.") from None

    @staticmethod
    def _validate_master_key(key: str, *, legacy: bool = False) -> Fernet:
        try:
            return Fernet(key)
        except (ValueError, TypeError):
            source = "O arquivo legado .iris_vault.key" if legacy else "A credencial do Windows Credential Manager"
            raise ValueError(f"{source} contém uma chave Fernet inválida. Restaure a chave original.") from None

    def _validate_legacy_values(self, cipher: Fernet) -> None:
        try:
            with self.session_factory() as db:
                for value in VaultRepository(db).list_encrypted_values():
                    cipher.decrypt(value.encode("ascii"))
        except (InvalidToken, UnicodeError, TypeError):
            raise ValueError(
                "Não foi possível validar os valores do Vault com .iris_vault.key. "
                "O arquivo foi preservado. Verifique a chave original e a integridade do banco."
            ) from None
        except SQLAlchemyError:
            raise ValueError("Não foi possível consultar os valores do Vault para migração. O arquivo legado foi preservado.") from None

    def _confirm_master_key(self, expected_key: str) -> None:
        if self.key_store.read() != expected_key:
            raise ValueError(
                "Não foi possível confirmar a chave mestra no Windows Credential Manager. "
                "Nenhum valor foi alterado e o arquivo legado, se existir, foi preservado. "
                "Verifique a credencial antes de tentar novamente."
            )

    def _encrypt(self, value: str, *, allow_create: bool) -> str:
        return self._fernet(allow_create=allow_create).encrypt(value.encode("utf-8")).decode("ascii")

    def _decrypt(self, record: VaultKey) -> str:
        try:
            return self._fernet().decrypt(record.encrypted_value.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeError):
            raise ValueError(f"Não foi possível descriptografar a Vault Key {record.name}. Verifique a chave mestra original e a integridade do banco ou cadastre o valor novamente.") from None

    def _save(self, db, record: VaultKey) -> None:
        try:
            VaultRepository(db).save(record)
        except SQLAlchemyError:
            db.rollback()
            raise ValueError("Não foi possível atualizar a Vault Key.") from None

    @staticmethod
    def _require_record(record: VaultKey | None) -> VaultKey:
        if record is None:
            raise ValueError("A Vault Key não foi encontrada. Atualize a lista.")
        return record

    @staticmethod
    def _validate_fields(value: str | None, description: str | None,
                         allow_iris_update: bool, *, allow_empty: bool = False) -> None:
        if (value is not None and not isinstance(value, str)) or (not allow_empty and not value):
            raise ValueError("Informe o valor da Vault Key.")
        if description is not None and not isinstance(description, str):
            raise ValueError("A descrição da Vault Key deve conter texto.")
        if type(allow_iris_update) is not bool:
            raise ValueError("A permissão de alteração pela IRIS deve ser booleana.")
