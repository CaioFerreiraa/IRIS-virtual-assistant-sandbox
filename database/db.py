from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, func, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///iris.db"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODULES_ROOT = PROJECT_ROOT / "modules" / "default_modules"

engine = create_engine(DATABASE_URL, echo=True)


def enable_sqlite_foreign_keys(target_engine: Engine) -> None:
    """Ativa chaves estrangeiras em toda conexão SQLite do engine informado."""
    if target_engine.url.get_backend_name() != "sqlite":
        return

    @event.listens_for(target_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


enable_sqlite_foreign_keys(engine)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()


DEFAULT_MODULE_TREE = (
    {
        "module_public_key": "iris.assistant",
        "name": "Assistente",
        "call_name": "assistente",
        "icon": "auto_awesome",
        "description": "Módulo principal da IRIS.",
        "readme_path": DEFAULT_MODULES_ROOT / "assistant" / "README.md",
    },
    {
        "module_public_key": "iris.calendar",
        "name": "Agenda",
        "call_name": "agenda",
        "icon": "calendar_month",
        "description": "Módulo responsável por compromissos e eventos.",
        "readme_path": DEFAULT_MODULES_ROOT / "calendar" / "README.md",
    },
    {
        "module_public_key": "iris.files",
        "name": "Arquivos",
        "call_name": "arquivos",
        "icon": "folder",
        "description": "Módulo responsável por localizar e organizar arquivos.",
        "readme_path": DEFAULT_MODULES_ROOT / "files" / "README.md",
    },
    {
        "module_public_key": "iris.browser",
        "name": "Navegador",
        "call_name": "navegador",
        "icon": "language",
        "description": "Módulo responsável por navegação e pesquisa.",
        "readme_path": DEFAULT_MODULES_ROOT / "browser" / "README.md",
    },
    {
        "module_public_key": "iris.system",
        "name": "Sistema",
        "call_name": "sistema",
        "icon": "computer",
        "description": "Módulo responsável por comandos do sistema.",
        "readme_path": DEFAULT_MODULES_ROOT / "system" / "README.md",
    },
    {
        "module_public_key": "iris.images",
        "name": "Imagens",
        "call_name": "imagens",
        "icon": "image",
        "description": "Módulo responsável por recursos de imagem.",
        "readme_path": DEFAULT_MODULES_ROOT / "images" / "README.md",
        "children": (
            {
                "module_public_key": "iris.images.numbers",
                "name": "Números",
                "call_name": "numeros",
                "icon": "pin",
                "description": "Submódulo de imagens com números.",
                "readme_path": DEFAULT_MODULES_ROOT / "images" / "numbers" / "README.md",
                "children": (
                    {
                        "module_public_key": "iris.images.numbers.five",
                        "name": "5",
                        "call_name": "5",
                        "icon": "looks_5",
                        "description": "Submódulo de imagem do número 5.",
                        "readme_path": DEFAULT_MODULES_ROOT / "images" / "numbers" / "five" / "README.md",
                    },
                ),
            },
        ),
    },
    {
        "module_public_key": "open",
        "name": "Abrir",
        "call_name": "abrir",
        "icon": "open_in_new",
        "description": "Módulo responsável por abrir recursos locais ou páginas.",
        "readme_path": DEFAULT_MODULES_ROOT / "open" / "README.md",
        "children": (
            {
                "module_public_key": "open.app",
                "name": "App",
                "call_name": "app",
                "icon": "apps",
                "description": "Abre itens da area de trabalho.",
                "readme_path": DEFAULT_MODULES_ROOT / "open" / "app" / "README.md",
                "request_method": "PYTHON",
                "request_url": "modules.default_modules.open.app.main",
                "is_executable": True,
            },
            {
                "module_public_key": "open.web",
                "name": "Web",
                "call_name": "web",
                "icon": "public",
                "description": "Submódulo responsável por abrir páginas web.",
                "readme_path": DEFAULT_MODULES_ROOT / "open" / "web" / "README.md",
                "children": (
                    {
                        "module_public_key": "open.web.green",
                        "name": "Verde",
                        "call_name": "verde",
                        "icon": "palette",
                        "description": "Abre uma página HTML com fundo verde.",
                        "readme_path": DEFAULT_MODULES_ROOT / "open" / "web" / "green" / "README.md",
                        "request_method": "GET",
                        "request_url": "http://127.0.0.1:4101/web/verde",
                        "is_executable": True,
                    },
                    {
                        "module_public_key": "open.web.red",
                        "name": "Vermelho",
                        "call_name": "vermelho",
                        "icon": "palette",
                        "description": "Abre uma página HTML com fundo vermelho.",
                        "readme_path": DEFAULT_MODULES_ROOT / "open" / "web" / "red" / "README.md",
                        "request_method": "GET",
                        "request_url": "http://127.0.0.1:4101/web/vermelho",
                        "is_executable": True,
                    },
                ),
            },
        ),
    },
)


def init_db() -> None:
    import database.models

    _ensure_sqlite_schema()
    _ensure_module_registry_schema()
    Base.metadata.create_all(bind=engine)
    _ensure_module_registry_schema()
    _seed_default_modules()


def _ensure_sqlite_schema() -> None:
    if engine.url.get_backend_name() != "sqlite":
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    def has_column(table_name: str, column_name: str) -> bool:
        return column_name in {
            column["name"] for column in inspector.get_columns(table_name)
        }

    with engine.begin() as connection:
        if "modules" in table_names and not has_column("modules", "parent_module_id"):
            connection.execute(
                text("ALTER TABLE modules ADD COLUMN parent_module_id INTEGER")
            )

        if "modules" in table_names and not has_column("modules", "request_method"):
            connection.execute(text("ALTER TABLE modules ADD COLUMN request_method VARCHAR(10)"))

        if "modules" in table_names and not has_column("modules", "request_url"):
            connection.execute(text("ALTER TABLE modules ADD COLUMN request_url VARCHAR(255)"))

        if "modules" in table_names and not has_column("modules", "is_executable"):
            connection.execute(text("ALTER TABLE modules ADD COLUMN is_executable BOOLEAN DEFAULT 0"))

        if "routine_actions" in table_names and not has_column("routine_actions", "module_id"):
            connection.execute(
                text("ALTER TABLE routine_actions ADD COLUMN module_id INTEGER")
            )

        if "logs" in table_names and not has_column("logs", "module_id"):
            connection.execute(text("ALTER TABLE logs ADD COLUMN module_id INTEGER"))

        if "actions" in table_names and "modules" in table_names:
            connection.execute(
                text(
                    """
                    INSERT INTO modules (
                        name,
                        call_name,
                        custom_call_name,
                        description,
                        parent_module_id,
                        created_date,
                        edited_date
                    )
                    SELECT
                        actions.name,
                        actions.call_name,
                        actions.custom_call_name,
                        actions.description,
                        actions.id_module,
                        actions.created_date,
                        actions.edited_date
                    FROM actions
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM modules
                        WHERE modules.parent_module_id = actions.id_module
                            AND modules.call_name = actions.call_name
                    )
                    """
                )
            )

            if "routine_actions" in table_names:
                connection.execute(
                    text(
                        """
                        UPDATE routine_actions
                        SET module_id = (
                            SELECT modules.id
                            FROM modules
                            JOIN actions
                                ON modules.parent_module_id = actions.id_module
                                AND modules.call_name = actions.call_name
                            WHERE actions.id = routine_actions.action_id
                            LIMIT 1
                        )
                        WHERE module_id IS NULL
                        """
                    )
                )

            if "logs" in table_names:
                connection.execute(
                    text(
                        """
                        UPDATE logs
                        SET module_id = (
                            SELECT modules.id
                            FROM modules
                            JOIN actions
                                ON modules.parent_module_id = actions.id_module
                                AND modules.call_name = actions.call_name
                            WHERE actions.id = logs.action_id
                            LIMIT 1
                        )
                        WHERE module_id IS NULL
                        """
                    )
                )


def _ensure_module_registry_schema() -> None:
    if engine.url.get_backend_name() != "sqlite":
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "modules" not in table_names:
        return

    module_columns = {column["name"] for column in inspector.get_columns("modules")}
    has_registry_schema = "module_public_key" in module_columns
    has_alembic_version = "alembic_version" in table_names

    if not has_registry_schema:
        _run_alembic_upgrade_from_legacy_schema(has_alembic_version)
        return

    if not has_alembic_version:
        if "icon" in module_columns:
            _stamp_alembic_revision("head")
            return
        _stamp_alembic_revision("f8c1d4a7b2e9")

    _upgrade_alembic_revision("head")


def _run_alembic_upgrade_from_legacy_schema(has_alembic_version: bool) -> None:
    if not has_alembic_version:
        _stamp_alembic_revision("e5f7a9c2d4b1")
    _upgrade_alembic_revision("head")


def _build_alembic_config():
    from alembic.config import Config

    project_root = Path(__file__).resolve().parents[1]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", str(engine.url))
    return config


def _stamp_alembic_revision(revision: str) -> None:
    from alembic import command

    command.stamp(_build_alembic_config(), revision)


def _upgrade_alembic_revision(revision: str) -> None:
    from alembic import command

    command.upgrade(_build_alembic_config(), revision)


def _seed_default_modules() -> None:
    from database.models import Module

    db = SessionLocal()
    try:
        def seed_tree(modules: tuple[dict, ...], parent_id: int | None = None) -> None:
            for module_data in modules:
                module = (
                    db.query(Module)
                    .filter(Module.module_public_key == module_data["module_public_key"])
                    .first()
                )

                if module is None:
                    module = (
                        db.query(Module)
                        .filter(
                            Module.module_public_key.like("legacy.module-%"),
                            func.lower(Module.call_name) == module_data["call_name"].lower(),
                            Module.parent_module_id == parent_id,
                            Module.manifest_directory.is_(None),
                        )
                        .first()
                    )
                    if module is not None:
                        module.module_public_key = module_data["module_public_key"]

                if module is None:
                    module = Module(
                        module_public_key=module_data["module_public_key"],
                        name=module_data["name"],
                        call_name=module_data["call_name"],
                        icon=module_data.get("icon", "extension"),
                        description=module_data.get("description", ""),
                        readme_path=str(module_data["readme_path"]),
                        parent_module_id=parent_id,
                        request_method=module_data.get("request_method"),
                        request_url=module_data.get("request_url"),
                        is_executable=module_data.get("is_executable", False),
                    )
                    db.add(module)
                    db.flush()
                else:
                    module.name = module_data["name"]
                    module.call_name = module_data["call_name"]
                    module.icon = module_data.get("icon", "extension")
                    module.description = module_data.get("description", module.description)
                    module.readme_path = str(module_data["readme_path"])
                    module.request_method = module_data.get("request_method", module.request_method)
                    module.request_url = module_data.get("request_url", module.request_url)
                    module.is_executable = module_data.get("is_executable", module.is_executable)

                seed_tree(tuple(module_data.get("children", ())), module.id)

        seed_tree(DEFAULT_MODULE_TREE)
        db.commit()
    finally:
        db.close()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
