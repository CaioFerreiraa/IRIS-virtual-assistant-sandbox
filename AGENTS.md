# AGENTS.md — Instruções para agentes de IA

## 1. Finalidade deste arquivo

Este arquivo contém instruções obrigatórias para agentes de inteligência artificial que analisam ou modificam o projeto IRIS.

O conteúdo de `AGENTS.md` é voltado ao trabalho de agentes. A documentação pública e conceitual do projeto está na pasta [`documentation/`](documentation/introduction.md).

Antes de alterar qualquer parte do sistema, leia este arquivo e os documentos relacionados à área que será modificada.

## 2. Visão geral do projeto

A IRIS é uma plataforma desktop open source de assistência virtual e automação modular, desenvolvida em Python.

A aplicação tem como objetivos principais:

- receber comandos digitados ou falados;
- localizar módulos compatíveis com o comando do usuário;
- executar tarefas locais ou integrações externas;
- permitir a composição futura de rotinas;
- registrar execuções e erros;
- processar voz localmente sempre que possível;
- permitir que a comunidade amplie a plataforma por meio de módulos.

A IRIS não é uma inteligência artificial generativa. Ela funciona como uma camada de interação e orquestração entre o usuário, o núcleo da aplicação e módulos responsáveis por tarefas específicas.

## 3. Idioma e nomenclatura

Regras obrigatórias:

- A interface da primeira versão deve permanecer em português do Brasil.
- A documentação da pasta `documentation/` deve ser escrita em português do Brasil.
- Mensagens apresentadas ao usuário devem ser escritas em português do Brasil.
- Identificadores de código, nomes de classes, funções, métodos, arquivos e variáveis devem ser escritos em inglês.
- Termos técnicos consolidados podem permanecer em inglês quando a tradução prejudicar a clareza.
- Não misture português e inglês no mesmo identificador.
- Preserve acentos em textos de interface e documentação.
- Salve arquivos Markdown e Python em UTF-8 sem BOM.

## 4. Fontes de verdade

Use as fontes nesta ordem:

1. código atual do repositório;
2. este `AGENTS.md`;
3. documentação da pasta `documentation/`;
4. migrations e modelos do banco;
5. artigo acadêmico do projeto;
6. suposições do agente.

Quando houver divergência, o código atual descreve o que existe, enquanto a documentação pode descrever a intenção futura. Não apresente uma funcionalidade planejada como implementada.

Atualize a documentação quando uma alteração modificar comportamento, arquitetura, banco, módulos, voz, interface, segurança ou limitações.

## 5. Documentos obrigatórios por área

Atenção a documentação pode ser alterada ou estar incompleta, ou desatualizada na fase atual de desenvolvimento.
Caso seja relevante, e tenha mudanças de regras no meio do desenvolvimento altere a documentação.


Leia os documentos relacionados antes de trabalhar:

- Visão geral: [`documentation/introduction.md`](documentation/introduction.md)
- Arquitetura: [`documentation/architecture.md`](documentation/architecture.md)
- Módulos: [`documentation/modules.md`](documentation/modules.md)
- Banco de dados: [`documentation/database.md`](documentation/database.md)
- Interface: [`documentation/ui.md`](documentation/ui.md)
- Voz: [`documentation/voice.md`](documentation/voice.md)
- Rotinas: [`documentation/routines.md`](documentation/routines.md)
- Credenciais: [`documentation/vault.md`](documentation/vault.md)
- Comunidade: [`documentation/community.md`](documentation/community.md)
- Limitações: [`documentation/limitation.md`](documentation/limitation.md)
- Fluxo e evolução: [`documentation/roadmap.md`](documentation/roadmap.md)
- Origem e inspiração: [`documentation/inspiration.md`](documentation/inspiration.md)

## 6. Arquitetura adotada

O projeto utiliza uma arquitetura modular em camadas.

Não descreva o projeto como uma implementação completa de Clean Architecture. A organização atual busca separação suficiente para manutenção e substituição de tecnologias, sem introduzir abstrações desnecessárias.

Responsabilidades principais:

- `core/`: orquestração e regras centrais de execução.
- `services/`: integrações técnicas e serviços externos ou substituíveis.
- `repositories/`: acesso e consultas ao banco de dados.
- `database/`: configuração do SQLite, modelos SQLAlchemy, inicialização e seeds.
- `api/`: rotas FastAPI finas, quando necessárias.
- `ui/`: interface desktop Flet, estado visual e eventos de interação.
- `modules/`: módulos locais, contratos e implementações padrão.
- `migrations/`: histórico de alterações estruturais do banco.
- `util/`: funções auxiliares genéricas e sem regra de negócio.
- `documentation/`: documentação pública para humanos e agentes.

## 7. Regras de dependência

Preserve estas direções:

- A interface pode chamar serviços de aplicação, mas não deve concentrar regra de negócio.
- Repositories acessam SQLAlchemy e modelos do banco.
- Serviços de integração não devem conhecer controles visuais do Flet.
- Módulos não devem depender da interface da IRIS.
- O núcleo não deve depender de detalhes visuais.
- Rotas FastAPI devem validar a entrada e delegar a execução.
- Funções utilitárias não devem importar `ui`, `database`, `repositories` ou módulos de domínio.
- Evite dependências circulares.

O código atual pode conter transições arquiteturais. Não aumente o acoplamento para imitar uma regra ideal. Prefira corrigir gradualmente e preservar o funcionamento existente.

## 8. Regras de implementação

Ao implementar uma funcionalidade:

1. identifique a responsabilidade da funcionalidade;
2. localize a camada apropriada;
3. reutilize componentes e serviços existentes;
4. mantenha funções pequenas e focadas;
5. adicione tipagem nas interfaces públicas;
6. trate erros próximos da fronteira em que podem ser apresentados ou registrados;
7. registre execuções de módulos;
8. não bloqueie a thread da interface com operações demoradas;
9. atualize a documentação relacionada;
10. teste o fluxo principal e os caminhos de erro.
11. Não altere nada e não leia a pasta voice_tests

Prefira código explícito, legível e direto. Não crie interfaces, factories, adapters ou abstrações sem necessidade concreta.

## 9. Convenções de código

- `snake_case`: arquivos, funções, métodos e variáveis.
- `PascalCase`: classes.
- `UPPER_CASE`: constantes.
- Prefixo `build_`: funções que constroem controles ou estruturas.
- Prefixo `on_`: callbacks de eventos.
- Prefixo `_`: membros internos.
- Imports absolutos a partir da raiz do projeto.
- Uma responsabilidade principal por módulo Python.
- Evite funções extensas com múltiplos níveis de aninhamento.
- Mensagens de erro devem explicar o problema e, quando possível, indicar a ação corretiva.
- Não remova comentários que documentam decisões ainda relevantes.
- Não introduza formatação incompatível com o estilo existente sem necessidade.

## 10. Banco de dados

O banco atual é SQLite, acessado por SQLAlchemy.

Entidades atuais:

- `Module`;
- `Routine`;
- `RoutineAction`;
- `Log`.

Regras:

- Novas alterações estruturais devem ser realizadas por migrations do Alembic.
- Não altere uma migration que já possa ter sido aplicada.
- Não adicione novas correções permanentes por `ALTER TABLE` manual em `database/db.py`.
- Seeds devem ser idempotentes.
- Não versione `iris.db`.
- Não armazene chaves, tokens ou senhas em texto puro.
- Não exclua registros de histórico silenciosamente.
- Mudanças em relacionamentos exigem revisão de cascade, nulabilidade e migração de dados.
- O código atual ainda contém compatibilidade de esquema e seed na inicialização; trate isso como dívida técnica existente, não como padrão para novas alterações.

## 11. Módulos

Um módulo representa uma capacidade da IRIS. Módulos e submódulos são armazenados na mesma entidade e relacionados por `parent_module_id`.

Campos relevantes:

- `name`;
- `call_name`;
- `custom_call_name`;
- `description`;
- `request_method`;
- `request_url`;
- `is_executable`;
- `parent_module_id`.

Regras:

- Um item organizacional pode não ser executável.
- Somente módulos com `is_executable=True` podem disparar ações.
- Entry points Python devem retornar um dicionário estruturado quando possível.
- O resultado deve conter `success` e pode conter `message`, `result` ou `opened`.
- Erros devem ser propagados para que o núcleo registre a falha.
- Não execute código de módulos desconhecidos sem validação.
- Preserve a independência entre módulos e a interface.
- O método chamado `GET` no código atual abre uma URL no navegador; não suponha que ele já realize uma requisição HTTP real.
- A instalação e a distribuição comunitária de módulos ainda não possuem contrato definitivo. Não invente um formato sem registrar uma decisão.

## 12. Interface

A interface usa Flet e foi projetada inicialmente para desktop Windows.

Regras:

- Preserve a identidade visual clara, leve e em cores pastéis.
- Use as constantes de `ui/theme/colors.py`.
- Reutilize toaster, tabelas, diálogos, header, sidebar e controles existentes.
- Não duplique estilos entre telas quando um componente compartilhado for adequado.
- Operações lentas devem rodar fora da thread visual.
- Atualizações disparadas por threads de áudio ou rede devem ser encaminhadas com segurança para a página Flet.
- Textos visíveis devem permanecer em português do Brasil.
- Estados de carregamento, sucesso, erro, vazio e indisponibilidade devem ser apresentados de forma clara.
- A futura tela de documentação deverá consumir os arquivos da pasta `documentation/`, sem manter cópias divergentes do conteúdo.

## 13. Voz

O reconhecimento de voz ainda não está implementado no código atual. `services/speech_service.py` é apenas um contrato provisório.

Direção planejada:

- RealtimeSTT para captura e atualizações parciais;
- Faster-Whisper como mecanismo local de transcrição;
- detecção de atividade de voz;
- palavra de ativação “IRIS”;
- escrita progressiva no input;
- filtragem progressiva de módulos;
- conclusão por silêncio ou pela palavra “enviar”.

Regras:

- Não apresente o fluxo de voz como concluído.
- Não coloque processamento de áudio dentro da camada visual.
- O modelo de transcrição deve ser carregado uma vez e reutilizado.
- A captura deve possuir ciclo de inicialização e encerramento.
- Texto parcial substitui o texto provisório anterior; não concatene resultados completos repetidos.
- A palavra “IRIS” deve ativar a interação, mas não deve fazer parte da consulta final do módulo.
- Um único resultado pode ser pré-selecionado, mas não deve ser executado prematuramente enquanto o usuário ainda fala.
- Configurações técnicas devem ter valores padrão seguros.

## 14. Rotinas

As entidades de rotina existem no banco, mas o fluxo completo de agendamento e edição ainda não está finalizado.

Não afirme que há scheduler ativo sem verificar a implementação.

Uma rotina deve:

- possuir nome;
- conter módulos ordenados;
- permitir ativação e desativação;
- registrar execução;
- interromper ou registrar adequadamente falhas;
- possuir comportamento definido para continuidade após erro.

Decisões ainda não tomadas devem ser registradas antes da implementação.

## 15. Credenciais e BYOK

O projeto adota conceitualmente BYOK, no qual cada usuário fornece suas próprias credenciais.

A implementação do cofre ainda não está concluída.

Regras absolutas:

- nunca incluir credenciais reais em código, documentação, logs ou testes;
- nunca versionar `.env`;
- nunca persistir segredo em texto puro;
- ocultar valores sensíveis na interface;
- evitar incluir segredo em exceções;
- não inventar criptografia própria;
- documentar o ciclo de vida antes de implementar armazenamento.

## 16. Documentação

Todo arquivo de `documentation/` deve:

- ser escrito em português do Brasil;
- usar linguagem clara para usuários e agentes;
- explicar termos técnicos na primeira ocorrência;
- distinguir “atual” de “planejado”;
- evitar promessas não implementadas;
- usar links relativos entre documentos;
- preservar títulos estáveis para a futura navegação na interface;
- não depender de elementos exclusivos do GitHub para ser compreendido;
- ser atualizado junto com o código relacionado.

Se uma seção ainda não foi definida, use um comentário HTML de placeholder em vez de inventar o conteúdo:

```html
<!-- Conteúdo futuro: decisão ainda não definida. -->
```

## 17. Ambiente atual

Versão principal de desenvolvimento:

- Python 3.11;
- Flet 0.85.3;
- SQLAlchemy 2.0.51;
- Alembic 1.18.5;
- FastAPI 0.138.1;
- Uvicorn 0.49.0;
- HTTPX 0.28.1.

Comandos no Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Para migrations:

```powershell
alembic current
alembic history
alembic upgrade head
```

Não execute `alembic revision --autogenerate` sem revisar os modelos e o diff gerado.

## 18. Arquivos que não devem ser versionados

- `.venv/`;
- `__pycache__/`;
- `*.pyc`;
- `.idea/`, salvo quando houver uma decisão explícita;
- `iris.db`;
- `*.db-journal`;
- `*.db-shm`;
- `*.db-wal`;
- `.env`;
- arquivos de áudio temporários;
- modelos baixados, salvo decisão explícita;
- credenciais e tokens.

## 19. Anti-padrões proibidos

- lógica de negócio extensa na UI;
- acesso ao banco espalhado por controles Flet;
- controllers ou rotas FastAPI com lógica pesada;
- serviços que manipulam diretamente componentes visuais;
- módulos acoplados ao banco interno da IRIS;
- execução automática de código comunitário sem validação;
- armazenamento de segredos em texto puro;
- criação de abstrações apenas para “seguir um padrão”;
- alteração silenciosa do idioma da interface;
- documentação que descreve funcionalidades inexistentes;
- chamadas bloqueantes longas na thread principal.

## 20. Checklist antes de concluir uma tarefa

Confirme:

- [ ] A alteração está na camada correta.
- [ ] O comportamento atual foi preservado quando necessário.
- [ ] Não foi criada dependência circular.
- [ ] Operações lentas não bloqueiam a UI.
- [ ] Erros relevantes são registrados e apresentados.
- [ ] Nenhum segredo foi incluído.
- [ ] Alterações de banco possuem migration.
- [ ] Textos visíveis estão em português do Brasil.
- [ ] Identificadores de código estão em inglês.
- [ ] A documentação relacionada foi atualizada.
- [ ] Funcionalidades planejadas não foram descritas como prontas.
- [ ] O fluxo principal foi testado.
