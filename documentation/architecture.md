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
3. os módulos padrão legados são inseridos ou atualizados;
4. os caminhos dos READMEs dos módulos padrão são associados aos registros legados;
5. `ModuleRegistryService` descobre e sincroniza cada pasta de `modules/installed` isoladamente;
6. o Flet inicia a aplicação;
7. `ui/flet_app.py` monta janela, tema, header, sidebar e área de conteúdo;
8. a rota inicial carrega a tela principal;
9. módulos disponíveis no banco são transformados em opções de pesquisa, enquanto módulos indisponíveis permanecem visíveis para diagnóstico na sidebar;
10. configurações de voz são carregadas;
11. gerenciadores de voz e runtimes habilitados iniciam seus backends em threads isoladas.

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
- persistência de definições e valores não sensíveis de módulos.

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
- ativação de foreign keys por conexão SQLite.

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
- executar uma requisição HTTP declarativa opcional;
- devolver resultado estruturado.
- declarar metadados, README, runtime e variáveis em `module.json`.

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
3. o usuário escolhe uma opção ou envia um texto sem ambiguidade;
4. o serviço da home cria uma sessão de banco;
5. a resolução produz o `module_id` e o `CommandProcessor` carrega esse registro;
6. o sistema valida se o módulo é executável;
7. a Home despacha a operação para background e o core escolhe entre a requisição HTTP declarada, o `ModuleRunner` para Python ou a abertura de URL do `GET` legado;
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

Módulos legados podem usar caminho de pacote. Módulos instalados usam um arquivo validado dentro da própria pasta. O runner procura uma função executável entre:

- `execute`;
- `run`;
- `main`.

O argumento é encaminhado quando a função aceita entrada.

Configurações de texto validadas são encaminhadas pelo parâmetro opcional `variables`. Elas não contêm credenciais.

### Registry e estados

O registry separa quatro estados:

- manifesto do desenvolvedor no sistema de arquivos;
- metadados e preferências persistidos no SQLite;
- status de runtime em memória;
- detalhes técnicos de descoberta e inicialização em `module.log`.

A UI não redescobre pastas ao redesenhar a sidebar. Ela consulta o banco e o snapshot preparado pelo registry.

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

### Requisição HTTP declarativa

Um manifesto pode declarar uma única requisição HTTP simples por meio do campo opcional `http_request`. A definição é validada pelo registry e sincronizada na relação opcional 1:1 `Module.http_request`. O `module.json` permanece como definição distribuível inicial. Enquanto a requisição não tiver sido personalizada, novas sincronizações atualizam o banco pelo manifesto; depois do primeiro salvamento do usuário, o banco passa a preservar a definição local. A ação “Voltar ao module.json” reaplica o manifesto validado e mantém o último argumento utilizado.

O argumento HTTP é uma string persistida separadamente das configurações do módulo, ao salvar a aba Execução ou disparar a requisição, e pode substituir o placeholder literal `{{argument}}` na URL, nos parâmetros, nos cabeçalhos e no body.

O serviço HTTP monta somente os campos habilitados, executa com timeout fixo e redirecionamentos habilitados e devolve status, duração, cabeçalhos e corpo limitado para exibição. Authorization com segredo continua proibida. Scripts vazios são exigidos no manifesto; textos de script personalizados podem ser armazenados localmente e exibidos, mas nunca são executados. Fluxos com múltiplas chamadas ou lógica personalizada continuam pertencendo a runtimes Python.

### Processo externo iniciado por adaptador Python

O runtime reconhecido pelo manifesto continua sendo Python. Um módulo raiz com
auto start pode usar seu `start()` como adaptador mínimo para iniciar um processo
externo e devolver um handle compatível com `subprocess.Popen`. O
`ModuleRuntimeManager` mantém a propriedade desse handle e encerra somente o
processo iniciado pela IRIS.

O módulo comunitário `notes.javascript` aplica esse contrato para iniciar um
servidor Node.js separado. A regra de notas, a API e a página HTML permanecem no
módulo; o núcleo conhece apenas o adaptador Python, o processo devolvido e as
requisições HTTP declaradas pelos filhos. Isso não transforma Node.js em runtime
nativo da IRIS.

### URL

O comportamento legado marcado como `GET` continua abrindo a URL no navegador. Ele não utiliza `ModuleHttpRequest` e não mudou de significado com a execução HTTP declarativa.

A arquitetura distingue:

- abrir URL;
- realizar uma requisição HTTP declarativa;
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

Falhas de descoberta, validação, importação, configuração ou inicialização não entram no histórico de execução. Elas tornam somente o módulo afetado indisponível, aparecem de forma resumida no diagnóstico e são detalhadas no `module.log` local.

Execuções HTTP registram somente método, status e duração. Corpo, cabeçalhos e query string completos não são persistidos no histórico.

A rota do módulo também agrega falhas técnicas dos submódulos na aba “Erro”. Erros de uma execução normal continuam separados nessa decisão: são registrados no SQLite e aparecem na aba “Log”, sem transformar a requisição em falha estrutural do módulo.

## Princípios de evolução

- Reutilizar o fluxo existente antes de criar outro.
- Separar operações demoradas da thread visual.
- Não acoplar módulos ao Flet.
- Não acoplar voz ao controle visual específico.
- Não espalhar sessões de banco sem encerramento.
- Não transformar todo recurso em uma abstração.
- Registrar decisões quando um novo tipo de integração for criado.
- Manter esta documentação compatível com o código real.
