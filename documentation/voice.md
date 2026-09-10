# Reconhecimento de voz

## Objetivo

A IRIS oferece reconhecimento local de voz em dois níveis de desempenho. Os dois modos reutilizam o mesmo fluxo visual e o mesmo processador dos comandos digitados.

## Estado atual

O código possui dois serviços funcionais:

```text
SpeechService
├── FasterWhisperSpeechService
└── RealtimeSpeechService
```

- `FasterWhisperSpeechService`: modo básico, com captura por `sounddevice`, detecção simples de volume e transcrição ao final da frase;
- `RealtimeSpeechService`: modo avançado, com RealtimeSTT, Faster-Whisper, VAD e atualizações parciais;
- `SpeechServiceManager`: mantém uma única instância ativa, distribui eventos e encerra o microfone junto com a aplicação;
- `VoiceSettingsService`: carrega e salva a configuração persistida.

As bibliotecas e modelos precisam estar instalados. O primeiro uso de um modelo pode exigir internet para download. A precisão e o desempenho ainda dependem de validação em diferentes microfones e computadores.

## Modos

### Básico

O modo básico é o padrão quando a voz é habilitada.

Fluxo:

1. o microfone entrega blocos de áudio;
2. o limiar de volume identifica o início da fala;
3. o tempo de silêncio encerra a frase;
4. o áudio completo é enviado ao modelo Faster-Whisper já carregado;
5. o texto final é interpretado como ativação ou comando.

Esse modo usa menos componentes e não produz texto parcial. Assim que o limiar de volume inicia a captura, o input apresenta “Ouvindo...” como retorno visual. A palavra de ativação ainda só pode ser confirmada depois do silêncio e da transcrição final.

Nesta etapa, o modo básico aceita somente áudio de entrada em 16.000 Hz, pois entrega um array NumPy diretamente ao Faster-Whisper. No Windows, a IRIS primeiro tenta abrir o microfone selecionado nesse formato. Quando o endpoint usa WASAPI e não aceita 16.000 Hz diretamente, a aplicação pode solicitar ao mixer compartilhado do Windows a conversão automática da taxa, mantendo o mesmo dispositivo selecionado.

Essa compatibilidade possui duas estratégias técnicas: `direct_16000` e `wasapi_auto_convert_16000`. Ela nunca representa a troca para outro microfone. Se o dispositivo explicitamente selecionado estiver indisponível ou se as duas estratégias falharem, o modo básico informa o erro e não usa o microfone padrão silenciosamente.

Quando a conversão WASAPI é necessária, o evento de prontidão informa “Voz pronta com ajuste de compatibilidade do Windows” sem apresentar nome ou índice do dispositivo. Na captura direta, a mensagem de prontidão permanece inalterada.

### Tempo real

O modo avançado usa o RealtimeSTT com Faster-Whisper como mecanismo de transcrição. Os callbacks de início e fim de gravação do RealtimeSTT alimentam o mesmo retorno visual “Ouvindo...” usado pelo modo básico.

Por padrão, podem ser carregados:

- um modelo principal para o resultado final;
- um modelo menor para atualizações parciais.

O intervalo parcial, o modelo em tempo real e o `beam size` permitem equilibrar latência e consumo. Intervalos muito baixos ou modelos grandes podem aumentar significativamente CPU, GPU e memória.

A conversão automática WASAPI descrita para o modo básico não é usada pelo RealtimeSTT. A compatibilidade de taxa e a identidade do dispositivo no modo em tempo real continuam dependendo do fluxo próprio dessa biblioteca e exigem validação separada.

## Palavra de ativação

A palavra de ativação é “IRIS”. A implementação reconhece também a grafia “Íris”.

Ela é detectada na transcrição, sem exigir Porcupine, OpenWakeWord ou um modelo adicional. Portanto, a detecção depende da qualidade do Whisper e pode apresentar falsos positivos ou não reconhecer a palavra em ambientes ruidosos.

A aceitação da palavra de ativação fica habilitada durante a aplicação,
independentemente da rota visual e mesmo com a janela oculta. A rota de teste do
microfone permanece um modo de diagnóstico próprio: nela as transcrições são
exibidas sem ativar nem executar comandos.

Antes da ativação, transcrições comuns são ignoradas. Depois da ativação:

- a palavra “IRIS” é retirada da consulta;
- a dica visual muda de “Ouvindo...” para “IRIS ativada” e permanece assim durante o comando;
- o input recebe foco;
- a borda e a sombra ficam roxas;
- o texto parcial substitui o texto provisório anterior;
- as recomendações são recalculadas;
- a dica de ativação fica visível até o comando ser concluído ou cancelado.

Se o usuário editar manualmente o texto durante uma interação ativa, o conteúdo
visível substitui o comando acumulado pelo serviço. As transcrições seguintes
continuam a partir dessa versão corrigida, e apagar o input impede que trechos
antigos reapareçam. Atualizações programáticas produzidas pela própria voz não
disparam essa sincronização de volta para o serviço.

O retorno “Ouvindo...” indica apenas que uma frase está sendo capturada. Ele não significa que a palavra “IRIS” já foi reconhecida. Não é necessário clicar no input: enquanto a voz está habilitada e a rota permite comandos, a captura permanece pronta para detectar fala.

## Conclusão por voz

Um comando resolvido de forma inequívoca é executado automaticamente depois de
dois segundos adicionais sem fala ou edição. Esse atraso é independente de
`silence_duration`, que pertence ao transcritor e apenas encerra a frase.
`silence_duration` define quando uma fala terminou; `submit_delay`, atualmente
fixado em 2 segundos na Home, é a espera adicional antes da execução automática.

A resolução aceita tanto o caminho falado completo quanto o nome isolado de uma
folha executável. Por exemplo, “verde” pode resolver `Abrir / Web / Verde` quando
essa correspondência é única. Falar o nome de um grupo como “web” não escolhe
silenciosamente entre seus descendentes: quando existem vários executáveis, a
Home mostra as opções e aguarda uma escolha.

Nova fala ou edição cancela a espera anterior. Ao terminar o atraso, a Home
resolve novamente o texto atual e confirma que a sessão de voz, a rota, a
pré-seleção, o argumento e o estado de execução continuam válidos. Comandos
ambíguos, módulos organizacionais, argumentos obrigatórios vazios e pesquisas
com vários argumentos permanecem aguardando interação. Quando a pesquisa de
argumentos retorna uma única opção, ela é pré-selecionada antes do envio.

Uma sugestão de argumento ainda não equivale a uma confirmação. Pesquisas
pendentes ou com mais de um resultado impedem o envio automático. Um resultado
único pode ser pré-selecionado e enviado por silêncio somente quando a interação
não começou com um argumento padrão salvo.

Quando o módulo possui argumento padrão salvo, a Home mostra esse valor, mas
exige confirmação explícita por “enviar” ou pelo botão. Essa exigência permanece
durante toda a interação: falar ou editar outro valor substitui apenas o texto
transitório enviado na execução atual e não modifica a configuração persistida.
Por isso, o silêncio também não executa depois dessa substituição.

O envio automático fica bloqueado quando não há módulo, a resolução é ambígua,
o item é apenas organizacional, a Home não está ativa, outra execução está em
andamento, falta um argumento obrigatório, a pesquisa ainda está pendente, há
vários argumentos compatíveis ou existe um argumento padrão salvo.

O comando também pode ser executado imediatamente quando “enviar” aparece no
final da fala.

Exemplo:

```text
IRIS abrir app Spotify enviar
```

O fluxo separa:

```text
Módulo: Abrir / App
Argumento: Spotify
```

O silêncio produz uma transcrição final, mas mantém o modo de voz ativo. Isso permite conferir a recomendação e falar “enviar” em seguida. O usuário também pode confirmar manualmente pelo botão.

## Recomendações progressivas

O texto de voz passa pelo mesmo filtro visual usado na digitação. Quando o início da frase corresponde a um módulo executável, o restante é tratado como argumento.

Exemplo progressivo:

```text
abrir
abrir app
abrir app Spotify
```

No último estado, a IRIS mantém `Abrir / App` como caminho e pesquisa `Spotify` no dropdown de argumentos. Um resultado único não é executado durante a fala.

## Prompt e nomes próprios

Um prompt interno com o nome “IRIS” é sempre aplicado. Ele não aparece no formulário e não pode ser removido pelo usuário.

As configurações permitem acrescentar:

- nomes próprios;
- contexto;
- palavras importantes.

Esses valores são combinados com o prompt fixo. No modo básico, palavras importantes também são encaminhadas como `hotwords` do Faster-Whisper.

Os valores atuais de `Module.call_name` e `Module.custom_call_name` são acrescentados dinamicamente ao prompt interno. Esse contexto não aparece nem é persistido no campo editável, evitando que a configuração fique desatualizada quando módulos forem adicionados ou alterados.

## Configurações disponíveis

A rota de configurações possui as abas:

- configurações gerais;
- configuração de voz;
- senhas.

Somente voz possui formulário completo nesta etapa.

Grupos configuráveis:

- ativação, modo, idioma e microfone;
- modelo final e modelo em tempo real;
- CPU, CUDA e tipo de computação;
- taxa de amostragem, limiar, silêncio e duração mínima;
- VAD, Silero e WebRTC;
- intervalo parcial e `beam size`;
- temperatura e uso de texto anterior no modo básico;
- nomes próprios, contexto e palavras importantes.

O padrão seguro mantém a voz desativada. Ao habilitar, o padrão de baixo custo é CPU, `int8`, modelo `small` para o resultado final e `tiny` para tempo real.

O microfone é escolhido por uma lista que mantém uma entrada por dispositivo físico e uma opção separada para o microfone padrão do sistema. No Windows, o botão “Recarregar” executa uma sondagem curta do PyAudio em um processo isolado para obter os endpoints WASAPI conectados naquele momento. O processo principal continua usando `sounddevice` para captura e visualização, evitando inicializar simultaneamente duas implementações do PortAudio no aplicativo. Não existe um monitor periódico de dispositivos em segundo plano.

A tela mantém separadamente o microfone salvo e o microfone selecionado no formulário. O visualizador acompanha primeiro o selecionado, mesmo antes de salvar; se não houver seleção, usa o índice salvo; se também não houver índice salvo, não inicia captura para visualização. Uma falha isolada de captura no visualizador não altera a seleção. Quando nenhuma entrada existe, a lista fica vazia, o campo fica bloqueado e o índice persistido também é removido. O botão “Deletar microfone” permite remover explicitamente o índice salvo e limpar a seleção ativa. Falhas de enumeração ou captura são tratadas sem encerrar a aplicação. Ao salvar o formulário, a IRIS persiste o índice do dispositivo selecionado para o backend de voz. Quando o modo básico é selecionado, o formulário oculta os parâmetros exclusivos do RealtimeSTT, pois eles não alteram esse backend.

Quando o serviço está pronto, a configuração de voz apresenta o botão “Testar microfone”. A rota `/settings/voice_checking` abre um modal de diagnóstico no qual não é necessário dizer “IRIS”:

- o visualizador confirma se há sinal chegando do dispositivo efetivo;
- o modo básico apresenta cada resultado final do Faster-Whisper;
- o modo completo apresenta separadamente o texto parcial do RealtimeSTT e o resultado final do Faster-Whisper;
- as frases reconhecidas ficam visíveis apenas durante a sessão da tela e não são persistidas.

O nível do áudio também aparece abaixo do cartão de estado na configuração de voz. Somente o nível normalizado é encaminhado à interface; o áudio bruto permanece no serviço.

## Ciclo de vida

Ao iniciar a aplicação:

1. as configurações são carregadas do SQLite;
2. o gerenciador de voz é criado;
3. se a voz estiver habilitada, o backend é iniciado em uma thread;
4. o modelo é carregado uma vez e reutilizado;
5. o microfone entra em espera.

Ao salvar alterações, o backend anterior é encerrado e a nova configuração é preparada. Ao fechar ou desconectar a página Flet, o microfone e o worker são encerrados.

Ocultar a janela na bandeja não representa o encerramento da aplicação. Nesse
estado, o backend continua aceitando a
palavra de ativação e executando o fluxo atual de comandos, independentemente da
rota visual. Somente a ação explícita **Sair da IRIS** encerrará o serviço. A
pausa feita pelo menu da bandeja será temporária e não modificará a configuração
persistida. Consulte [Execução em segundo plano](background_execution.md).

Depois que uma execução termina, com sucesso ou erro retornado pelo módulo, os
campos de comando e argumento são limpos para deixar a IRIS pronta para uma nova
interação. O feedback de erro informa explicitamente que o comando foi limpo. O
HUD usa uma orientação curta, enquanto a notificação nativa preserva a mensagem
completa e é tentada mesmo quando a janela está visível.
Bloqueios anteriores à execução, como ambiguidade ou argumento obrigatório
ausente, preservam o texto para permitir correção manual.

Quando habilitado nas Configurações gerais, o indicador flutuante observa os
mesmos eventos persistentes do gerenciador de voz. `ACTIVATED` abre o HUD,
`PARTIAL` e `FINAL` atualizam a transcrição, `DEACTIVATED` e `STOPPED` o ocultam,
e `ERROR` apresenta uma mensagem temporária antes de fechá-lo. A janela nativa
do indicador também apresenta resultados e erros de módulos. Nos erros de
módulo, o HUD aplica uma borda vermelha e mostra apenas uma orientação curta;
os detalhes ficam na notificação do Windows e no histórico. Esses feedbacks têm
um tempo mínimo de exibição e não são ocultados imediatamente pelo evento
`DEACTIVATED`. A janela usa uma thread própria e recebe eventos por fila, sem
executar processamento de áudio.

## Threads e interface

Captura, carregamento de modelo e transcrição ficam em serviços, fora da camada visual. Eventos vindos dos workers são encaminhados pelo agendador da página Flet antes de modificar controles.

A interface não recebe áudio bruto e os serviços não importam componentes visuais.

## Privacidade

O áudio é processado localmente e não é salvo em logs ou arquivos pela IRIS.

Internet ainda pode ser necessária para:

- instalar dependências;
- baixar um modelo pela primeira vez.

Módulos executados depois da transcrição podem possuir integrações externas próprias.

## Erros tratados

O fluxo apresenta mensagens para:

- dependências ausentes;
- microfone indisponível;
- permissão negada;
- falha ao carregar ou baixar o modelo;
- configuração inválida;
- comando falado sem módulo compatível.

Falhas são apresentadas por toaster e não devem derrubar a janela.

## Limitações atuais

- a palavra de ativação é reconhecida pela transcrição, não por um detector dedicado;
- o modo básico não mostra texto durante a fala;
- a enumeração de microfones depende do PortAudio e das permissões disponíveis no sistema;
- CUDA depende das bibliotecas compatíveis instaladas na máquina;
- modelos podem consumir vários gigabytes;
- precisão, latência e falsos positivos ainda precisam de testes práticos ampliados;
- não há síntese de voz.

## Validação

Os testes automatizados cobrem:

- remoção da palavra de ativação;
- bloqueio antes de “IRIS”;
- conclusão por “enviar”;
- preservação do último comando;
- prompt fixo combinado com contexto;
- validação e persistência das configurações;
- separação entre caminho de módulo e argumento.

Testes com microfone e modelos reais são manuais, pois dependem de hardware, permissões e downloads.
