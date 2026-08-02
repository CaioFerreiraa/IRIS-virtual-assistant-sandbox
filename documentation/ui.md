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
- ações da janela.

### Sidebar

A sidebar apresenta módulos e acesso rápido a áreas do sistema.

### Área de conteúdo

A área principal muda conforme a rota.

Rotas atuais ou planejadas:

- início;
- comunidade;
- rotinas;
- histórico;
- configurações;
- documentação.

### Home

A home possui:

- título;
- campo de comando;
- botão de envio;
- botão para limpar;
- lista de módulos;
- lista de argumentos;
- logo de fundo.

### Histórico

Apresenta registros em tabela responsiva.

Campos:

- ID;
- data;
- módulo;
- rotina;
- status;
- mensagem.

## Componentes compartilhados

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

A ausência de feedback não deve ser usada como indicação de sucesso.

## Voz na interface

Quando a voz for implementada:

1. “IRIS” ativa o input;
2. o campo recebe foco;
3. borda e sombra roxas indicam escuta;
4. o texto parcial aparece;
5. o dropdown é atualizado;
6. a dica “‘Enviar’ para concluir” aparece sobre o botão;
7. o fim da fala dispara validação;
8. o visual retorna ao normal.

Esse brilho deve acontecer apenas na ativação por voz.

## Documentação na interface

A futura tab de documentação deverá:

- ler os arquivos Markdown da pasta `documentation/`;
- apresentar navegação por títulos;
- manter links entre documentos;
- evitar cópias de texto em código;
- permitir atualização sem editar controles visuais;
- funcionar também para agentes.

`introduction.md` será o documento inicial.

## Configurações

A tela será dividida em:

- configurações gerais;
- configuração de voz;
- senhas.

A primeira seção com conteúdo completo deverá ser voz.

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
