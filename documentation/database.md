# Banco de dados

## Tecnologia utilizada

A IRIS utiliza SQLite como banco de dados local.

O SQLite foi escolhido porque:

- não exige servidor;
- funciona em um único arquivo;
- possui baixa complexidade de configuração;
- é adequado para aplicações desktop;
- facilita a instalação da primeira versão;
- permite que os dados permaneçam no computador do usuário.

O acesso é realizado por SQLAlchemy. Alterações estruturais devem ser controladas pelo Alembic.

## Responsabilidades do banco

O banco armazena ou armazenará:

- módulos instalados;
- hierarquia de módulos;
- configurações de execução;
- rotinas;
- ordem das ações de uma rotina;
- logs;
- configurações do usuário;
- metadados de credenciais, sem expor segredos;
- estado de módulos comunitários.

Nem todos esses itens já possuem implementação completa.

## Arquivo local

A configuração atual usa:

```text
sqlite:///iris.db
```

Isso cria `iris.db` no diretório de execução.

O arquivo não deve ser versionado. Cada instalação deve possuir seu próprio banco.

No futuro, o banco deverá ser armazenado em um diretório de dados apropriado do usuário, reduzindo dependência do diretório em que o programa foi iniciado.

## SQLAlchemy

O SQLAlchemy oferece:

- modelos Python;
- relacionamentos;
- sessões;
- consultas;
- controle de transações;
- compatibilidade com migrations.

A aplicação usa `SessionLocal` para criar sessões. Toda sessão aberta deve ser encerrada, inclusive em caso de erro.

## Entidades atuais

### Module

Representa módulos e submódulos.

Campos:

- `id`: identificador;
- `module_public_key`: chave pública obrigatória, única e estável;
- `name`: nome exibido;
- `call_name`: nome padrão usado em comandos;
- `custom_call_name`: nome personalizado;
- `description`: explicação;
- `request_method`: modo de execução;
- `request_url`: destino ou entry point;
- `is_executable`: indica se pode ser executado;
- `is_available`: indica se o módulo pode ser usado;
- `validation_error`: mensagem curta para módulo inválido;
- `manifest_directory` e `readme_path`: caminhos validados do módulo instalado;
- `runtime_type` e `supports_auto_start`: capacidade declarada pelo manifesto;
- `auto_start_enabled`: preferência do usuário;
- `parent_module_id`: módulo pai;
- `created_date`: criação;
- `edited_date`: última edição.

A própria tabela representa uma árvore. Um módulo sem pai fica na raiz. Um módulo com `parent_module_id` é filho de outro.

`module_public_key` é usado pela sincronização do manifesto. O ID numérico continua sendo usado pelas relações internas, rotas e execuções.

### ModuleVariableDefinition

Representa uma variável declarada em `module.json`.

Campos principais:

- `module_id`;
- `key`, única dentro do módulo;
- `label` e `description`;
- `type`;
- `is_required`;
- `is_user_editable`;
- `default_value`;
- `display_order`;
- `is_active`.

Uma definição removida do manifesto fica inativa até existir uma política explícita de exclusão.

### ModuleVariableValue

Armazena um único valor de texto editado pelo usuário para uma definição editável.

Campos:

- `variable_definition_id`, único;
- `value_text`;
- `updated_at`.

Valores não editáveis não precisam de registro e usam o padrão do manifesto. Estas tabelas não podem armazenar credenciais ou outros segredos.

### Routine

Representa uma rotina.

Campos:

- `id`;
- `name`;
- `cron_expression`;
- `active`;
- `last_run_at`;
- `created_at`.

A existência dos campos não significa que o scheduler esteja concluído.

### RoutineAction

Liga uma rotina a um módulo.

Campos:

- `id`;
- `routine_id`;
- `module_id`;
- `execution_order`;
- `active`.

O vínculo permite que uma rotina mantenha uma sequência de módulos.

### Log

Registra uma execução.

Campos:

- `id`;
- `module_id`;
- `routine_id`;
- `status`;
- `message`;
- `created_at`.

O log pode representar uma execução manual ou uma ação vinculada a rotina.

### VoiceSetting

Armazena a configuração local do reconhecimento de voz em um registro singleton de ID `1`.

Grupos de campos:

- ativação e modo;
- modelos final e em tempo real;
- idioma, dispositivo e precisão;
- microfone e captura;
- VAD e sensibilidades;
- parâmetros de reconhecimento;
- nomes próprios, contexto e palavras importantes.

O prompt interno da palavra “IRIS” não é persistido. Ele permanece fixo no código e é combinado em memória com o contexto configurável.

## Relacionamentos

```text
Module
 ├── parent_module
 ├── child_modules
 ├── logs
 └── routine_actions
 └── variable_definitions

ModuleVariableDefinition
 └── value opcional

Routine
 ├── routine_actions
 └── logs

RoutineAction
 ├── routine
 └── module

Log
 ├── module
 └── routine opcional
```

## Inicialização atual

`init_db()` executa três etapas:

1. cria tabelas ausentes com `Base.metadata.create_all`;
2. aplica compatibilidades manuais para bancos antigos;
3. insere ou atualiza módulos padrão legados;
4. antes da abertura do Flet, o registry sincroniza `modules/installed`.

A compatibilidade manual existe devido à evolução inicial do modelo. Ela não deve ser usada como padrão para novas mudanças.

## Seeds

O projeto possui uma árvore inicial de módulos.

O seed atual possui chaves públicas explícitas. A procura normal usa essas chaves. Apenas a adoção única de registros anteriores à nova coluna utiliza `call_name` e pai para substituir a chave temporária `legacy.module-{id}`.

Essa operação precisa permanecer idempotente: iniciar a aplicação várias vezes não pode duplicar os mesmos módulos.

Módulos instalados por manifesto não usam o seed. O registry sincroniza por `module_public_key` e preserva `custom_call_name`, `auto_start_enabled` e valores do usuário.

## Alembic

O Alembic deve controlar novas alterações.

Fluxo esperado:

```powershell
alembic current
alembic revision --autogenerate -m "descricao_da_alteracao"
alembic upgrade head
```

A revisão gerada deve ser conferida antes da execução.

Uma migration deve considerar:

- criação e remoção de colunas;
- valores padrão;
- nulabilidade;
- chaves estrangeiras;
- dados já existentes;
- downgrade possível;
- compatibilidade com SQLite.

A migration do registry é `f8c1d4a7b2e9`. Ela cria as tabelas de variáveis, adiciona os campos do manifesto e reforça a FK da hierarquia com restrição de exclusão.

## Transações

Operações de escrita devem:

1. adicionar ou alterar entidades;
2. chamar `commit`;
3. atualizar a entidade quando necessário;
4. executar `rollback` em falhas que deixem a sessão inválida;
5. encerrar a sessão.

Não mantenha uma sessão global compartilhada indefinidamente entre eventos da interface.

## Foreign keys

O engine executa `PRAGMA foreign_keys=ON` em cada nova conexão SQLite. A migration usa a mesma configuração. A aplicação também rejeita autorreferências e ciclos antes de persistir a hierarquia.

## Logs e transparência

O histórico ajuda o usuário a compreender o comportamento da plataforma.

Todo módulo executável deve gerar registro contendo:

- módulo;
- status;
- mensagem;
- data;
- rotina, quando aplicável.

Logs não devem armazenar:

- senhas;
- tokens;
- chaves de API;
- conteúdo sensível desnecessário;
- cabeçalhos de autenticação.

## Configurações

A tela de voz já persiste:

- idioma de voz;
- modelo de transcrição;
- microfone;
- limiar de áudio;
- tempo de silêncio;
- nomes próprios;
- opções de desempenho;
- opções de desempenho e reconhecimento.

Preferências visuais e outras configurações gerais ainda não possuem modelo definido.

## Credenciais

Credenciais não devem ser armazenadas diretamente nas tabelas atuais.

O banco poderá guardar metadados, por exemplo:

- nome da credencial;
- serviço;
- identificador interno;
- data de criação;
- data de alteração;
- referência ao armazenamento seguro.

O segredo deve permanecer em um mecanismo protegido. Consulte [Cofre e BYOK](vault.md).

## Regras de manutenção

- Não versionar o banco.
- Não editar migrations aplicadas.
- Não usar `ALTER TABLE` manual para toda nova mudança.
- Não criar tabela sem documentar seu propósito.
- Não deixar sessão aberta.
- Não expor segredo em logs.
- Não apagar histórico sem ação explícita.
- Atualizar este documento quando os modelos mudarem.
