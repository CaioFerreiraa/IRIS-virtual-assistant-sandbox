import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.command_processor import CommandProcessor
from core.module_runner import ModuleRunner
from database.db import Base, DEFAULT_MODULE_TREE, enable_sqlite_foreign_keys
from database.models import Module, ModuleVariableDefinition, ModuleVariableValue
from repositories.module_repository import ModuleRepository
from services.module_loader import load_python_entrypoint
from services.module_registry_service import ModuleRegistryService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALLED_MODULES_ROOT = PROJECT_ROOT / "modules" / "installed"


def walk_default_modules(modules: tuple[dict, ...]):
    for module in modules:
        yield module
        yield from walk_default_modules(tuple(module.get("children", ())))


class DemoModuleRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        database_path = Path(self.temporary_directory.name) / "demo-modules.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        self.addCleanup(self.engine.dispose)
        enable_sqlite_foreign_keys(self.engine)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def test_all_installed_demo_modules_are_valid_and_documented(self) -> None:
        state = ModuleRegistryService(
            INSTALLED_MODULES_ROOT,
            self.session_factory,
        ).sync()

        self.assertEqual((), state.invalid_modules)
        self.assertEqual(10, len(state.synced_module_ids))
        self.assertTrue(all(content.strip() for content in state.readme_contents.values()))
        self.assertTrue(
            all("O que" in content for content in state.readme_contents.values())
        )

        db = self.session_factory()
        try:
            root = db.query(Module).filter_by(module_public_key="test.showcase").one()
            contracts = db.query(Module).filter_by(
                module_public_key="test.showcase.contracts"
            ).one()
            execute_module = db.query(Module).filter_by(
                module_public_key="test.showcase.contracts.execute"
            ).one()
            weather = db.query(Module).filter_by(
                module_public_key="weather.forecast"
            ).one()
            self.assertIsNone(root.parent_module_id)
            self.assertEqual(root.id, contracts.parent_module_id)
            self.assertEqual(contracts.id, execute_module.parent_module_id)
            self.assertTrue(root.supports_auto_start)
            self.assertTrue(weather.is_executable)
        finally:
            db.close()

    def test_every_legacy_default_module_has_a_readme(self) -> None:
        modules = list(walk_default_modules(DEFAULT_MODULE_TREE))
        self.assertEqual(13, len(modules))
        for module in modules:
            with self.subTest(public_key=module["module_public_key"]):
                readme_path = Path(module["readme_path"])
                self.assertTrue(readme_path.is_file())
                self.assertIn("# ", readme_path.read_text(encoding="utf-8"))

    def test_weather_requests_argument_only_without_default_location(self) -> None:
        ModuleRegistryService(
            INSTALLED_MODULES_ROOT,
            self.session_factory,
        ).sync()
        db = self.session_factory()
        try:
            weather = db.query(Module).filter_by(
                module_public_key="weather.forecast"
            ).one()
            processor = CommandProcessor(ModuleRepository(db))
            self.assertTrue(processor.module_requires_argument_by_id(weather.id))

            definition = db.query(ModuleVariableDefinition).filter_by(
                module_id=weather.id,
                key="default_location",
            ).one()
            db.add(
                ModuleVariableValue(
                    variable_definition_id=definition.id,
                    value_text="Recife",
                )
            )
            db.commit()

            self.assertFalse(processor.module_requires_argument_by_id(weather.id))
        finally:
            db.close()


class DemoModuleExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = ModuleRunner()

    def entrypoint(self, folder: str) -> str:
        return str(INSTALLED_MODULES_ROOT / folder / "main.py")

    def test_execute_run_and_main_contracts(self) -> None:
        scenarios = (
            ("test_showcase_execute", "test.showcase.contracts.execute", "execute"),
            ("test_showcase_run", "test.showcase.contracts.run", "run"),
            ("test_showcase_main", "test.showcase.contracts.main", "main"),
        )
        for folder, public_key, function_name in scenarios:
            with self.subTest(function_name=function_name):
                result = self.runner.run_entrypoint(
                    self.entrypoint(folder),
                    "teste",
                    module_public_key=public_key,
                )
                self.assertTrue(result["success"])
                self.assertIn(function_name, result["message"])

    def test_current_and_compatibility_argument_contracts(self) -> None:
        current_results = self.runner.search_arguments(
            self.entrypoint("test_showcase_arguments"),
            "beta",
            "test.showcase.arguments",
        )
        compatibility_results = self.runner.search_arguments(
            self.entrypoint("test_showcase_arguments_compatibility"),
            "consulta ignorada",
            "test.showcase.arguments_compatibility",
        )

        self.assertEqual("beta", current_results[0]["value"])
        self.assertEqual("compatível um", compatibility_results[0]["label"])
        self.assertEqual("", compatibility_results[0]["description"])

        result = self.runner.run_entrypoint(
            self.entrypoint("test_showcase_arguments_compatibility"),
            "compatível dois",
            module_public_key="test.showcase.arguments_compatibility",
        )
        self.assertIn("compatível dois", result["message"])

    def test_plain_response_is_normalized(self) -> None:
        result = self.runner.run_entrypoint(
            self.entrypoint("test_showcase_responses"),
            "plain",
            module_public_key="test.showcase.responses",
        )
        self.assertEqual(True, result["success"])
        self.assertIn("String convertida", result["result"])

    def test_controlled_failure_and_exception(self) -> None:
        controlled = self.runner.run_entrypoint(
            self.entrypoint("test_showcase_failures"),
            "controlled",
            module_public_key="test.showcase.failures",
        )
        self.assertFalse(controlled["success"])

        with self.assertRaisesRegex(RuntimeError, "intencional"):
            self.runner.run_entrypoint(
                self.entrypoint("test_showcase_failures"),
                "exception",
                module_public_key="test.showcase.failures",
            )

    def test_root_auto_start_contract(self) -> None:
        loaded_module = load_python_entrypoint(
            self.entrypoint("test_showcase"),
            "test.showcase",
        )
        loaded_module.start(variables={"editable_text": "teste"})
        self.assertTrue(loaded_module._is_started)
        loaded_module.stop()
        self.assertFalse(loaded_module._is_started)


if __name__ == "__main__":
    unittest.main()
