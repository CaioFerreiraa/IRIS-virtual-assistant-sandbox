from sqlalchemy.orm import Session

from database.models import Module, VaultKey
from util.vault_names import load_vault_names


class VaultRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_name(self, name: str) -> VaultKey | None:
        return self.db.query(VaultKey).filter_by(name=name).one_or_none()

    def get_by_id(self, key_id: int) -> VaultKey | None:
        return self.db.get(VaultKey, key_id)

    def list_metadata(self) -> list[dict[str, object]]:
        rows = self.db.query(
            VaultKey.id, VaultKey.name, VaultKey.description,
            VaultKey.allow_iris_update, VaultKey.created_date, VaultKey.edited_date,
            VaultKey.encrypted_value.is_not(None).label("has_value"),
        ).order_by(VaultKey.name).all()
        return [dict(row._mapping) for row in rows]

    def has_keys(self) -> bool:
        return self.db.query(VaultKey.id).first() is not None

    def has_encrypted_values(self) -> bool:
        return self.db.query(VaultKey.id).filter(
            VaultKey.encrypted_value.is_not(None)
        ).first() is not None

    def modules_using(self, name: str) -> list[dict[str, object]]:
        rows = self.db.query(Module.id, Module.name, Module.vault_keys_json).order_by(Module.name, Module.id).all()
        return [{"id": row.id, "name": row.name} for row in rows if name in load_vault_names(row.vault_keys_json)]

    def declared_names(self, module_id: int) -> tuple[str, ...]:
        module = self.db.get(Module, module_id)
        if module is None:
            raise ValueError("O módulo não foi encontrado.")
        return load_vault_names(module.vault_keys_json)

    def available_names(self, module_id: int) -> tuple[str, ...]:
        declared = self.declared_names(module_id)
        if not declared:
            return ()
        configured = {
            row.name
            for row in self.db.query(VaultKey.name).filter(
                VaultKey.name.in_(declared),
                VaultKey.encrypted_value.is_not(None),
            ).all()
        }
        return tuple(name for name in declared if name in configured)

    def save(self, record: VaultKey) -> None:
        self.db.add(record)
        self.db.commit()

    def delete(self, record: VaultKey) -> None:
        self.db.delete(record)
        self.db.commit()
