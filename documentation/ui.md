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

O indicador de voz abre um diálogo ao ser clicado, independentemente do estado atual. O diálogo lista os estados possíveis do microfone com seus ícones e cores, destacando o estado ativo. Seu tooltip também descreve se o backend está carregando, com erro, pronto no modo básico, pronto no modo completo, desativado, indisponível ou pausado fora das rotas autorizadas. Durante uma ativação por “IRIS”, o indicador recebe uma sombra luminosa na cor do estado atual.

### Sidebar

A sidebar apresenta os módulos em uma árvore recolhível: cada submódulo
fica dentro do menu de seu pai, sem alterar a rota numérica usada na navegação.
O item ativo mantém seus ancestrais expandidos, exceto quando o usuário
recolhe explicitamente um deles. Clicar em qualquer item que possui filhos
sempre alterna a exibição dos submódulos e mantém a navegação para a tela do
módulo pai.

Os itens listados usam cantos retos, tamanho fixo, ficam encostados uns aos
outros e a `ListView` alcança as laterais internas do painel. O padding fica no
cabeçalho da seção e nos próprios itens, sem criar uma segunda margem ao redor
da lista. Nomes longos usam a quebra de linha nativa do Flet dentro do limite do
item. Quando existe, `custom_call_name` aparece entre parênteses como texto
secundário logo após o nome do módulo.

Cada item possui uma bolinha de status. Módulos executáveis usam bolinha verde,
itens organizacionais usam bolinha roxa e módulos com problema aparecem com
bolinha vermelha na área de diagnóstico.

Módulos raiz usam sempre `SURFACE`. Submódulos são deslocados para a direita e
escurecem conforme a profundidade: `GREY_100` (`#F5F6FA`), `GREY_200`
(`#E4E7F2`), `GREY_300` (`#D3D8EA`), `GREY_400` (`#C2C8E1`) e `GREY_500`
(`#B0B9D9`). Profundidades adicionais permanecem em `GREY_500` para preservar
contraste e legibilidade.

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

A pesquisa considera nome exibido, `call_name` e `custom_call_name`. A seleção visual mantém o `module_id`; comandos ambíguos não são executados automaticamente. A execução acontece em background para manter a interface responsiva.

### Tela do módulo

A rota `/modules/{module_id}` monta a tela consultando o banco e o estado preparado pelo registry. Ela contém:

- breadcrumb calculado pela hierarquia;
- nome e status;
- switch “Iniciar com a IRIS” quando o runtime raiz suporta auto start;
- README em Markdown, com caminho validado e HTML rejeitado;
- `call_name` somente leitura;
- um único `custom_call_name` editável;
- campos Flet automáticos somente para variáveis de texto editáveis;
- validação e toaster de sucesso ou erro.

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

### Diálogo

Utilizado quando uma ação exige:

- confirmação;
- escolha;
- aviso;
- conteúdo complementar.

### Tabela

Oferece estrutura reutilizável para listas com colunas.

### Controles de formulário

Centralizam estilos de dropdowns, campos de texto, botões primários e mensagens de tooltip usados por formulários.
Campos de entrada devem preencher toda a largura disponível na célula da grid, independentemente do tamanho do texto exibido.
Quando um campo possuir texto de ajuda, o mesmo conteúdo deve ficar disponível como tooltip.

### Controles da janela

Como a janela usa moldura personalizada, ações de minimizar, maximizar e fechar precisam manter comportamento consistente.

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

Salvamentos devem usar toaster para indicar sucesso ou erro.

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
