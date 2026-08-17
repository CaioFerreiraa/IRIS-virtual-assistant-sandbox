from itertools import product

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import Module, ModuleVariableDefinition, ModuleVariableValue


class ModuleRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_modules(self, *, available_only: bool = False) -> list[Module]:
        query = self.db.query(Module)
        if available_only:
            query = query.filter(Module.is_available.is_(True))
        modules = query.all()
        return sorted(modules, key=self.get_module_path)

    def list_module_paths(self) -> list[str]:
        return [
            self.get_module_path(module)
            for module in self.list_modules(available_only=True)
        ]

    def list_module_options(
        self,
        *,
        available_only: bool = True,
    ) -> list[dict[str, object]]:
        options: list[dict[str, object]] = []
        for module in self.list_modules(available_only=available_only):
            path = self.get_module_path(module)
            command_paths = self.get_module_command_paths(module)
            options.append(
                {
                    "module_id": module.id,
                    "path": path,
                    "name": module.name,
                    "call_name": module.call_name,
                    "custom_call_name": module.custom_call_name,
                    "description": module.description or "",
                    "icon": module.icon or "extension",
                    "module_public_key": module.module_public_key,
                    "parent_module_id": module.parent_module_id,
                    "is_executable": bool(module.is_executable),
                    "is_available": bool(module.is_available),
                    "command_paths": command_paths,
                    "search_text": " ".join(
                        dict.fromkeys(
                            [
                                path,
                                *command_paths,
                                module.call_name,
                                module.custom_call_name or "",
                            ]
                        )
                    ),
                }
            )
        return options

    def list_call_names(self) -> list[str]:
        """Retorna nomes originais e personalizados sem duplicatas."""
        rows = (
            self.db.query(Module.call_name, Module.custom_call_name)
            .filter(Module.is_available.is_(True))
            .all()
        )
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
        modules = (
            self.db.query(Module)
            .filter(
                Module.parent_module_id.is_(None),
                Module.is_available.is_(True),
            )
            .all()
        )
        return [
            self.get_module_path(module)
            for module in sorted(modules, key=self.get_module_path)
        ]

    def get_module_path(self, module: Module) -> str:
        names: list[str] = []
        current: Module | None = module
        visited_ids: set[int] = set()
        while current is not None and current.id not in visited_ids:
            visited_ids.add(current.id)
            names.append(current.name)
            current = current.parent_module
        if current is not None:
            names.append("Hierarquia inválida")
        return " / ".join(reversed(names))

    def get_module_command_paths(self, module: Module) -> list[str]:
        hierarchy: list[Module] = []
        current: Module | None = module
        visited_ids: set[int] = set()
        while current is not None and current.id not in visited_ids:
            visited_ids.add(current.id)
            hierarchy.append(current)
            current = current.parent_module
        hierarchy.reverse()

        name_choices = [
            tuple(
                dict.fromkeys(
                    value.strip()
                    for value in (
                        item.call_name,
                        item.custom_call_name,
                        item.name,
                    )
                    if value and value.strip()
                )
            )
            for item in hierarchy
        ]
        paths = [" / ".join(parts) for parts in product(*name_choices)]
        return list(dict.fromkeys(paths))

    def get_by_id(self, module_id: int) -> Module | None:
        return self.db.query(Module).filter(Module.id == module_id).one_or_none()

    def get_by_public_key(self, module_public_key: str) -> Module | None:
        return (
            self.db.query(Module)
            .filter(Module.module_public_key == module_public_key)
            .one_or_none()
        )

    def list_descendants(self, module_id: int) -> list[Module]:
        descendants: list[Module] = []
        pending_ids = [module_id]
        visited_ids = {module_id}
        while pending_ids:
            children = (
                self.db.query(Module)
                .filter(Module.parent_module_id.in_(pending_ids))
                .all()
            )
            pending_ids = []
            for child in children:
                if child.id in visited_ids:
                    continue
                visited_ids.add(child.id)
                descendants.append(child)
                pending_ids.append(child.id)
        return descendants

    def get_breadcrumb(self, module: Module) -> list[dict[str, int | str]]:
        items: list[dict[str, int | str]] = []
        current: Module | None = module
        visited_ids: set[int] = set()
        while current is not None and current.id not in visited_ids:
            visited_ids.add(current.id)
            items.append({"id": current.id, "name": current.name})
            current = current.parent_module
        return list(reversed(items))

    def list_variable_definitions(
        self,
        module_id: int,
        *,
        active_only: bool = True,
    ) -> list[ModuleVariableDefinition]:
        query = self.db.query(ModuleVariableDefinition).filter(
            ModuleVariableDefinition.module_id == module_id
        )
        if active_only:
            query = query.filter(ModuleVariableDefinition.is_active.is_(True))
        return query.order_by(ModuleVariableDefinition.display_order).all()

    def get_variable_value(
        self,
        variable_definition_id: int,
    ) -> ModuleVariableValue | None:
        return (
            self.db.query(ModuleVariableValue)
            .filter(
                ModuleVariableValue.variable_definition_id
                == variable_definition_id
            )
            .one_or_none()
        )

    def find_modules_by_command(self, command: str) -> list[Module]:
        normalized_command = command.strip().casefold()
        if not normalized_command:
            return []
        return [
            module
            for module in self.list_modules(available_only=True)
            if normalized_command
            in {
                path.casefold()
                for path in (
                    self.get_module_path(module),
                    *self.get_module_command_paths(module),
                )
            }
        ]

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
        module_public_key: str,
        name: str,
        call_name: str,
        custom_call_name: str | None = None,
        description: str = "",
        icon: str = "extension",
        parent_module_id: int | None = None,
    ) -> Module:
        module = Module(
            module_public_key=module_public_key,
            name=name,
            call_name=call_name,
            custom_call_name=custom_call_name,
            description=description,
            icon=icon,
            parent_module_id=parent_module_id,
        )
        self.db.add(module)
        self.db.commit()
        self.db.refresh(module)
        return module

    def find_by_path(self, module_path: str) -> Module | None:
        exact_matches = self.find_modules_by_command(module_path)
        if len(exact_matches) == 1:
            return exact_matches[0]
        if len(exact_matches) > 1:
            raise ValueError(
                "O comando corresponde a mais de um módulo. Escolha um item da lista."
            )

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
                    Module.is_available.is_(True),
                )
                .first()
            )
            if module is None:
                module = (
                    self.db.query(Module)
                    .filter(
                        func.lower(Module.call_name) == part,
                        Module.parent_module_id == parent_id,
                        Module.is_available.is_(True),
                    )
                    .first()
                )
            if module is None:
                module = (
                    self.db.query(Module)
                    .filter(
                        func.lower(Module.custom_call_name) == part,
                        Module.parent_module_id == parent_id,
                        Module.is_available.is_(True),
                    )
                    .first()
                )
            if module is None:
                return None
            parent_id = module.id
        return module
