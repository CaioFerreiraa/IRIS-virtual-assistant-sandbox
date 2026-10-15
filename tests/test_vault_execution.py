import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.command_processor import CommandProcessor
from core.module_runner import ModuleRunner
from database.db import Base
from database.models import Log, Module, ModuleHttpRequest, Routine
from repositories.module_repository import ModuleRepository
from services.vault_service import VaultService


def item(key, value, enabled=True):
    return {'key': key, 'value': value, 'description': '', 'enabled': enabled}


class VaultExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engine = create_engine(f"sqlite:///{self.root / 'execution.db'}")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        self.vault = VaultService(self.factory, self.root / '.iris_vault.key')
        self.secret = 'demo-private-value'
        self.vault.create('KEY', self.secret)
        self.vault.create('OTHER', 'other-demo-value')

    def create_http(self, *, declared=None, url=None, body=None, headers=None, params=None,
                    response_vault=None):
        with self.factory() as db:
            module = Module(module_public_key='example.http', name='HTTP', call_name='http',
                            is_executable=True, vault_keys_json=json.dumps(['KEY'] if declared is None else declared))
            db.add(module)
            db.flush()
            db.add(ModuleHttpRequest(module_id=module.id, method='POST',
                                    url=url or 'https://example.com/{{vk.KEY}}/{{argument}}', argument_enabled=True,
                                    params_json=json.dumps(params or []), headers_json=json.dumps(headers or []),
                                    body_json=json.dumps(body or {'mode': 'none', 'content': ''}),
                                    response_vault_json=json.dumps(response_vault)))
            db.commit()
            return module.id

    def execute(self, module_id, argument='texto', routine_id=None):
        with self.factory() as db:
            return CommandProcessor(ModuleRepository(db), self.factory, self.vault).execute_module_id(
                module_id, argument, routine_id=routine_id)

    def create_python_for_update(self, declared):
        with self.factory() as db:
            module = Module(
                module_public_key='example.vault_update',
                name='Atualização',
                call_name='atualização',
                is_executable=True,
                request_method='PYTHON',
                request_url='fake_entrypoint',
                vault_keys_json=json.dumps(declared),
            )
            db.add(module)
            db.commit()
            return module.id

    def response(self, body=None):
        return httpx.Response(200, json=body or {'ok': True}, request=httpx.Request('POST', 'https://example.com'))

    def test_http_resolves_url_params_headers_body_and_preserves_argument(self):
        module_id = self.create_http(params=[item('search', '{{argument}}'), item('token', '{{vk.KEY}}')],
                                     headers=[item('X-IRIS-Vault', '{{vk.KEY}}'), item('{{vk.KEY}}', '{{argument}}')],
                                     body={'mode': 'raw_json', 'content': '{"token":"{{vk.KEY}}","text":"{{argument}}"}'})
        with patch('services.http_service.httpx.request', return_value=self.response()) as request:
            self.assertTrue(self.execute(module_id)['success'])
        self.assertEqual(f'https://example.com/{self.secret}/texto', request.call_args.args[1])
        self.assertEqual({'search': 'texto', 'token': self.secret}, request.call_args.kwargs['params'])
        self.assertEqual({'X-IRIS-Vault': self.secret, self.secret: 'texto'}, request.call_args.kwargs['headers'])
        self.assertEqual({'token': self.secret, 'text': 'texto'}, request.call_args.kwargs['json'])
        with self.factory() as db:
            self.assertNotIn(self.secret, str([log.message for log in db.query(Log)]))
            self.assertNotIn(self.secret, db.query(ModuleHttpRequest).one().headers_json)

    def test_http_resolves_vault_reference_typed_as_argument(self):
        module_id = self.create_http(url='https://example.com/{{argument}}')
        with patch('services.http_service.httpx.request', return_value=self.response()) as request:
            self.execute(module_id, 'tokens/{{vk.KEY}}')
        self.assertEqual(
            f'https://example.com/tokens/{self.secret}',
            request.call_args.args[1],
        )
        with self.factory() as db:
            self.assertEqual(
                'tokens/{{vk.KEY}}',
                db.query(ModuleHttpRequest).one().argument,
            )

    def test_legacy_vault_placeholder_is_rejected(self):
        module_id = self.create_http(url='https://example.com/{{KEY}}')
        with patch('services.http_service.httpx.request') as request:
            with self.assertRaisesRegex(ValueError, 'Use.*vk.NOME_DA_CHAVE'):
                self.execute(module_id)
        request.assert_not_called()

    def test_raw_text_and_form_body_resolve_keys(self):
        for mode in ('raw_text', 'form_urlencoded'):
            with self.subTest(mode=mode):
                with self.factory() as db:
                    db.query(Log).delete()
                    db.query(ModuleHttpRequest).delete()
                    db.query(Module).delete()
                    db.commit()
                content = '{{vk.KEY}}/{{argument}}' if mode == 'raw_text' else [item('token', '{{vk.KEY}}')]
                module_id = self.create_http(body={'mode': mode, 'content': content})
                with patch('services.http_service.httpx.request', return_value=self.response()) as request:
                    self.execute(module_id)
                field = 'content' if mode == 'raw_text' else 'data'
                expected = self.secret + '/texto' if mode == 'raw_text' else {'token': self.secret}
                self.assertEqual(expected, request.call_args.kwargs[field])

    def test_undeclared_placeholder_prevents_request(self):
        module_id = self.create_http(declared=[])
        with patch('services.http_service.httpx.request') as request:
            with self.assertRaisesRegex(ValueError, 'KEY não foi declarada'):
                self.execute(module_id)
        request.assert_not_called()

    def test_missing_declared_key_prevents_request(self):
        module_id = self.create_http(declared=['MISSING'], url='https://example.com/{{vk.MISSING}}')
        with patch('services.http_service.httpx.request') as request:
            with self.assertRaisesRegex(ValueError, 'A Vault Key MISSING não foi configurada.'):
                self.execute(module_id)
        request.assert_not_called()
        with self.factory() as db:
            self.assertIn('MISSING não foi configurada', db.query(Log).one().message)

    def test_disabled_fields_and_unused_missing_declarations_do_not_resolve(self):
        module_id = self.create_http(declared=['MISSING'], url='https://example.com/{{argument}}',
                                     headers=[item('token', '{{vk.UNDECLARED}}', False)])
        with patch.object(self.vault, 'get_value', side_effect=AssertionError('Não deve descriptografar')):
            with patch('services.http_service.httpx.request', return_value=self.response()) as request:
                self.execute(module_id)
        self.assertEqual('https://example.com/texto', request.call_args.args[1])

    def test_http_echo_and_exception_do_not_expose_resolved_values(self):
        module_id = self.create_http()
        response = self.response({'echo': self.secret, self.secret: [self.secret]})
        response.headers['X-Echo'] = self.secret
        with patch('services.http_service.httpx.request', return_value=response):
            result = self.execute(module_id)
        self.assertNotIn(self.secret, json.dumps(result))
        with patch('services.http_service.httpx.request', side_effect=RuntimeError('Invalid header ' + self.secret)):
            with self.assertRaises(ValueError) as caught:
                self.execute(module_id)
        self.assertNotIn(self.secret, str(caught.exception))
        with self.factory() as db:
            self.assertNotIn(self.secret, str([log.message for log in db.query(Log)]))

    def test_json_secret_is_escaped_and_is_not_resolved_recursively(self):
        secret = 'demo"\\value {{OTHER}}'
        self.vault.update(self.vault.list_metadata()[0]['id'], new_value=secret)
        module_id = self.create_http(body={'mode': 'raw_json', 'content': '{"token":"{{vk.KEY}}"}'})
        with patch('services.http_service.httpx.request', return_value=self.response()) as request:
            self.execute(module_id)
        self.assertEqual(secret, request.call_args.kwargs['json']['token'])

    def test_routine_uses_vault_without_overwriting_saved_argument(self):
        module_id = self.create_http()
        with self.factory() as db:
            routine = Routine(name='Rotina')
            db.add(routine)
            db.query(ModuleHttpRequest).one().argument = 'salvo'
            db.commit()
            routine_id = routine.id
        with patch('services.http_service.httpx.request', return_value=self.response()):
            self.execute(module_id, 'etapa', routine_id=routine_id)
        with self.factory() as db:
            self.assertEqual('salvo', db.query(ModuleHttpRequest).one().argument)
            self.assertEqual(routine_id, db.query(Log).one().routine_id)

    def test_python_receives_only_declared_existing_keys_without_environment_changes(self):
        entrypoint = self.root / 'main.py'
        entrypoint.write_text('''def execute(argument=None, variables=None, vault=None):
    return {"success": vault.get("KEY") == "demo-private-value",
            "keys": sorted(vault), "variables": variables, "message": vault.get("KEY")}
''', encoding='utf-8')
        with self.factory() as db:
            module = Module(module_public_key='example.python', name='Python', call_name='python',
                            is_executable=True, request_method='PYTHON', request_url=str(entrypoint),
                            vault_keys_json='["KEY","MISSING"]')
            db.add(module)
            db.commit()
            module_id = module.id
        environment = dict(os.environ)
        result = self.execute(module_id)
        self.assertTrue(result['success'])
        self.assertEqual(['KEY'], result['keys'])
        self.assertEqual({}, result['variables'])
        self.assertEqual(environment, dict(os.environ))
        self.assertNotIn(self.secret, str(result))
        with self.factory() as db:
            self.assertNotIn(self.secret, db.query(Log).one().message)

    def test_python_missing_key_can_use_get_and_report_its_own_error(self):
        with patch.object(ModuleRunner, '_load_entrypoint', return_value=SimpleNamespace(
            execute=lambda vault=None: {'success': False, 'message': 'Configure MISSING nas Vault Keys.'} if not vault.get('MISSING') else {'success': True})):
            result = ModuleRunner().run_entrypoint('fake', vault={})
        self.assertFalse(result['success'])
        self.assertIn('Configure MISSING', result['message'])

    def test_python_argument_can_reference_declared_vault_key(self):
        entrypoint = self.root / 'argument.py'
        entrypoint.write_text(
            'def execute(argument=None, vault=None):\n'
            '    return {"success": argument == "prefix/" + vault["KEY"], "message": argument}\n',
            encoding='utf-8',
        )
        with self.factory() as db:
            module = Module(
                module_public_key='example.argument',
                name='Argumento',
                call_name='argumento',
                is_executable=True,
                request_method='PYTHON',
                request_url=str(entrypoint),
                vault_keys_json='["KEY"]',
            )
            db.add(module)
            db.commit()
            module_id = module.id
        result = self.execute(module_id, 'prefix/{{vk.KEY}}')
        self.assertTrue(result['success'])
        self.assertNotIn(self.secret, str(result))

    def test_runner_preserves_legacy_signatures_and_supports_kwargs_and_positional_only(self):
        functions = [lambda: {'success': True}, lambda argument=None: {'success': argument == 'text'},
                     lambda value: {'success': value == 'text'}, lambda variables=None: {'success': variables == {'prefix': 'IRIS'}},
                     lambda argument=None, variables=None: {'success': argument == 'text' and variables == {'prefix': 'IRIS'}},
                     lambda **kwargs: {'success': kwargs['vault'] == {'KEY': self.secret}},
                     lambda argument, /, vault=None: {'success': argument == 'text' and vault['KEY'] == self.secret},
                     lambda value, *, vault=None: {'success': value == 'text' and vault['KEY'] == self.secret}]
        for function in functions:
            with self.subTest(function=function), patch.object(ModuleRunner, '_load_entrypoint', return_value=SimpleNamespace(execute=function)):
                result = ModuleRunner().run_entrypoint('fake', 'text', {'prefix': 'IRIS'}, vault={'KEY': self.secret})
                self.assertTrue(result['success'])

    def test_python_error_is_redacted_before_logging(self):
        entrypoint = self.root / 'failure.py'
        entrypoint.write_text('def execute(vault=None):\n    raise ValueError("Invalid " + vault["KEY"])\n', encoding='utf-8')
        with self.factory() as db:
            module = Module(module_public_key='example.error', name='Erro', call_name='erro', is_executable=True,
                            request_method='PYTHON', request_url=str(entrypoint), vault_keys_json='["KEY"]')
            db.add(module)
            db.commit()
            module_id = module.id
        with self.assertRaises(RuntimeError) as caught:
            self.execute(module_id)
        self.assertNotIn(self.secret, str(caught.exception))
        with self.factory() as db:
            self.assertNotIn(self.secret, db.query(Log).one().message)

    def test_url_can_be_entirely_declared_by_vault(self):
        self.vault.create("SERVICE_URL", "https://example.com/demo")
        module_id = self.create_http(declared=["SERVICE_URL"], url="{{vk.SERVICE_URL}}/{{argument}}")
        with patch("services.http_service.httpx.request", return_value=self.response()) as request:
            self.execute(module_id)
        self.assertEqual("https://example.com/demo/texto", request.call_args.args[1])

    def test_long_http_response_redacts_before_truncation(self):
        from services.http_service import MAX_RESPONSE_BODY_CHARACTERS
        module_id = self.create_http()
        response = httpx.Response(200, text="x" * (MAX_RESPONSE_BODY_CHARACTERS - 5) + self.secret,
                                  request=httpx.Request("POST", "https://example.com"))
        with patch("services.http_service.httpx.request", return_value=response):
            result = self.execute(module_id)
        self.assertNotIn("demo-", result["body"])

    def test_python_cannot_bypass_return_redaction_by_mutating_vault_dictionary(self):
        def execute(vault=None):
            token = vault.pop("KEY")
            return {"success": True, "message": token, "result": token.encode()}
        with patch.object(ModuleRunner, "_load_entrypoint", return_value=SimpleNamespace(execute=execute)):
            result = ModuleRunner().run_entrypoint("fake", vault={"KEY": self.secret})
        self.assertNotIn(self.secret, str(result))

    def test_background_execution_and_next_run_read_the_current_value(self):
        from concurrent.futures import ThreadPoolExecutor
        module_id = self.create_http(headers=[item("X-IRIS-Vault", "{{vk.KEY}}")])
        with patch("services.http_service.httpx.request", return_value=self.response()) as request:
            with ThreadPoolExecutor(max_workers=1) as pool:
                self.assertTrue(pool.submit(self.execute, module_id).result(timeout=5)["success"])
            self.assertEqual(self.secret, request.call_args.kwargs["headers"]["X-IRIS-Vault"])
            self.vault.update(self.vault.list_metadata()[0]["id"], new_value="new-demo-value")
            self.execute(module_id)
            self.assertEqual("new-demo-value", request.call_args.kwargs["headers"]["X-IRIS-Vault"])
        self.vault.delete(self.vault.list_metadata()[0]["id"])
        with self.assertRaisesRegex(ValueError, "KEY não foi configurada"):
            self.execute(module_id)

    def test_redaction_preserves_the_result_contract_for_short_values(self):
        with patch.object(ModuleRunner, "_load_entrypoint", return_value=SimpleNamespace(
                execute=lambda vault=None: {"success": False, "message": vault["KEY"]})):
            result = ModuleRunner().run_entrypoint("fake", vault={"KEY": "s"})
        self.assertFalse(result["success"])
        self.assertEqual("[valor protegido]", result["message"])

    def test_http_response_updates_vault_and_hides_new_token(self):
        self.vault.create('TOKEN_NOTAS', 'aguardando-login', allow_iris_update=True)
        module_id = self.create_http(
            declared=['KEY', 'TOKEN_NOTAS'],
            url='https://example.com/login',
            body={'mode': 'raw_json', 'content': '{"password":"{{vk.KEY}}"}'},
            response_vault={'key': 'TOKEN_NOTAS', 'path': 'data.token'},
        )
        new_token = 'novo-token-http'
        response = httpx.Response(
            200,
            json={'data': {'token': new_token}, 'echo': self.secret},
            headers={'X-Token': new_token},
            request=httpx.Request('POST', 'https://example.com/login'),
        )
        with patch('services.http_service.httpx.request', return_value=response) as request:
            result = self.execute(module_id)
        self.assertTrue(result['success'])
        self.assertEqual(self.secret, request.call_args.kwargs['json']['password'])
        self.assertEqual(new_token, self.vault.get_value('TOKEN_NOTAS'))
        self.assertNotIn(new_token, json.dumps(result))
        self.assertNotIn(self.secret, json.dumps(result))
        self.assertEqual('[valor protegido]', result['body']['data']['token'])
        with self.factory() as db:
            self.assertNotIn(new_token, db.query(Log).one().message)

    def test_http_response_vault_requires_existing_permitted_key_before_request(self):
        module_id = self.create_http(
            declared=['KEY', 'TOKEN_NOTAS'],
            url='https://example.com/login',
            response_vault={'key': 'TOKEN_NOTAS', 'path': 'data.token'},
        )
        with patch('services.http_service.httpx.request') as request:
            with self.assertRaisesRegex(ValueError, 'Cadastre.*TOKEN_NOTAS'):
                self.execute(module_id)
            request.assert_not_called()
        self.vault.create('TOKEN_NOTAS', 'aguardando-login')
        with patch('services.http_service.httpx.request') as request:
            with self.assertRaisesRegex(ValueError, 'IRIS pode alterar'):
                self.execute(module_id)
            request.assert_not_called()

    def test_http_failed_or_malformed_response_does_not_update_vault(self):
        self.vault.create('TOKEN_NOTAS', 'aguardando-login', allow_iris_update=True)
        module_id = self.create_http(
            declared=['KEY', 'TOKEN_NOTAS'],
            url='https://example.com/login',
            response_vault={'key': 'TOKEN_NOTAS', 'path': 'data.token'},
        )
        rejected_token = 'token-de-erro'
        rejected = httpx.Response(
            401, json={'data': {'token': rejected_token}},
            request=httpx.Request('POST', 'https://example.com/login'),
        )
        with patch('services.http_service.httpx.request', return_value=rejected):
            result = self.execute(module_id)
        self.assertFalse(result['success'])
        self.assertNotIn(rejected_token, json.dumps(result))
        self.assertEqual('aguardando-login', self.vault.get_value('TOKEN_NOTAS'))

        malformed = httpx.Response(
            200, json={'data': {}},
            request=httpx.Request('POST', 'https://example.com/login'),
        )
        with patch('services.http_service.httpx.request', return_value=malformed):
            with self.assertRaisesRegex(ValueError, 'caminho JSON'):
                self.execute(module_id)
        self.assertEqual('aguardando-login', self.vault.get_value('TOKEN_NOTAS'))

    def test_python_can_update_declared_permitted_key_without_exposing_value(self):
        self.vault.create('TOKEN_NOTAS', 'aguardando-login', allow_iris_update=True)
        module_id = self.create_python_for_update(['KEY', 'TOKEN_NOTAS'])
        new_token = 'novo-token-de-teste'
        def execute(vault=None):
            return {'success': True, 'message': new_token,
                    'vault_update': {'name': 'TOKEN_NOTAS', 'value': new_token}}
        with patch.object(ModuleRunner, '_load_entrypoint',
                          return_value=SimpleNamespace(execute=execute)):
            result = self.execute(module_id)
        self.assertEqual(new_token, self.vault.get_value('TOKEN_NOTAS'))
        self.assertNotIn('vault_update', result)
        self.assertNotIn(new_token, str(result))
        with self.factory() as db:
            self.assertNotIn(new_token, db.query(Log).one().message)

    def test_python_cannot_update_key_without_permission(self):
        module_id = self.create_python_for_update(['OTHER'])
        with patch.object(ModuleRunner, '_load_entrypoint', return_value=SimpleNamespace(
                execute=lambda vault=None: {'success': True,
                    'vault_update': {'name': 'OTHER', 'value': 'novo-valor'}})):
            with self.assertRaisesRegex(ValueError, 'permissão'):
                self.execute(module_id)
        self.assertEqual('other-demo-value', self.vault.get_value('OTHER'))

    def test_python_cannot_update_undeclared_key_or_on_failure(self):
        self.vault.create('TOKEN_NOTAS', 'aguardando-login', allow_iris_update=True)
        module_id = self.create_python_for_update(['KEY'])
        with patch.object(ModuleRunner, '_load_entrypoint', return_value=SimpleNamespace(
                execute=lambda vault=None: {'success': True,
                    'vault_update': {'name': 'TOKEN_NOTAS', 'value': 'novo-valor'}})):
            with self.assertRaisesRegex(ValueError, 'não declarada'):
                self.execute(module_id)
        self.assertEqual('aguardando-login', self.vault.get_value('TOKEN_NOTAS'))

        with patch.object(ModuleRunner, '_load_entrypoint', return_value=SimpleNamespace(
                execute=lambda vault=None: {'success': False,
                    'vault_update': {'name': 'KEY', 'value': 'novo-valor'}})):
            with self.assertRaisesRegex(ValueError, 'com falha'):
                self.execute(module_id)
        self.assertEqual(self.secret, self.vault.get_value('KEY'))
