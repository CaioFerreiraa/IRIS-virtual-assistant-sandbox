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

Esse modo usa menos componentes e não produz texto parcial.

### Tempo real

O modo avançado usa o RealtimeSTT com Faster-Whisper como mecanismo de transcrição.

Por padrão, podem ser carregados:

- um modelo principal para o resultado final;
- um modelo menor para atualizações parciais.

O intervalo parcial, o modelo em tempo real e o `beam size` permitem equilibrar latência e consumo. Intervalos muito baixos ou modelos grandes podem aumentar significativamente CPU, GPU e memória.

## Palavra de ativação

A palavra de ativação é “IRIS”. A implementação reconhece também a grafia “Íris”.

Ela é detectada na transcrição, sem exigir Porcupine, OpenWakeWord ou um modelo adicional. Portanto, a detecção depende da qualidade do Whisper e pode apresentar falsos positivos ou não reconhecer a palavra em ambientes ruidosos.

A aceitação da palavra de ativação fica habilitada na rota Início e na rota de teste do microfone. Nas demais rotas, o backend pode continuar carregado e pronto, mas as transcrições não ativam comandos e qualquer interação de voz em andamento é encerrada.

Antes da ativação, transcrições comuns são ignoradas. Depois da ativação:

- a palavra “IRIS” é retirada da consulta;
- o input recebe foco;
- a borda e a sombra ficam roxas;
- o texto parcial substitui o texto provisório anterior;
- as recomendações são recalculadas;
- a dica “Enviar para concluir” fica visível.

## Conclusão por voz

O comando somente é executado automaticamente quando “enviar” aparece no final da fala.

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

O microfone é escolhido por uma lista das entradas de áudio disponíveis. A opção padrão delega a escolha ao Windows. Quando o modo básico é selecionado, o formulário oculta os parâmetros exclusivos do RealtimeSTT, pois eles não alteram esse backend.

Quando o serviço está pronto, a configuração de voz apresenta o botão “Testar microfone”. A rota `/settings/voice_checking` abre um modal de diagnóstico no qual não é necessário dizer “IRIS”:

- o visualizador confirma se há sinal chegando do dispositivo selecionado;
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
