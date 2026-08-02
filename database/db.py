from collections.abc import Generator

from sqlalchemy import create_engine, func, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///iris.db"

engine = create_engine(DATABASE_URL, echo=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()


DEFAULT_MODULE_TREE = (
    {
        "name": "Assistente",
        "call_name": "assistente",
        "description": "Módulo principal da IRIS.",
    },
    {
        "name": "Agenda",
        "call_name": "agenda",
        "description": "Módulo responsável por compromissos e eventos.",
    },
    {
        "name": "Arquivos",
        "call_name": "arquivos",
        "description": "Módulo responsável por localizar e organizar arquivos.",
    },
    {
        "name": "Navegador",
        "call_name": "navegador",
        "description": "Módulo responsável por navegação e pesquisa.",
    },
    {
        "name": "Sistema",
        "call_name": "sistema",
        "description": "Módulo responsável por comandos do sistema.",
    },
    {
        "name": "Imagens",
        "call_name": "imagens",
        "description": "Módulo responsável por recursos de imagem.",
        "children": (
            {
                "name": "Números",
                "call_name": "numeros",
                "description": "Submódulo de imagens com números.",
                "children": (
                    {
                        "name": "5",
                        "call_name": "5",
                        "description": "Submódulo de imagem do número 5.",
                    },
                ),
            },
        ),
    },
    {
        "name": "Abrir",
        "call_name": "abrir",
        "description": "Módulo responsável por abrir recursos locais ou páginas.",
        "children": (
            {
                "name": "App",
                "call_name": "app",
                "description": "Abre itens da area de trabalho.",
                "request_method": "PYTHON",
                "request_url": "modules.default_modules.open.app.main",
                "is_executable": True,
            },
            {
                "name": "Web",
                "call_name": "web",
                "description": "Submódulo responsável por abrir páginas web.",
                "children": (
                    {
                        "name": "Verde",
                        "call_name": "verde",
                        "description": "Abre uma página HTML com fundo verde.",
                        "request_method": "GET",
                        "request_url": "http://127.0.0.1:4101/web/verde",
                        "is_executable": True,
                    },
                    {
                        "name": "Vermelho",
                        "call_name": "vermelho",
                        "description": "Abre uma página HTML com fundo vermelho.",
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

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_schema()
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


def _seed_default_modules() -> None:
    from database.models import Module

    db = SessionLocal()
    try:
        def seed_tree(modules: tuple[dict, ...], parent_id: int | None = None) -> None:
            for module_data in modules:
                module = (
                    db.query(Module)
                    .filter(
                        func.lower(Module.call_name) == module_data["call_name"].lower(),
                        Module.parent_module_id == parent_id,
                    )
                    .first()
                )

                if module is None:
                    module = Module(
                        name=module_data["name"],
                        call_name=module_data["call_name"],
                        description=module_data.get("description", ""),
                        parent_module_id=parent_id,
                        request_method=module_data.get("request_method"),
                        request_url=module_data.get("request_url"),
                        is_executable=module_data.get("is_executable", False),
                    )
                    db.add(module)
                    db.flush()
                else:
                    module.description = module_data.get("description", module.description)
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
