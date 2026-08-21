from core.command_processor import CommandProcessor
from database.db import SessionLocal
from repositories.module_repository import ModuleRepository


class HomeService:
    def __init__(self, session_factory=SessionLocal) -> None:
        self.session_factory = session_factory

    def module_has_arguments(self, module_id: int) -> bool:
        # Verifica se um modulo executavel possui busca de argumentos.
        processor, db = self._build_processor()
        try:
            return processor.module_has_argument_search_by_id(module_id)
        except Exception as error:
            print(error)
            return False
        finally:
            db.close()

    def module_requires_argument(self, module_id: int) -> bool:
        # Decide se a execucao atual precisa abrir o campo de argumento.
        processor, db = self._build_processor()
        try:
            return processor.module_requires_argument_by_id(module_id)
        except Exception as error:
            print(error)
            return processor.module_has_argument_search_by_id(module_id)
        finally:
            db.close()

    def search_module_arguments(self, module_id: int, query: str = "") -> list[dict[str, str]]:
        # Busca os argumentos disponiveis para um modulo.
        processor, db = self._build_processor()
        try:
            return processor.search_module_arguments_by_id(module_id, query)
        except Exception as error:
            print(error)
            return []
        finally:
            db.close()

    def execute_module(self, module_id: int, argument: str | None = None) -> dict:
        # Executa um modulo com ou sem argumento.
        processor, db = self._build_processor()
        try:
            return processor.execute_module_id(module_id, argument)
        finally:
            db.close()

    def _build_processor(self) -> tuple[CommandProcessor, object]:
        # Cria o processador com uma sessao de banco propria.
        db = self.session_factory()
        return CommandProcessor(ModuleRepository(db)), db
