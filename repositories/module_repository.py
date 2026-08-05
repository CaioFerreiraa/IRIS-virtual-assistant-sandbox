from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import Module


class ModuleRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_modules(self) -> list[Module]:
        modules = self.db.query(Module).all()
        return sorted(modules, key=self.get_module_path)

    def list_module_paths(self) -> list[str]:
        return [self.get_module_path(module) for module in self.list_modules()]

    def list_module_options(self) -> list[dict[str, str | bool]]:
        return [
            {
                "path": self.get_module_path(module),
                "is_executable": bool(module.is_executable),
            }
            for module in self.list_modules()
        ]

    def list_call_names(self) -> list[str]:
        """Retorna nomes de chamada e aliases sem duplicatas para contexto de voz."""
        rows = self.db.query(Module.call_name, Module.custom_call_name).all()
        names: list[str] = []
        seen: set[str] = set()
        for call_name, custom_call_name in rows:
            for value in (call_name, custom_call_name):
                normalized = (value or "").strip()
                lookup_key = normalized.casefold()
                if normalized and lookup_key not in seen:
                    seen.add(lookup_key)
                    names.append(normalized)
        return names

    def list_root_module_paths(self) -> list[str]:
        modules = self.db.query(Module).filter(Module.parent_module_id.is_(None)).all()
        return [self.get_module_path(module) for module in sorted(modules, key=self.get_module_path)]

    def get_module_path(self, module: Module) -> str:
        names = [module.name]
        parent = module.parent_module
        while parent is not None:
            names.append(parent.name)
            parent = parent.parent_module
        return " / ".join(reversed(names))

    def find_module(
        self,
        call_name: str,
        parent_module_id: int | None = None,
    ) -> Module | None:
        return (
            self.db.query(Module)
            .filter(
                func.lower(Module.call_name) == call_name.lower(),
                Module.parent_module_id == parent_module_id,
            )
            .first()
        )

    def create_module(
        self,
        name: str,
        call_name: str,
        custom_call_name: str | None = None,
        description: str = "",
        parent_module_id: int | None = None,
    ) -> Module:
        module = Module(
            name=name,
            call_name=call_name,
            custom_call_name=custom_call_name,
            description=description,
            parent_module_id=parent_module_id,
        )
        self.db.add(module)
        self.db.commit()
        self.db.refresh(module)
        return module

    def find_by_path(self, module_path: str) -> Module | None:
        parts = [part.strip().lower() for part in module_path.split("/") if part.strip()]

        if not parts:
            return None

        parent_id = None
        module = None

        for part in parts:
            module = (
                self.db.query(Module)
                .filter(
                    func.lower(Module.name) == part,
                    Module.parent_module_id == parent_id,
                )
                .first()
            )

            if module is None:
                module = (
                    self.db.query(Module)
                    .filter(
                        func.lower(Module.call_name) == part,
                        Module.parent_module_id == parent_id,
                    )
                    .first()
                )

            if module is None:
                return None

            parent_id = module.id

        return module
