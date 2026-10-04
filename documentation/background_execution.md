# Execução em segundo plano

## Estado

Esta funcionalidade está implementada para Windows. A integração automatizada,
o fallback e o ciclo de vida possuem testes; a aparência e o comportamento da
bandeja ainda exigem validação manual em uma máquina Windows.

Este documento registra o primeiro escopo acordado para manter a IRIS disponível
quando sua janela estiver oculta. O objetivo é entregar o ciclo básico de
segundo plano sem ampliar o contrato dos módulos nem introduzir um serviço
separado do Windows.

## Objetivo do primeiro escopo

No Windows, fechar a janela pelo botão `X` oculta-a e mantém o processo
da IRIS ativo na bandeja do sistema quando a opção **Manter a IRIS em segundo
plano** estiver ligada nas Configurações gerais. O reconhecimento de voz, os
runtimes já iniciados e o scheduler de rotinas continuam funcionando no mesmo
processo.

```text
IRIS aberta
   ↓ fechar pelo X
Janela oculta e processo ativo na bandeja
   ↓ abrir pelo menu ou pelo ícone
Mesma janela, rota e estado visíveis novamente
```

Minimizar continua usando o comportamento normal da janela. A aplicação
também continua iniciando com a janela visível.

## Bandeja do sistema

O menu da bandeja possui somente estas ações:

- **Abrir IRIS**: restaura a mesma janela sem trocar a rota ou reconstruir seu
  estado;
- **Pausar voz** ou **Ativar voz**: alterna temporariamente a recepção de
  comandos falados;
- **Sair da IRIS**: encerra o reconhecimento de voz, os runtimes pertencentes à
  aplicação, o scheduler de rotinas e o processo.

A pausa feita pela bandeja vale somente para a execução atual. Ela não altera a
configuração de voz persistida. Um duplo clique no ícone também restaura
a janela.

O HUD e as notificações externas aparecem somente quando a janela da IRIS não
tem foco, inclusive quando está minimizada ou oculta. Ao recuperar o foco, os
overlays são fechados sem repetir avisos antigos. O feedback interno permanece
na janela quando ela está em foco; o histórico e os logs continuam disponíveis.

Ao reconhecer “IRIS”, o HUD claro aparece na parte inferior da tela com
“Ouvindo…”, antes do texto do comando. Ele cresce para acomodar o conteúdo até
o limite da tela e permite rolagem quando necessário. O botão × dispensa
resultados e erros; durante a escuta, cancela a interação atual e qualquer
envio por silêncio pendente. Na entrada da escuta, o HUD sobe suavemente até a
posição final; a animação não reinicia a cada trecho transcrito. Os botões ×
do HUD e do Notify da IRIS destacam-se e mostram o cursor de mão ao passar o
mouse. O HUD não obtém foco. A preferência **Mostrar
indicador flutuante de voz** fica nas Configurações gerais e vem ligada por
padrão.

Se uma fala finalizada não corresponder a um módulo nem ao começo de um nome
conhecido, o HUD informa isso brevemente e volta ao estado “Ouvindo…”. A frase
sem correspondência não é juntada ao próximo comando falado.

O canal de Notify é exclusivo: **Sem Notify**, **Notify da IRIS** ou
**Notificação do Windows**. A escolha não desliga o HUD. Instalações existentes
começam com Notify da IRIS. O popup da IRIS usa uma pilha visual clara: o aviso
mais recente fica na frente, com até dois anteriores parcialmente visíveis.
Cada aviso expira 6,5 segundos após chegar; passar o mouse sobre o aviso da
frente pausa somente seu prazo. Ao fechá-lo, aparece o próximo ainda válido.
Erros idênticos consecutivos são agrupados. Clicar no corpo do aviso abre a
IRIS. O modo Windows usa as notificações da bandeja (`pystray`) e segue a
apresentação e o prazo do sistema. O clique na notificação nativa não abre a
IRIS; essa interação existe no Notify da IRIS. A bandeja permite remover o
aviso atual; o histórico de notificações do Windows segue o sistema. Se a
bandeja estiver indisponível, a preferência não é trocada silenciosamente e a
indisponibilidade aparece nas Configurações gerais.

Ao desligar a opção nas Configurações gerais, a bandeja é encerrada e o botão
`X` volta a fechar a aplicação. A preferência é persistida para as próximas
execuções e vem ligada por padrão para preservar o comportamento existente.
Se a bandeja não puder ser inicializada, o botão `X` também fecha a aplicação.
A janela não pode ser ocultada sem um meio confiável de restaurá-la ou encerrar
o processo.

## Ícone e estados da voz

O ícone da bandeja usa o logo da IRIS. Um pequeno marcador sobre o logo possui
estados estáticos e um tooltip coerente com o reconhecimento de voz:

| Cor | Estado |
| --- | --- |
| Cinza | Voz desativada, pausada ou indisponível |
| Roxo | Voz pronta e aguardando a palavra “IRIS” |
| Verde | Palavra “IRIS” reconhecida e comando em andamento |

Durante um comando em andamento, o marcador verde aumenta e um contorno da
mesma cor envolve todo o ícone para tornar o estado ativo mais visível.

Ao concluir, enviar ou cancelar a interação falada, o marcador retorna ao estado
roxo enquanto o serviço estiver pronto. A primeira versão não tem animação
nem som de estado.

## Comandos com a janela oculta

O primeiro escopo reutiliza as mesmas regras atuais de reconhecimento,
resolução e execução de comandos. Ocultar a janela não interrompe uma
interação de voz em andamento.

Esta etapa não cria:

- políticas de execução em segundo plano por módulo;
- tratamento específico para comandos ambíguos ou incompletos;
- confirmações adicionais;
- atalhos globais;
- inicialização automática com o Windows;
- inicialização diretamente na bandeja.

Esses comportamentos só deverão ser especificados se entrarem em um escopo
futuro.

## Direção de implementação

A integração com a bandeja fica em um serviço isolado da interface
visual e do processamento de comandos. Esse serviço observa os eventos do
gerenciador de voz e traduz apenas os estados relevantes para o ícone.

O ciclo de vida da aplicação distingue duas ações:

- ocultar ou restaurar a janela;
- encerrar definitivamente a aplicação e seus recursos.

O reconhecimento de comandos em segundo plano não depende da rota
visual ativa. A rota de teste do microfone continua sendo um modo próprio de
diagnóstico.

Não existe daemon, serviço do Windows ou segundo processo permanente neste
escopo. Interface, voz, bandeja e runtimes continuam pertencendo ao mesmo
processo desktop.

## Plataforma e validação

O primeiro suporte é exclusivo para Windows. A integração permanece
localizada para permitir estudo posterior de outros sistemas, mas compatibilidade
com Linux e macOS não faz parte desta entrega.

A validação automatizada cobre o ciclo de vida e os estados sem usar recursos
nativos. A validação manual no Windows deve cobrir:

- ocultar pelo `X` sem encerrar voz e runtimes;
- restaurar a mesma janela pelo menu e por duplo clique;
- pausar e reativar a voz sem alterar a configuração persistida;
- refletir os três estados no ícone;
- manter uma interação falada ao ocultar a janela;
- encerrar todos os recursos pela ação **Sair da IRIS**;
- preservar o fechamento normal quando a bandeja falhar ao iniciar.
- dizer “IRIS” sozinha e com comando contínuo nos modos Básico e Tempo real;
- confirmar que HUD e Notify não aparecem com a janela em foco e somem ao
  recuperar o foco;
- conferir altura, rolagem e botão × do HUD com transcrição longa;
- provocar avisos rápidos, repetidos e expirados para verificar a pilha do
  Notify da IRIS;
- alternar entre os três canais e confirmar que somente o escolhido aparece;
- conferir a notificação nativa pela bandeja e seu fechamento ao recuperar o
  foco da IRIS.
