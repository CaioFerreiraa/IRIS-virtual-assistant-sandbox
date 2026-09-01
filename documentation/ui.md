# Interface e identidade visual

## Objetivo da interface

A interface da IRIS deve tornar automações compreensíveis para usuários com diferentes níveis de experiência técnica.

A plataforma não depende apenas de voz. Todas as funções importantes devem possuir representação visual sempre que isso for viável.

## Tecnologia

A interface é desenvolvida com Flet.

A escolha permite:

- construir desktop com Python;
- reutilizar componentes;
- integrar interface e lógica de aplicação;
- manter possibilidade de estudar outros ambientes no futuro.

O MVP está direcionado ao Windows.

## Conceito visual

A identidade visual representa leveza.

A automação pode parecer um assunto técnico e rígido. A IRIS procura apresentar esse universo de maneira clara, amigável e organizada.

As cores representam o arco-íris em tons pastéis. Essa escolha transmite uma seriedade descontraída:

- séria o suficiente para ambientes profissionais;
- leve o suficiente para uma assistente pessoal;
- variada sem ser excessivamente chamativa;
- acolhedora sem perder legibilidade.

## Paleta atual

A paleta inclui:

- vermelho pastel;
- amarelo pastel;
- verde pastel;
- azul pastel;
- roxo pastel;
- roxo escuro;
- superfícies claras;
- textos em cinza escuro;
- bordas suaves.

Uso semântico:

- verde: confirmação;
- vermelho: erro ou cancelamento;
- amarelo: aviso;
- azul: destaque suave;
- roxo: identidade e ação principal.

As telas devem usar constantes de `ui/theme/colors.py`.

## Logo

A logo utiliza uma forma inspirada em uma rosa dos ventos.

A rosa dos ventos representa o caminho que o usuário decide seguir.

A IRIS não determina uma única direção. Ela apresenta capacidades e encaminha a escolha do usuário ao módulo correto.

O símbolo também se relaciona ao papel de guia da plataforma.

## Estrutura atual

### Header

O header contém:

- logo;
- navegação principal;
- indicador do estado do reconhecimento de voz;
- ações da janela.

O indicador de voz abre um diálogo ao ser clicado, independentemente do estado atual. O diálogo lista os estados possíveis do microfone com seus ícones e cores, destacando o estado ativo. Seu tooltip também descreve se o backend está carregando, com erro, pronto no modo básico, pronto no modo completo, desativado, indisponível ou pausado fora das rotas autorizadas. Durante uma ativação por “IRIS”, o indicador recebe uma sombra luminosa na cor do estado atual. No modo básico, o input também apresenta “Ouvindo...” enquanto uma frase é capturada; esse retorno antecede a transcrição final e não confirma por si só a palavra de ativação.

### Sidebar

A sidebar apresenta os módulos em uma árvore recolhível: cada submódulo
fica dentro do menu de seu pai, sem alterar a rota numérica usada na navegação.
O item ativo mantém seus ancestrais expandidos, exceto quando o usuário
recolhe explicitamente um deles. Clicar em qualquer item que possui filhos
sempre alterna a exibição dos submódulos e mantém a navegação para a tela do
módulo pai.

Os itens listados usam cantos retos, tamanho fixo, ficam encostados uns aos
outros e mantêm o mesmo padding horizontal em qualquer profundidade. Nomes
longos usam a quebra de linha nativa do Flet dentro do limite do item. Quando
existe, `custom_call_name` aparece entre parênteses como texto secundário logo
após o nome do módulo. O item selecionado exibe somente uma linha roxa, poucos
pixels abaixo do nome; sua borda externa não muda.

O ícone aparece primeiro e mantém sempre as mesmas cores, sem variar conforme o
estado do módulo. Entre ele e o nome fica uma bolinha de status pequena:
`GREY_900` para módulos offline, verde para módulos online e vermelha para
módulos com problema. Itens organizacionais sem problema não exibem a bolinha.
Módulos inválidos sem item na árvore continuam com o indicador vermelho na área
de diagnóstico.

Módulos raiz usam sempre `SURFACE`. Submódulos não ganham recuo adicional e
escurecem conforme a profundidade: `GREY_100` (`#F5F6FA`), `GREY_200`
(`#E4E7F2`), `GREY_300` (`#D3D8EA`), `GREY_400` (`#C2C8E1`) e `GREY_500`
(`#B0B9D9`). Profundidades adicionais permanecem em `GREY_500` para preservar
contraste e legibilidade. O primeiro filho de cada pai recebe uma sombra leve
na cor de fundo do pai para reforçar visualmente a profundidade da árvore.

A `ListView` alcança as laterais internas do painel e expande verticalmente para
usar todo o espaço disponível. Sua área externa também usa `SURFACE`, inclusive
abaixo do último item quando a lista não ocupa toda a altura.

Ao navegar para outra rota, a árvore visual e a `ListView` permanecem montadas.
Somente os itens e o estado ativo são atualizados, preservando a posição de
rolagem sem saltos visíveis.

Ao manter o ponteiro sobre um item, o tooltip apresenta o nome do módulo e um
resumo de até três linhas do README, com reticências quando houver mais texto.
O README é lido durante a sincronização do registry e mantido em memória; a
sidebar não consulta o sistema de arquivos em cada renderização. Módulos
legados usam a descrição persistida como fallback.

A borda direita da sidebar pode ser arrastada horizontalmente entre limites
seguros. A largura permanece durante a navegação da sessão e a área da rota se
ajusta ao espaço restante.

### Área de conteúdo

A área principal muda conforme a rota.

Rotas atuais ou planejadas:

- início;
- comunidade;
- rotinas;
- histórico;
- configurações;
- documentação.
- módulo: `/modules/{module_id}`.

### Home

A home possui:

- título;
- campo de comando;
- botão de envio;
- botão para limpar;
- lista de módulos;
- lista de argumentos;
- logo de fundo.

O ícone à esquerda do input acompanha o módulo selecionado. As sugestões também
usam o ícone persistido; quando não há seleção, o input mostra `explore`.

A pesquisa considera nome exibido, `call_name` e `custom_call_name`. A seleção visual mantém o `module_id`; comandos ambíguos não são executados automaticamente. O campo secundário usa uma instrução genérica porque pode receber arquivos, cidades ou outros tipos de argumento. Módulos com busca pedem esse valor por padrão, mas podem usar `should_request_argument(variables)` para dispensá-lo quando uma configuração já fornece o valor necessário. A execução acontece em background para manter a interface responsiva.

### Tela do módulo

A rota `/modules/{module_id}` monta a tela consultando o banco e o estado preparado pelo registry. O cabeçalho usa o ícone Material Symbols Rounded do módulo. Em execuções Python e legadas, o botão primário “Executar” aparece à esquerda do status; em módulos HTTP, o mesmo botão fica junto de método e URL na aba “Execução”. O conteúdo é dividido em abas:

- **Sobre**: descrição, README quando existe e `module.json` formatado com fonte Consolas quando existe;
- **Execução**: aparece somente em módulos executáveis, concentra o argumento e permite personalizar a definição HTTP quando existe;
- **Configurações**: primeiro apresenta `call_name` em modo de leitura, `custom_call_name` editável e, somente para módulos raiz, a opção “Iniciar com a IRIS”; depois mostra os dados persistidos do módulo em formato de formulário e as variáveis editáveis quando existirem;
- **Log**: aparece somente em módulos executáveis e lista as execuções do módulo, usando a mesma tabela do histórico;
- **Erro**: aparece somente para falhas técnicas de descoberta, validação, importação, configuração ou inicialização do módulo ou de um submódulo. Quando existe, fica em primeiro lugar e é selecionada inicialmente.

O switch “Iniciar com a IRIS” aparece somente para módulos raiz. Ele só fica habilitado para runtime Python raiz que declara `supports_auto_start`; nos demais casos, a própria tela explica por que a opção está desabilitada. Erros normais ocorridos durante uma requisição permanecem apenas no histórico e não criam a aba de erro.

Na aba “Execução”, o card “Argumento da execução” aparece primeiro e ocupa a
largura disponível. Módulos Python mantêm o argumento transitório e o fluxo
atual, sem um card informativo adicional. Módulos HTTP mostram método, URL, a
ação “Voltar ao module.json” e o único botão “Executar”, seguidos das subabas
“Parâmetros”, “Autorização”, “Cabeçalhos”, “Corpo” e “Scripts”. Todos os campos
da definição HTTP podem ser editados. Params e Headers usam linhas com estado,
chave, valor e descrição, incluindo ações para adicionar ou remover itens;
Authorization usa o seletor “Sem autenticação”; o body separa modo e conteúdo;
scripts são textos armazenados, mas não executados. Quando qualquer campo muda, a barra flutuante “Salvar
requisição” aparece da mesma forma que a barra da aba “Configurações”. Salvar
mantém a personalização no banco; executar salva alterações pendentes antes da
chamada. “Voltar ao module.json” restaura a definição distribuída e preserva o
último argumento utilizado.
Quando `argument_enabled` é falso, o campo fica desabilitado e explica que o
módulo não utiliza argumento de execução. Módulos executáveis indisponíveis
mantêm a aba visível, com controles desabilitados e o motivo apresentado.
Ao executar pela tela, um card entra com animação acima das abas e mostra o
status e o corpo estruturado completo do retorno. O corpo pode ser recolhido ou
exibido novamente por um botão de seta no cabeçalho do card. O status do
cabeçalho mantém a mesma altura do botão “Executar”. O usuário também pode
arrastar a borda inferior para redimensionar verticalmente o card; a altura
mínima preserva somente o cabeçalho, e o corpo rolável ocupa o espaço escolhido
sem receber uma altura fixa do fluxo de execução.

Na demonstração Notas, o módulo raiz não possui aba “Execução” e apresenta o
switch de auto start em “Configurações”. Seus quatro filhos possuem aba
“Execução”; os três filhos HTTP exibem a definição estilo Postman e o filho
“Abrir notas” abre a página externa servida pelo backend local.

O card “Dados do módulo” fica sempre no fim da aba “Configurações”. Ele lista em
modo desabilitado todas as colunas mapeadas pela entidade `Module`; novas colunas
do modelo passam a aparecer automaticamente. O tooltip do input continua
mostrando seu valor, enquanto o ícone de informação explica o significado do
campo.

O botão “Salvar configurações” aparece somente quando existem alterações
pendentes e permanece flutuante no centro inferior da aba para evitar que o
usuário precise rolar até o fim do formulário. A tela compara os snapshots
`module_state_saved` e `module_state_edited`; o segundo começa nulo e é preenchido
quando um campo editável de Configurações muda. O argumento pertence à aba
“Execução” e não participa desse snapshot nem da barra de Configurações. O
a requisição HTTP completa possui um snapshot próprio da aba Execução;
argumentos Python continuam temporários e são enviados somente na execução.

IDs inexistentes ou inválidos exibem “Módulo não encontrado”. Módulos inválidos sem ID aparecem no diagnóstico da sidebar com pasta, mensagem curta e caminho do `module.log`, sem traceback.

### Histórico

Apresenta registros em tabela responsiva que ocupa toda a área disponível da
rota. As colunas são distribuídas por peso para acompanhar a largura da linha,
com reticências e tooltip quando o conteúdo não couber.

A tela possui uma barra de pesquisa que filtra os registros por ID, data,
módulo, rotina, status e mensagem. A pesquisa ignora diferenças entre
maiúsculas, minúsculas e acentos.

Campos:

- ID;
- data;
- módulo;
- rotina;
- status;
- mensagem.

## Componentes compartilhados

### Conteúdo de rota

`build_route_content_container`, definido em
`ui/shared/components/route_content_container.py`, é o shell visual comum das
rotas. Ele centraliza margem, padding, superfície, borda, raio e o cabeçalho com
ícone, título, subtítulo e ação opcional à direita.

Somente `content` é obrigatório. `icon`, `title`, `subtitle`, `trailing` e
`expand` são
opcionais; quando nenhum elemento de cabeçalho é informado, o componente
renderiza apenas o conteúdo no shell padrão. Título e subtítulo também aceitam
um controle Flet, permitindo preservar elementos como o breadcrumb da tela de
módulo.

Home, Histórico, Configurações, Documentação, detalhes de módulo e rotas em
desenvolvimento usam esse componente. O teste de voz continua apresentado
como modal, mas o card interno também utiliza o mesmo shell.

### Toaster

Apresenta:

- sucesso;
- erro;
- aviso;
- informação.

O toaster deve usar mensagens curtas e úteis.

### Card de resultado

`build_result_card`, definido em `ui/shared/components/result_card.py`, monta um
card com status, corpo estruturado, cabeçalho fixo e botão de seta para alternar
a exibição do conteúdo.

O componente é responsável pela formatação do retorno, pelo estado interno de
recolhimento, pela altura expandida ou recolhida e pelas dimensões do corpo.
`height`, `width`, `body_height` e `body_width` são opcionais. Por padrão, o card
e o corpo usam toda a largura disponibilizada pelo componente pai.

### Diálogo

Utilizado quando uma ação exige:

- confirmação;
- escolha;
- aviso;
- conteúdo complementar.

### Tabela

Oferece estrutura reutilizável para listas com colunas.

### Controles de formulário

Centralizam estilos de dropdowns, campos de texto, botões primários e mensagens de tooltip usados por formulários. Somente campos de entrada desabilitados usam fundo `GREY_100`, texto `TEXT_PRIMARY` e borda `TEXT_PRIMARY`. Campos habilitados preservam o fundo padrão, a borda `BORDER` e a borda de foco roxa. O valor, o rótulo e o placeholder dos campos usam tamanho 14; o texto auxiliar preserva o tamanho padrão do Flet.
Campos de entrada devem preencher toda a largura disponível na célula da grid, independentemente do tamanho do texto exibido.
Quando um campo possuir texto de ajuda, o mesmo conteúdo deve ficar disponível como tooltip.
`build_floating_save_bar` mantém a barra de salvamento montada e anima sua
entrada de baixo para cima, com saída no sentido inverso e transição de
opacidade. O fundo do painel é branco com leve transparência para preservar a
leitura do conteúdo abaixo.

### Tooltip

`build_tooltip_container`, definido em
`ui/shared/components/tooltip_container.py`, recebe somente o texto da dica e
aplica a largura e o espaçamento comuns. A cor fica sob responsabilidade do
tema nativo do Flet, mantendo o cinza translúcido usado pelos tooltips padrão
dos campos.

### Controles da janela

Como a janela usa moldura personalizada, ações de minimizar, maximizar e fechar precisam manter comportamento consistente.
A área externa da aplicação possui regiões transparentes nas quatro bordas e nos
quatro cantos. Essas regiões iniciam o redimensionamento nativo da janela e
preservam o tamanho mínimo de 1000 × 650 pixels configurado pelo Flet. O header
continua responsável por mover, maximizar e restaurar a janela, enquanto a
borda interna da sidebar redimensiona somente o menu lateral.

## Estados visuais

Toda funcionalidade deve considerar:

- carregando;
- sucesso;
- erro;
- lista vazia;
- indisponível;
- desativado;
- foco;
- hover;
- execução em andamento.
- módulo inválido e backend online ou com erro.

A ausência de feedback não deve ser usada como indicação de sucesso.

## Voz na interface

Quando a voz está habilitada:

1. “IRIS” ativa o input;
2. o campo recebe foco;
3. borda e sombra roxas indicam escuta;
4. o texto parcial aparece;
5. o dropdown é atualizado;
6. a dica “‘Enviar’ para concluir” aparece sobre o botão;
7. a palavra “enviar” dispara a validação, enquanto o silêncio estabiliza o texto;
8. o visual retorna ao normal.

Esse brilho deve acontecer apenas na ativação por voz.

## Documentação na interface

A aba de documentação atual:

- lê os arquivos Markdown da pasta `documentation/`;
- renderiza o conteúdo Markdown na interface;
- lista os documentos disponíveis em uma navegação lateral;
- abre `introduction.md` como documento inicial;
- mantém links relativos entre documentos Markdown;
- evita cópias de texto em código;
- permite atualização dos textos sem editar controles visuais;
- oferece busca em modal por documentos, títulos e trechos.

A navegação por âncoras internas de títulos ainda pode ser refinada em versões futuras.

## Configurações

A tela será dividida em:

- configurações gerais;
- configuração de voz;
- senhas.

A seção de voz possui o primeiro formulário completo. Configurações gerais e senhas permanecem como placeholders explícitos.

O formulário de voz permite escolher modo básico ou tempo real, modelos, idioma, um microfone disponível, CPU ou CUDA, precisão, captura, VAD e opções de reconhecimento. O campo de microfone ocupa a segunda linha da primeira seção e mantém, na mesma linha, uma coluna separada para as ações “Recarregar” e “Deletar microfone”. A primeira consulta novamente os dispositivos; a segunda remove o índice persistido e deixa a seleção sem microfone ativo. O card de estado identifica o microfone selecionado; se não houver seleção, usa o microfone salvo; se também não houver salvo, informa que nenhum microfone está conectado. Abaixo, apresenta o estado do serviço de voz. Cada campo possui um ícone de informação sem ação de clique; a explicação aparece como tooltip no hover. O modo básico oculta os parâmetros exclusivos do RealtimeSTT. O prompt fixo de “IRIS” e o contexto dinâmico dos nomes de chamada dos módulos não são exibidos.

Abaixo do estado do serviço existe um visualizador do nível do microfone efetivo: primeiro o selecionado, depois o salvo e, se ambos estiverem ausentes, nenhum. Quando o backend está pronto, o botão “Testar microfone” abre a rota `/settings/voice_checking` como um modal centralizado. Essa tela exibe transcrições brutas sem exigir a palavra de ativação e permite comparar RealtimeSTT e Faster-Whisper no modo completo.

Salvamentos devem usar toaster para indicar sucesso ou erro. O botão “Salvar” da configuração de voz aparece somente quando existem alterações pendentes e permanece flutuante no centro inferior da aba.

## Acessibilidade

A interface deve buscar:

- contraste suficiente;
- foco visível;
- textos objetivos;
- botões com tooltip;
- não depender somente de cor;
- tamanhos legíveis;
- ordem previsível;
- mensagens de erro claras.

## Responsividade

A aplicação é desktop, mas precisa responder a diferentes tamanhos dentro dos limites mínimos da janela.

Evite:

- larguras rígidas sem necessidade;
- conteúdo cortado;
- tabelas sem rolagem;
- overlays presos à tela;
- controles fora da área visível.

## Desempenho

Não execute na thread visual:

- carregamento de modelo;
- transcrição;
- captura contínua;
- chamadas HTTP demoradas;
- leitura extensa;
- processamento pesado.

A interface deve receber eventos já processados e atualizar apenas os controles necessários.

## Consistência textual

Textos visíveis devem:

- estar em português do Brasil;
- usar o mesmo termo para a mesma função;
- evitar mensagens técnicas sem explicação;
- não exibir stack trace;
- orientar a correção quando possível.

## Evolução

Novas telas devem reutilizar:

- cores;
- fontes;
- espaçamentos;
- toaster;
- diálogos;
- tabelas;
- estrutura de rotas;
- padrões de estado.

A identidade deve permanecer leve mesmo quando a plataforma ganhar recursos avançados.
