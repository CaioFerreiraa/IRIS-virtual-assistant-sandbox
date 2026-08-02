from core.command_processor import CommandProcessor
from database.db import SessionLocal
from repositories.module_repository import ModuleRepository


class HomeService:
    def module_has_arguments(self, module_path: str) -> bool:
        # Verifica se um modulo executavel possui busca de argumentos.
        processor, db = self._build_processor()
        try:
            return processor.module_has_argument_search(module_path)
        except Exception as error:
            print(error)
            return False
        finally:
            db.close()

    def search_module_arguments(self, module_path: str, query: str = "") -> list[dict[str, str]]:
        # Busca os argumentos disponiveis para um modulo.
        processor, db = self._build_processor()
        try:
            return processor.search_module_arguments(module_path, query)
        except Exception as error:
            print(error)
            return []
        finally:
            db.close()

    def execute_module(self, module_path: str, argument: str | None = None) -> dict:
        # Executa um modulo com ou sem argumento.
        processor, db = self._build_processor()
        try:
            return processor.execute_module_path(module_path, argument)
        finally:
            db.close()

    def _build_processor(self) -> tuple[CommandProcessor, object]:
        # Cria o processador com uma sessao de banco propria.
        db = SessionLocal()
        return CommandProcessor(ModuleRepository(db)), db
