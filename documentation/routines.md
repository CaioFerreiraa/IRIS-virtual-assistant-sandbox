# Rotinas

## Conceito

Uma rotina reúne módulos executáveis em uma sequência ordenada. Ela oferece uma forma alternativa de acionar as mesmas capacidades já disponíveis na Home e na tela de cada módulo.

A execução não possui um mecanismo próprio para Python, HTTP ou abertura de URL. Cada etapa é delegada ao `CommandProcessor`, que continua responsável por validar o módulo, executar e registrar o resultado.

## Estado atual

O fluxo de Rotinas está implementado com:

- criação, edição, ativação, desativação e exclusão lógica;
- execução manual, inclusive quando a rotina está inativa;
- execução automática com APScheduler;
- agendamentos semanais e mensais;
- horário local da máquina;
- módulos ordenados e repetíveis;
- argumento fixo opcional por etapa;
- registro de cada módulo no histórico com o identificador da rotina;
- prevenção de duas execuções simultâneas da mesma rotina.

A rota `/routines` apresenta a listagem, os estados de carregamento, vazio e erro, além do formulário completo em diálogo.

## Agendamento

O usuário não precisa conhecer cron. A interface oferece dois tipos de repetição e um horário no formato `HH:mm`.

### Dias da semana

É possível selecionar um ou vários dias entre segunda-feira e domingo. O seletor múltiplo compacto mostra os dias escolhidos como etiquetas removíveis. O checkbox “Todos os dias” seleciona ou limpa a semana completa.

Exemplos de persistência:

```text
0 8 * * mon,tue,wed,thu,fri,sat,sun
30 18 * * mon,wed,fri
```

### Dias do mês

É possível selecionar um ou vários dias entre 1 e 31. Cada dia é informado em
um campo numérico e incluído pelo botão roxo com ícone de adição. Valores
negativos, decimais, zero e números acima de 31 são rejeitados. Ao informar um
dia acima de 28, a interface avisa que a execução pode não acontecer em todos
os meses.

Exemplo:

```text
0 9 1,15 * *
```

Se o número escolhido não existir em determinado mês, a rotina não é executada naquele mês. O dia 31, por exemplo, é ignorado em fevereiro sem ser tratado como erro.

### Horário local e próxima execução

O scheduler usa o fuso horário local da máquina. Não existe seleção de fuso por rotina nesta versão.

O serviço de agendamento:

- valida os dados do formulário;
- gera a expressão cron persistida em `Routine.cron_expression`;
- interpreta as expressões geradas pela IRIS;
- produz uma descrição amigável;
- calcula a próxima execução.

Expressões antigas ou inválidas são apresentadas como agendamento que precisa ser corrigido. Elas não derrubam a tela, não são carregadas no scheduler e não podem ser ativadas até serem corrigidas.

## Scheduler

O `BackgroundScheduler` é iniciado uma única vez durante a montagem da aplicação. Na inicialização, ele carrega somente rotinas ativas, válidas e não excluídas.

Cada job usa um identificador determinístico no formato `routine-{id}`, `max_instances=1`, `coalesce=True` e tolerância curta para atraso. A IRIS não recupera em massa execuções perdidas enquanto o computador estava desligado.

Criar, editar ou ativar uma rotina sincroniza seu job. Desativar ou excluir remove o job. Uma rotina inválida ou a falha de um job não interrompe as demais. O scheduler é encerrado em `page.on_close` e `page.on_disconnect` junto com os outros serviços da aplicação.

## Módulos e argumentos

Somente módulos com `is_executable=True` podem ser adicionados. Novas etapas também exigem que o módulo esteja disponível.

O mesmo módulo pode aparecer mais de uma vez, inclusive com argumentos diferentes. Quando o módulo aceita argumento, a etapa apresenta um campo próprio. Se o argumento for necessário e as configurações do módulo não fornecerem um padrão suficiente, o campo é obrigatório.

O argumento pertence à `RoutineAction` e não altera a configuração global do módulo. Em módulos HTTP, a execução de rotina não substitui silenciosamente o último argumento salvo na tela do módulo.

Argumentos que aparentam conter token, senha, chave de API ou credencial são rejeitados antes da persistência. O Vault não faz parte desta entrega.

Não existe passagem automática do resultado de uma etapa para a próxima. Cada argumento é um texto fixo configurado previamente.

Se um módulo já associado ficar indisponível ou deixar de ser executável, a rotina continua carregando e a interface identifica a etapa. Na execução, isso produz uma falha controlada.

## Execução e falhas

As etapas ativas são executadas sequencialmente por `execution_order`. O resultado da rotina informa:

- estado final: `success`, `partial` ou `error`;
- total de etapas;
- quantidade executada;
- quantidade de falhas e etapas ignoradas;
- se houve interrupção;
- resumo de cada etapa sem incluir o argumento.

`last_run_at` é atualizado sempre que há uma tentativa de execução da rotina, mesmo quando uma etapa falha.

### Parar se alguma requisição falhar

A opção visível usa o texto “Parar se alguma requisição falhar”, mas a regra vale para qualquer módulo executável.

Quando marcada, a primeira exceção ou retorno com `success=False` interrompe a sequência. As etapas restantes aparecem como não executadas.

Quando desmarcada, a falha é registrada e a rotina continua. O resultado é `partial` quando há sucessos e falhas, ou `error` quando todas as etapas falham.

Falhas esperadas são devolvidas como dados estruturados e não fecham a aplicação.

## Concorrência

Duas execuções da mesma rotina não podem ocorrer ao mesmo tempo, independentemente de terem sido iniciadas manualmente ou pelo scheduler. A segunda tentativa recebe uma mensagem controlada.

Rotinas diferentes podem executar simultaneamente. Cada execução e cada job criam sua própria sessão SQLAlchemy; sessões não são compartilhadas entre threads.

## Persistência e histórico

Criação e edição da rotina e de suas etapas acontecem em uma única transação. A ordem é normalizada para `1..N` antes da persistência.

A exclusão é lógica: preenche `deleted_at`, desativa a rotina e remove o job. A rotina deixa de aparecer nas listagens normais, mas os logs históricos continuam associados a ela.

Cada módulo tentado pelo caminho central gera um registro em `Log` com `routine_id`. Os logs não incluem argumentos, credenciais, corpos completos, cabeçalhos ou query strings de requisições HTTP.

## Limitações atuais

Esta versão não oferece:

- fuso horário por rotina;
- encadeamento de resultados entre etapas;
- repetição automática de uma etapa com falha;
- recuperação em massa de horários perdidos;
- cancelamento de uma execução já iniciada;
- argumentos solicitados interativamente durante uma execução agendada;
- armazenamento de credenciais em argumentos.
