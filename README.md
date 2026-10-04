# IRIS

A IRIS é uma assistente virtual desktop e uma plataforma de automação modular.
Ela recebe comandos por texto ou voz, encontra uma capacidade instalada e
executa ações locais ou integrações externas com histórico e feedback visual.

O projeto está em desenvolvimento e sendo preparado para distribuição open
source. A licença ainda precisa ser escolhida pelo mantenedor; até um arquivo
`LICENSE` ser publicado, não presuma permissão para redistribuir o código.

## Estado atual

A aplicação já oferece:

- interface desktop em Flet, inicialmente voltada ao Windows;
- módulos hierárquicos descobertos por manifesto;
- runtimes Python e requisições HTTP declarativas;
- comandos digitados e fluxo de voz local;
- variáveis de configuração não sensíveis;
- histórico de execução e diagnóstico de módulos;
- estrutura inicial de rotinas e API FastAPI.

Instalação comunitária, catálogo, assinatura, permissões e isolamento de código
de terceiros ainda não estão concluídos. Consulte as
[limitações atuais](documentation/limitation.md) antes de executar módulos que
você não escreveu ou revisou.

## Executar em desenvolvimento

Requisitos principais:

- Windows;
- Python 3.11;
- microfone apenas para os recursos de voz.

No PowerShell:

```powershell
git clone https://github.com/CaioFerreiraa/IRIS-virtual-assistant-sandbox.git
cd IRIS-virtual-assistant-sandbox
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

O primeiro início cria o banco SQLite local, sincroniza os módulos disponíveis
e abre a interface. Arquivos `iris.db`, `.env`, modelos baixados e logs locais
não devem ser versionados.

## Criar o primeiro módulo

No PowerShell, a partir da raiz do repositório:

```powershell
python -m modules new community.hello --name "Olá comunidade"
python -m modules validate modules/installed/community_hello
python -m modules check modules/installed/community_hello
```

`validate` confere manifesto e arquivos sem importar o Python. `check` também
importa o entry point e valida o contrato executável; use-o apenas em código que
você escreveu ou revisou. Os mesmos primeiros passos estão disponíveis em
**Configurações > Módulos locais**. Nessa aba, ressincronize somente código
revisado; a barra lateral incorpora o resultado na navegação seguinte.

O contrato completo está em
[Desenvolvimento de módulos](documentation/module-development.md). Módulos
Python são importados no mesmo processo da IRIS e não contam com uma sandbox de
segurança.

## Testes

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Para trabalhar apenas no contrato de módulos, consulte os comandos menores em
[CONTRIBUTING.md](CONTRIBUTING.md). O schema para editores está em
[`modules/module.schema.json`](modules/module.schema.json).

## Contribuir

Correções, testes, documentação, acessibilidade e novos módulos são bem-vindos.
Leia o [guia de contribuição](CONTRIBUTING.md), o
[código de conduta](CODE_OF_CONDUCT.md) e a
[política de segurança](SECURITY.md) antes de abrir uma mudança.

A documentação funcional está em [documentation/](documentation/introduction.md)
e também pode ser consultada pela tela Documentação da aplicação.

## Licença

<!-- Decisão pendente do mantenedor: escolher e publicar a licença do projeto. -->

A licença do projeto ainda não foi definida. Essa decisão é necessária antes
de uma distribuição open source oficial.
