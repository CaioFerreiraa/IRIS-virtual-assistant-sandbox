# Documentação da IRIS

## Bem-vindo

A IRIS é uma plataforma desktop open source de assistência virtual e automação modular. Seu objetivo é permitir que usuários executem tarefas digitais por texto ou voz, usando módulos independentes que podem ser desenvolvidos e ampliados pela comunidade.

A plataforma foi concebida para aproximar pessoas e serviços digitais sem limitar o usuário a um único fornecedor. Em vez de concentrar todas as funcionalidades em um sistema fechado, a IRIS organiza suas capacidades em módulos. Cada módulo representa uma tarefa, uma integração ou um conjunto de ações relacionadas.

A primeira versão é desenvolvida em Python, possui interface desktop criada com Flet e utiliza SQLite para armazenamento local. A arquitetura prioriza simplicidade, modularidade, transparência e evolução gradual.

## Para quem é esta documentação

Esta documentação foi escrita para:

- usuários que desejam compreender a plataforma;
- desenvolvedores que pretendem contribuir;
- pessoas interessadas em criar módulos;
- avaliadores e pesquisadores do projeto;
- agentes de inteligência artificial que auxiliam no desenvolvimento;
- futuros mantenedores da IRIS.

Os textos procuram equilibrar explicações conceituais e detalhes técnicos. Quando um recurso ainda não foi implementado, isso é informado explicitamente.

## O que a IRIS faz

A IRIS recebe um comando do usuário, procura um módulo compatível e encaminha a execução para o destino configurado.

Um comando pode representar tarefas como:

- abrir um programa ou arquivo;
- acessar uma página;
- consultar uma agenda;
- enviar uma mensagem;
- interagir com uma API;
- executar uma ação em um sistema local;
- iniciar uma sequência de tarefas por meio de uma rotina.

Nem todas essas possibilidades estão concluídas na versão atual. Elas representam o escopo modular planejado para a plataforma.

## O que a IRIS não é

A IRIS não é uma inteligência artificial generativa. Seu objetivo principal não é criar respostas, imagens ou novos conhecimentos.

Ela funciona como uma assistente virtual operacional: interpreta a intenção expressa pelo usuário, identifica uma ação previamente disponível e executa um fluxo definido.

O reconhecimento de voz é uma forma de entrada. A decisão sobre o que executar depende dos módulos registrados na plataforma.

## Princípios do projeto

### Código aberto

O código da IRIS pode ser estudado, modificado e ampliado. A proposta open source permite que a evolução da plataforma não dependa exclusivamente de um fornecedor.

### Modularidade

Novas capacidades devem ser adicionadas por módulos ou serviços bem delimitados, evitando alterações desnecessárias no núcleo.

### Processamento local

Sempre que possível, dados sensíveis e comandos de voz devem ser processados no próprio computador do usuário.

### Controle do usuário

O usuário decide quais módulos utiliza, quais integrações autoriza e quais credenciais fornece.

### Transparência

Execuções relevantes devem gerar registros que permitam entender qual módulo foi acionado, quando ocorreu e qual foi o resultado.

### Simplicidade

A arquitetura busca separação de responsabilidades sem adotar camadas ou abstrações que não tragam benefício concreto.

## Estado atual

A base atual já possui:

- aplicação desktop em Flet;
- navegação entre telas;
- identidade visual própria;
- módulos e submódulos armazenados no SQLite;
- pesquisa por caminhos de módulos;
- execução de entry points Python;
- abertura de URLs de teste;
- registro de sucesso e erro;
- tela de histórico;
- componentes compartilhados, como toaster, tabela e diálogo;
- estrutura inicial para rotinas;
- estrutura inicial para FastAPI;
- migrations com Alembic.

Ainda estão em desenvolvimento ou planejamento:

- reconhecimento de voz em tempo real;
- palavra de ativação “IRIS”;
- tela completa de configurações;
- scheduler de rotinas;
- cofre de credenciais;
- distribuição de módulos da comunidade;
- versões para outros sistemas operacionais;
- tela interna de documentação.

## Navegação

- [Inspiração e origem](inspiration.md)
- [Arquitetura](architecture.md)
- [Módulos](modules.md)
- [Rotinas](routines.md)
- [Voz](voice.md)
- [Banco de dados](database.md)
- [Interface](ui.md)
- [Cofre e BYOK](vault.md)
- [Comunidade](community.md)
- [Fluxo e roadmap](roadmap.md)
- [Limitações](limitation.md)

## Relação com o artigo acadêmico

A documentação acompanha o projeto prático e utiliza o artigo do TCC como uma de suas bases conceituais. Entretanto, o código evolui durante o desenvolvimento.

Quando o artigo, a documentação e a implementação apresentarem níveis diferentes de maturidade, esta documentação deve separar claramente:

- o que já está implementado;
- o que está parcialmente implementado;
- o que está planejado;
- o que está fora do escopo inicial.
