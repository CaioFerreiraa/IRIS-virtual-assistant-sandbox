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
- `name`: nome exibido;
- `call_name`: nome padrão usado em comandos;
- `custom_call_name`: nome personalizado;
- `description`: explicação;
- `request_method`: modo de execução;
- `request_url`: destino ou entry point;
- `is_executable`: indica se pode ser executado;
- `parent_module_id`: módulo pai;
- `created_date`: criação;
- `edited_date`: última edição.

A própria tabela representa uma árvore. Um módulo sem pai fica na raiz. Um módulo com `parent_module_id` é filho de outro.

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

## Relacionamentos

```text
Module
 ├── parent_module
 ├── child_modules
 ├── logs
 └── routine_actions

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
3. insere ou atualiza módulos padrão.

A compatibilidade manual existe devido à evolução inicial do modelo. Ela não deve ser usada como padrão para novas mudanças.

## Seeds

O projeto possui uma árvore inicial de módulos.

O seed procura cada módulo por `call_name` e `parent_module_id`. Quando encontra um registro, atualiza propriedades principais. Quando não encontra, cria o item.

Essa operação precisa permanecer idempotente: iniciar a aplicação várias vezes não pode duplicar os mesmos módulos.

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

## Transações

Operações de escrita devem:

1. adicionar ou alterar entidades;
2. chamar `commit`;
3. atualizar a entidade quando necessário;
4. executar `rollback` em falhas que deixem a sessão inválida;
5. encerrar a sessão.

Não mantenha uma sessão global compartilhada indefinidamente entre eventos da interface.

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

## Configurações futuras

A tela de configurações exigirá persistência para recursos como:

- idioma de voz;
- modelo de transcrição;
- microfone;
- limiar de áudio;
- tempo de silêncio;
- nomes próprios;
- opções de desempenho;
- preferências visuais.

Esses modelos ainda não estão definidos.

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
