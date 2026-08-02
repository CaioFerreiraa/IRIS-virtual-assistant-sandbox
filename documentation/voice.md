# Reconhecimento de voz

## Objetivo

A voz será uma das principais formas de interação com a IRIS.

O usuário poderá falar um comando e acompanhar o texto aparecendo no input enquanto ainda está falando.

A transcrição parcial permitirá que a lista de módulos seja filtrada progressivamente.

## Estado atual

O reconhecimento de voz ainda não está implementado.

O arquivo `services/speech_service.py` contém apenas métodos provisórios que lançam `NotImplementedError`.

As tecnologias descritas neste documento representam a direção planejada e precisam ser validadas no projeto.

## Tecnologias planejadas

### RealtimeSTT

O RealtimeSTT será responsável por organizar a captura contínua e fornecer callbacks de transcrição parcial e final.

Ele será a camada de tempo real.

Responsabilidades esperadas:

- acessar o microfone;
- detectar início de fala;
- detectar silêncio;
- gerar atualizações parciais;
- estabilizar transcrição;
- acionar callbacks;
- coordenar o Faster-Whisper.

### Faster-Whisper

O Faster-Whisper será o mecanismo local de reconhecimento.

Ele utiliza CTranslate2 para executar modelos Whisper de forma otimizada.

Responsabilidades:

- converter áudio em texto;
- reconhecer português;
- aplicar contexto inicial;
- melhorar nomes próprios;
- produzir transcrição final;
- funcionar em CPU ou GPU conforme configuração.

O Faster-Whisper sozinho não oferece a experiência completa de streaming palavra por palavra. O RealtimeSTT realizará a orquestração necessária.

### VAD

VAD significa detecção de atividade de voz.

Ele ajuda a identificar:

- quando a pessoa começou;
- quando está falando;
- quando parou;
- quais trechos são silêncio.

A IRIS também poderá usar limiar de volume e tempo de silêncio.

### Wake word

A palavra de ativação será:

```text
IRIS
```

No primeiro MVP, ela poderá ser identificada pela transcrição parcial.

No futuro, poderá ser criado um modelo específico de wake word.

## Experiência planejada

Usuário fala:

```text
IRIS, abrir app Spotify
```

Atualizações possíveis:

```text
IRIS
IRIS abrir
IRIS abrir app
IRIS abrir app Spotify
```

Após detectar “IRIS”, a interface deverá retirar a palavra de ativação da consulta.

O input exibirá:

```text
abrir app Spotify
```

## Filtragem progressiva

### Após “IRIS”

O dropdown mostra todos os módulos, como quando o usuário clica no campo vazio.

### Após “abrir”

Mostra módulos e caminhos compatíveis com “abrir”.

### Após “abrir app”

Prioriza caminhos que contenham os dois termos.

### Após “abrir app Spotify”

Prioriza caminhos com todos os termos.

## Comando direto

Usuário fala:

```text
IRIS, Spotify
```

A consulta será:

```text
Spotify
```

A lista deve retornar módulos ou submódulos compatíveis.

## Resultado parcial

A transcrição parcial pode mudar.

Exemplo:

```text
abrir a
abrir app
abrir app spot
abrir app Spotify
```

Por isso, a interface deve substituir o texto provisório inteiro.

Não deve fazer:

```python
input.value += partial_text
```

Deve fazer:

```python
input.value = partial_text
```

## Seleção

O primeiro item do dropdown ficará pré-selecionado.

Ele será executado quando:

- o usuário falar “enviar”;
- o VAD detectar fim da fala;
- o usuário confirmar manualmente.

Ter apenas um resultado não deve disparar imediatamente enquanto há fala ativa.

## Palavra “enviar”

Quando “enviar” aparecer no fim do comando:

1. a palavra é retirada;
2. a transcrição anterior é validada;
3. o primeiro módulo é selecionado;
4. a execução começa;
5. o modo de voz é encerrado.

Exemplo:

```text
IRIS abrir app Spotify enviar
```

Comando utilizado:

```text
abrir app Spotify
```

## Visual planejado

Ao ativar por voz:

- o input recebe foco;
- a borda fica roxa pastel;
- a sombra aumenta;
- ocorre animação de brilho;
- aparece “‘Enviar’ para concluir”;
- o texto é atualizado;
- o dropdown permanece visível.

Esse estado deve acontecer somente para voz.

## Arquitetura recomendada

```text
services/voice/
├── microphone_service.py
├── realtime_transcription_service.py
├── faster_whisper_service.py
└── voice_settings.py

core/
├── voice_controller.py
└── voice_events.py
```

Responsabilidades:

```text
MicrophoneService
    captura áudio

RealtimeTranscriptionService
    produz texto parcial e final

FasterWhisperService
    configura e reutiliza o modelo

VoiceController
    controla estados, wake word e conclusão

UI
    apresenta eventos
```

## Estados

Estados recomendados:

- iniciando;
- aguardando palavra de ativação;
- escutando comando;
- transcrevendo;
- finalizando;
- erro;
- parado.

## Ciclo de vida

Ao iniciar:

1. carregar configurações;
2. inicializar worker;
3. carregar modelo;
4. abrir microfone;
5. entrar em espera.

Ao fechar:

1. interromper captura;
2. cancelar callbacks;
3. encerrar worker;
4. liberar microfone;
5. liberar recursos.

## Configurações previstas

### Básicas

- ativar voz;
- idioma;
- modelo;
- modelo em tempo real;
- dispositivo;
- tipo de computação;
- microfone.

### Captura

- limiar de volume;
- tempo de silêncio;
- tempo máximo;
- intervalo parcial;
- VAD.

### Reconhecimento

- nomes próprios;
- contexto;
- hotwords;
- beam size;
- temperatura;
- texto anterior.

Nem toda opção precisa ser exibida ao usuário comum.

## Prompt fixo

O prompt sempre deverá conter contexto para reconhecer “Íris” e “IRIS”.

Esse trecho será interno e não editável.

O usuário poderá acrescentar nomes próprios e contexto sem remover a base.

## Desempenho

Estratégia inicial:

- modelo pequeno para parcial;
- modelo maior para final;
- CPU com `int8`;
- GPU opcional;
- intervalo parcial moderado.

Atualizações frequentes demais podem aumentar consumo e travar a interface.

## Threads

Callbacks de áudio não devem atualizar controles Flet diretamente sem encaminhamento seguro.

O modelo não deve ser carregado dentro de cada transcrição.

A UI não deve bloquear enquanto o reconhecimento trabalha.

## Privacidade

O objetivo é processar áudio localmente.

Isso reduz a necessidade de enviar voz para terceiros.

Ainda assim:

- modelos podem precisar ser baixados;
- módulos executados podem usar internet;
- logs não devem guardar áudio bruto;
- gravações temporárias devem ser removidas;
- o usuário deve poder desativar o microfone.

## Erros

A interface deve tratar:

- microfone não encontrado;
- permissão negada;
- modelo ausente;
- falha no download;
- memória insuficiente;
- dispositivo incompatível;
- worker encerrado;
- áudio inválido;
- transcrição vazia.

## Validação

Testes futuros devem medir:

- tempo até texto parcial;
- tempo até texto final;
- precisão de “IRIS”;
- falsos positivos;
- ruído;
- nomes próprios;
- comando curto;
- comando longo;
- CPU;
- encerramento;
- impacto na interface.
