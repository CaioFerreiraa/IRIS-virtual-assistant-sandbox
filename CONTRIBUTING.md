# Como contribuir com a IRIS

Obrigado por ajudar a construir a IRIS. Você pode colaborar sem conhecer todo o
sistema: escolha uma mudança pequena, mantenha-a focada e teste o comportamento
que alterou.

Ao participar, siga o [Código de Conduta](CODE_OF_CONDUCT.md). Problemas de
segurança devem seguir [SECURITY.md](SECURITY.md), não uma issue pública.

## Escolha uma trilha

### Criar ou melhorar um módulo

Use o manifesto local versão 1 e mantenha o módulo independente da interface e
do banco interno. Comece pelo guia
[Desenvolvimento de módulos](documentation/module-development.md) e pelo exemplo
[`modules/examples/minimal`](modules/examples/minimal).

Crie e valide um módulo sem iniciar a interface:

```powershell
python -m modules new community.hello --name "Olá comunidade"
python -m modules validate modules/installed/community_hello
python -m modules check modules/installed/community_hello
```

O comando `validate` não importa o entry point. `check` importa o Python para
conferir o contrato e só deve ser usado em código revisado.

Como apoio ao fluxo local, **Configurações > Módulos locais** oferece o mesmo
scaffold, validação segura, diagnóstico e uma ressincronização explícita. A aba
não é um catálogo nem um instalador: ela opera somente sobre pastas locais e a
ressincronização importa runtimes Python no processo da IRIS.

A interface canônica de um runtime Python novo é:

```python
def execute(
    argument: str | None = None,
    variables: dict[str, str] | None = None,
) -> dict:
    return {"success": True, "message": "Ação concluída."}
```

Os nomes `run`, `main`, `searchArguments` e `shouldRequestArgument` existem para
compatibilidade. Código novo deve preferir `execute`, `search_arguments` e
`should_request_argument`.

Não inclua credenciais, tokens ou senhas. A IRIS ainda não possui Vault nem
isolamento seguro para código comunitário.

### Alterar o núcleo da aplicação

Antes de editar, leia [AGENTS.md](AGENTS.md) e os documentos relacionados em
`documentation/`. Preserve a separação existente:

- `core/`: orquestração e regras centrais;
- `services/`: integrações e recursos substituíveis;
- `repositories/`: persistência;
- `ui/`: estado visual e interação Flet;
- `modules/`: contratos e módulos locais.

Não coloque operações demoradas na thread visual nem acople módulos comunitários
a controles Flet ou ao banco da IRIS.

### Melhorar documentação e experiência

Textos de interface e documentação permanecem em português do Brasil. Quando
uma mudança altera comportamento, atualize o documento correspondente e deixe
claro o que está implementado, parcial ou planejado.

## Preparar o ambiente

O ambiente principal usa Python 3.11 e Windows. No PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Inicie a aplicação com:

```powershell
python main.py
```

## Executar testes

Suíte completa:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Contrato principal de módulos:

```powershell
python -m unittest tests.test_module_manifest
python -m unittest tests.test_module_registry
python -m unittest tests.test_module_execution
python -m unittest tests.test_module_runtime
```

Use banco e diretórios temporários em testes. Não versione `iris.db`, logs,
áudio, modelos ou arquivos `.env`.

## Preparar uma mudança

1. Crie uma branch a partir de `main`.
2. Faça uma mudança coesa, sem incluir arquivos gerados ou alterações alheias.
3. Adicione testes para o fluxo principal e para falhas relevantes.
4. Atualize a documentação afetada.
5. Execute os testes proporcionais ao risco.
6. Abra o pull request explicando problema, solução, validação e limitações.

Para mudanças visuais, inclua imagem ou gravação quando possível. Para mudanças
de banco, inclua uma migration Alembic revisada e não altere migrations que já
possam ter sido aplicadas.

## Checklist do pull request

- [ ] A mudança tem uma responsabilidade clara.
- [ ] O comportamento anterior foi preservado quando necessário.
- [ ] Testes relevantes passam localmente.
- [ ] A documentação relacionada foi atualizada.
- [ ] Textos visíveis estão em português do Brasil.
- [ ] Identificadores de código estão em inglês.
- [ ] Nenhum segredo ou dado pessoal foi incluído.
- [ ] Riscos e validações manuais estão descritos no pull request.
