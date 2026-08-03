# Arquitetura da IRIS

## Visão geral

A IRIS utiliza uma arquitetura modular em camadas. Essa organização separa interface, regras de execução, persistência, integrações e módulos, sem tentar aplicar uma implementação completa de Clean Architecture.

A decisão busca equilibrar:

- organização;
- facilidade de manutenção;
- compreensão por novos contribuidores;
- substituição futura de tecnologias;
- baixo nível de complexidade para o escopo do projeto.

A arquitetura não deve ser entendida como um conjunto rígido de abstrações. Cada camada existe para resolver uma responsabilidade real.

## Inicialização atual

O ponto de entrada é `main.py`.

O fluxo atual de inicialização é:

1. `main.py` chama `init_db()`;
2. o SQLite é criado ou atualizado;
3. os módulos padrão são inseridos;
4. o Flet inicia a aplicação;
5. `ui/flet_app.py` monta janela, tema, header, sidebar e área de conteúdo;
6. a rota inicial carrega a tela principal;
7. módulos registrados no banco são transformados em opções de pesquisa;
8. configurações de voz são carregadas;
9. o gerenciador de voz fica pronto e inicia o backend em uma thread quando a voz está habilitada.

## Camadas e responsabilidades

### `core/`

Contém a orquestração principal da aplicação.

Responsabilidades atuais e planejadas:

- validar comandos;
- localizar módulos;
- decidir o tipo de execução;
- executar entry points;
- registrar resultado de módulos;
- coordenar rotinas;
- futuramente coordenar estados de voz.

Arquivos importantes:

- `command_processor.py`;
- `module_runner.py`;
- `logger_service.py`;
- `routine_executor.py`;
- `routes.py`;
- `fatal_error_handler.py`.

O `core` não deve conhecer detalhes visuais do Flet.

### `services/`

Contém integrações técnicas e recursos substituíveis.

Exemplos:

- serviço HTTP;
- acesso a credenciais;
- serviço da tela inicial;
- captura e transcrição de voz;
- integração futura com serviços do sistema operacional.

Serviços podem usar bibliotecas externas, mas não devem manipular controles da interface diretamente.

### `repositories/`

Centraliza acesso ao banco de dados.

Exemplos:

- consulta de módulos;
- criação de logs;
- carregamento de rotinas;
- persistência futura de configurações.

A camada evita que consultas SQLAlchemy sejam espalhadas por toda a aplicação.

### `database/`

Responsável por:

- configuração do SQLite;
- criação do engine;
- sessões SQLAlchemy;
- modelos;
- inicialização;
- seeds;
- compatibilidade temporária de esquemas antigos.

A evolução estrutural deve migrar progressivamente para o Alembic.

### `api/`

Contém rotas FastAPI.

A API deve funcionar como fronteira fina:

1. recebe uma entrada;
2. valida dados básicos;
3. chama `core`, `services` ou repositories adequados;
4. devolve resposta estruturada.

Não deve concentrar regras de negócio.

### `ui/`

Contém a interface Flet.

Responsabilidades:

- montagem da janela;
- roteamento visual;
- componentes;
- estado de telas;
- feedback ao usuário;
- eventos de clique, foco e digitação;
- visualização de histórico;
- futura tela de documentação e configurações.

A interface não deve executar diretamente consultas complexas, processamento de voz ou chamadas demoradas.

### `modules/`

Contém contratos e módulos locais.

Um módulo pode:

- executar código Python;
- pesquisar argumentos;
- abrir um recurso;
- futuramente chamar um serviço HTTP;
- devolver resultado estruturado.

Módulos comunitários devem permanecer independentes do layout interno da interface.

### `migrations/`

Armazena revisões do Alembic.

Cada mudança estrutural nova deve possuir uma migration revisada antes de ser aplicada.

### `util/`

Contém funções pequenas e reutilizáveis que não representam regras da IRIS.

Exemplos:

- normalização de texto;
- conversão numérica;
- formatação genérica.

### `documentation/`

Contém textos para humanos e agentes.

No futuro, a própria interface deverá apresentar esses arquivos em uma aba de documentação.

## Fluxo de comando manual

O fluxo atual de um comando digitado é:

1. o usuário escreve no campo principal;
2. a tela atualiza as sugestões de módulos;
3. o usuário escolhe um caminho ou envia o texto;
4. o serviço da home cria uma sessão de banco;
5. o `CommandProcessor` localiza o módulo;
6. o sistema valida se o módulo é executável;
7. o `ModuleRunner` executa o entry point Python ou o sistema abre a URL configurada;
8. o resultado é transformado em resposta estruturada;
9. um log de sucesso ou erro é salvo;
10. a interface apresenta um toaster;
11. o histórico pode exibir a execução.

## Fluxo atual de voz

O fluxo implementado é:

1. o serviço de voz permanece aguardando a palavra “IRIS”;
2. a palavra de ativação coloca a interface em modo de escuta;
3. a transcrição parcial atualiza o input;
4. cada atualização filtra os módulos;
5. o primeiro resultado é pré-selecionado;
6. o silêncio estabiliza o texto e o usuário encerra falando “enviar” ou confirmando manualmente;
7. o texto final é validado;
8. o mesmo fluxo de execução manual é reutilizado;
9. a interface volta ao estado de espera.

O modo básico entrega somente texto final. O modo em tempo real também entrega texto parcial. A palavra de ativação é identificada pela transcrição e ainda não usa um detector dedicado.

A voz não deve criar um segundo processador de comandos. Entrada manual e entrada por voz devem convergir para o mesmo fluxo.

## Comunicação com módulos

A comunicação depende do tipo do módulo.

### Entry point Python

O módulo é carregado por importação dinâmica. O runner procura uma função executável entre:

- `execute`;
- `run`;
- `main`.

O argumento é encaminhado quando a função aceita entrada.

### Pesquisa de argumentos

Um módulo Python pode oferecer:

- `search_arguments`;
- `searchArguments`.

Os resultados são normalizados para:

```python
{
    "label": "Texto apresentado",
    "value": "Valor enviado",
    "description": "Descrição opcional",
}
```

### URL

O comportamento atual marcado como `GET` abre a URL no navegador. Ele ainda não representa uma implementação completa de comunicação HTTP entre núcleo e módulo.

A arquitetura futura deve distinguir claramente:

- abrir URL;
- realizar `GET`;
- realizar `POST`;
- executar processo local;
- executar entry point Python.

## Resposta estruturada

Módulos devem devolver um dicionário.

Exemplo:

```python
{
    "success": True,
    "message": "Aplicativo aberto com sucesso.",
}
```

Chaves reconhecidas atualmente:

- `success`;
- `message`;
- `result`;
- `opened`.

## Tratamento de erros

Erros de execução devem:

1. interromper o fluxo inválido;
2. ser registrados no histórico;
3. gerar mensagem clara;
4. não derrubar a janela;
5. permitir uma nova tentativa.

O `FatalErrorHandler` protege eventos gerais, enquanto erros esperados de módulo devem ser tratados no fluxo da própria funcionalidade.

## Princípios de evolução

- Reutilizar o fluxo existente antes de criar outro.
- Separar operações demoradas da thread visual.
- Não acoplar módulos ao Flet.
- Não acoplar voz ao controle visual específico.
- Não espalhar sessões de banco sem encerramento.
- Não transformar todo recurso em uma abstração.
- Registrar decisões quando um novo tipo de integração for criado.
- Manter esta documentação compatível com o código real.
