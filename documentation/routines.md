# Rotinas

## Conceito

Uma rotina reúne várias ações em uma sequência.

Enquanto um módulo executa uma capacidade específica, uma rotina permite combinar capacidades para formar um fluxo.

Exemplo conceitual:

```text
Rotina: Início do expediente

1. Consultar agenda
2. Abrir aplicativo de comunicação
3. Enviar mensagem de início
4. Registrar conclusão
```

## Objetivo

Rotinas permitem que o usuário:

- agrupe ações;
- defina ordem;
- programe horário;
- reutilize sequências;
- automatize tarefas recorrentes;
- acompanhe resultados.

## Estado atual

O banco já possui:

- `Routine`;
- `RoutineAction`;
- relacionamentos com `Module`;
- relacionamento com `Log`;
- campo de cron;
- flag de ativação;
- data da última execução.

Isso representa a base de persistência.

O fluxo completo ainda não está concluído. A versão atual não deve ser descrita como possuindo um scheduler operacional sem verificação do código.

## Entidade Routine

Campos:

- `name`: identificação;
- `cron_expression`: programação;
- `active`: ativação;
- `last_run_at`: última execução;
- `created_at`: criação.

## Entidade RoutineAction

Liga módulo e rotina.

Campos:

- `routine_id`;
- `module_id`;
- `execution_order`;
- `active`.

A ordem deve ser determinística. Não devem existir duas interpretações diferentes para a mesma sequência.

## Fluxo planejado

```text
Scheduler
   ↓
Localiza rotinas ativas
   ↓
Valida horário
   ↓
Carrega ações ordenadas
   ↓
Executa módulo 1
   ↓
Registra resultado
   ↓
Executa módulo 2
   ↓
Registra resultado
   ↓
Atualiza rotina
```

## Execução manual

Além do agendamento, uma rotina poderá ser executada manualmente.

Isso será útil para:

- testar;
- confirmar permissões;
- validar argumentos;
- repetir um fluxo;
- diagnosticar falhas.

## Argumentos

Alguns módulos dependem de argumentos.

A rotina precisará armazenar ou resolver:

- valor fixo;
- valor escolhido pelo usuário;
- resultado de ação anterior;
- configuração;
- credencial;
- entrada fornecida no momento.

Esse contrato ainda não foi definido.

## Falhas

O comportamento em erro precisa ser configurável ou documentado.

Possibilidades:

- interromper imediatamente;
- continuar;
- tentar novamente;
- aguardar;
- executar ação de compensação;
- notificar o usuário.

A primeira versão deve escolher uma regra simples e previsível.

## Logs

Uma execução de rotina deve registrar:

- início;
- rotina;
- ações;
- ordem;
- resultado de cada módulo;
- falha;
- duração;
- conclusão.

Credenciais não podem aparecer nas mensagens.

## Agendamento

O campo `cron_expression` foi criado para representar recorrência.

Antes da interface aceitar uma expressão, ela deverá:

- validar formato;
- explicar o próximo horário;
- impedir expressão inválida;
- considerar fuso horário;
- definir comportamento quando o computador estiver desligado;
- definir execução perdida;
- permitir desativação.

## Concorrência

Ainda será necessário decidir:

- se duas execuções da mesma rotina podem coexistir;
- o que fazer quando uma rotina anterior ainda está ativa;
- quantos módulos podem rodar simultaneamente;
- como cancelar;
- como encerrar ao fechar a IRIS.

## Segurança

Rotinas podem executar várias ações sem interação imediata.

Por isso:

- ações destrutivas devem exigir cuidado;
- permissões devem ser visíveis;
- credenciais devem ser controladas;
- módulos desconhecidos não devem entrar silenciosamente;
- alterações críticas podem exigir confirmação;
- o usuário deve conseguir desativar a rotina.

## Interface planejada

A tela de rotinas poderá permitir:

- listar;
- criar;
- editar;
- duplicar;
- ativar;
- desativar;
- excluir;
- ordenar módulos;
- testar;
- consultar histórico;
- visualizar próxima execução.

## Exemplo futuro

```text
Nome: Reunião diária
Horário: dias úteis às 08:50

Ações:
1. Abrir Teams
2. Consultar agenda
3. Enviar lembrete
```

Esse exemplo ilustra a proposta, não uma rotina disponível atualmente.
