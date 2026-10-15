import asyncio
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.db import Base
from services.vault_service import VaultService
from ui.settings.vault_keys_tab import MASKED_VALUE_MARKER, VaultKeysTab
from ui.settings.view import SETTINGS_TABS, SettingsViewState
from ui.theme.colors import GREY_200, TEXT_PRIMARY


class VaultKeysTabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        engine = create_engine(f"sqlite:///{root / 'ui.db'}")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        self.vault = VaultService(sessionmaker(bind=engine), root / '.iris_vault.key')
        self.toaster = Mock()
        self.tab = VaultKeysTab(self.toaster, self.vault)
        self.page = SimpleNamespace(overlay=[], update=Mock())

    def test_settings_tab_and_empty_state(self):
        self.assertIn(('vault', 'Vault Keys'), [(key, label) for key, label, _ in SETTINGS_TABS])
        asyncio.run(self.tab.refresh())
        body = self.tab.table_slot.content.content.controls[1]
        self.assertEqual('Nenhuma Vault Key cadastrada.', body.content.value)

    def test_general_settings_is_initial_tab(self):
        with patch('ui.settings.view.VoiceSettingsTab', return_value=Mock()):
            state = SettingsViewState(
                Mock(), Mock(), Mock(),
                Mock(), Mock(), Mock(), Mock(),
            )
        self.assertEqual('general', state.active_tab)

    def test_form_create_edit_empty_value_and_masked_table(self):
        dialog = self.tab._open_form(self.page)
        left_column, right_column = dialog.content.content.controls
        name, value, allow = left_column.controls
        description = right_column.controls[0]
        self.assertEqual(840, dialog.content.width)
        self.assertEqual({"sm": 12, "md": 6}, left_column.col)
        self.assertEqual({"sm": 12, "md": 6}, right_column.col)
        self.assertTrue(value.password)
        self.assertTrue(value.can_reveal_password)
        self.assertFalse(allow.value)
        name.value = 'demo_key'
        description.value = 'Exemplo'
        value.value = 'demo-private-value'
        asyncio.run(dialog.actions[1].on_click(SimpleNamespace(page=self.page)))
        self.assertFalse(dialog.open)
        self.assertEqual('', value.value)
        key = self.vault.list_metadata()[0]
        row = self.tab._build_row(key)
        self.assertEqual('••••••••', row['value'])
        self.assertEqual('Nenhum módulo', row['modules'])
        self.assertNotIn('demo-private-value', str({k: v for k, v in row.items() if k != 'actions'}))
        edit = self.tab._open_form(self.page, key)
        left_column, right_column = edit.content.content.controls
        name, value, allow = left_column.controls
        description = right_column.controls[0]
        self.assertTrue(name.read_only)
        self.assertTrue(name.disabled)
        self.assertEqual(GREY_200, name.bgcolor)
        self.assertEqual(TEXT_PRIMARY, name.text_style.color)
        self.assertEqual(MASKED_VALUE_MARKER, value.value)
        self.assertTrue(value.password)
        self.assertFalse(value.can_reveal_password)
        self.assertEqual("•", value.obscuring_character)
        self.assertEqual(280, edit.content.height)
        description.value = 'Editada'
        asyncio.run(edit.actions[1].on_click(SimpleNamespace(page=self.page)))
        self.assertEqual('demo-private-value', self.vault.get_value('DEMO_KEY'))
        self.assertEqual('Editada', self.vault.list_metadata()[0]['description'])
        self.toaster.show_success.assert_called()

        edit = self.tab._open_form(self.page, self.vault.list_metadata()[0])
        value = edit.content.content.controls[0].controls[1]
        value.value = ''
        asyncio.run(edit.actions[1].on_click(SimpleNamespace(page=self.page)))
        self.assertIsNone(self.vault.get_value('DEMO_KEY'))

        edit = self.tab._open_form(self.page, self.vault.list_metadata()[0])
        value = edit.content.content.controls[0].controls[1]
        self.assertEqual('', value.value)
        value.value = 'replacement-value'
        asyncio.run(edit.actions[1].on_click(SimpleNamespace(page=self.page)))
        self.assertEqual('replacement-value', self.vault.get_value('DEMO_KEY'))

    def test_create_null_value_and_search(self):
        self.vault.create('TOKEN_NOTAS', None, 'Token de acesso')
        self.vault.create('OTHER', 'another', 'Outra chave')
        asyncio.run(self.tab.refresh())
        self.assertEqual(2, len(self.tab.table_slot.content.content.controls[1].controls))
        self.tab.search_input.value = 'token acesso'
        self.tab.on_search_change(SimpleNamespace(control=self.tab.search_input))
        body = self.tab.table_slot.content.content.controls[1]
        self.assertEqual(1, len(body.controls))
        self.assertEqual('—', body.controls[0].content.controls[2].content.value)
        self.tab.clear_search(SimpleNamespace())
        self.assertEqual(2, len(self.tab.table_slot.content.content.controls[1].controls))

    def test_delete_requires_confirmation_and_warns_about_modules(self):
        self.vault.create('DEMO_KEY', 'demo-private-value')
        key = self.vault.list_metadata()[0]
        self.vault.modules_using = Mock(return_value=[{'id': 1, 'name': 'Criar nota'}])
        asyncio.run(self.tab.on_delete(SimpleNamespace(page=self.page), key))
        self.assertEqual(1, len(self.vault.list_metadata()))
        dialog = self.page.overlay[-1]
        message = dialog.content.content.controls[0].value
        self.assertIn('Criar nota', message)
        asyncio.run(dialog.actions[1].on_click(SimpleNamespace(page=self.page)))
        self.assertEqual([], self.vault.list_metadata())

    def test_form_validation_and_unavailable_state_use_toast(self):
        dialog = self.tab._open_form(self.page)
        asyncio.run(dialog.actions[1].on_click(SimpleNamespace(page=self.page)))
        self.assertTrue(dialog.open)
        self.toaster.show_error.assert_called()
        self.vault.list_metadata = Mock(side_effect=RuntimeError('private storage details'))
        asyncio.run(self.tab.refresh())
        self.assertIn('Não foi possível carregar', self.tab.table_slot.content.value)
        self.assertNotIn('private storage details', self.toaster.show_error.call_args.args[0])
