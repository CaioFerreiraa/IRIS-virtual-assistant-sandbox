# Comunidade

## Uma plataforma construída para crescer

A proposta open source da IRIS permite que sua evolução seja compartilhada entre usuários, desenvolvedores e pessoas interessadas em automação.

O núcleo da plataforma oferece a estrutura de execução. A comunidade pode ampliar as capacidades por meio de módulos, correções, documentação, testes e propostas de melhoria.

A colaboração não deve exigir que todo participante compreenda o projeto inteiro. Um módulo bem delimitado pode ser desenvolvido de forma independente, desde que respeite o contrato da IRIS.

## O que a comunidade poderá fazer

### Criar módulos

Desenvolvedores poderão criar módulos para integrar a IRIS com:

- serviços de agenda;
- plataformas de comunicação;
- repositórios de código;
- ferramentas de tarefas;
- sistemas empresariais;
- programas locais;
- arquivos e recursos do sistema operacional;
- APIs públicas;
- APIs privadas autorizadas pelo usuário.

Um módulo deve executar uma responsabilidade clara e devolver uma resposta compreensível.

### Melhorar módulos existentes

Contribuidores poderão:

- corrigir erros;
- melhorar compatibilidade;
- ampliar pesquisas de argumentos;
- adicionar tratamento de falhas;
- melhorar mensagens;
- atualizar integrações;
- acrescentar testes.

### Melhorar a plataforma

Também serão aceitas contribuições relacionadas a:

- interface;
- acessibilidade;
- documentação;
- banco de dados;
- voz;
- segurança;
- rotinas;
- desempenho;
- distribuição;
- compatibilidade com outros ambientes.

### Validar a experiência

Usuários sem experiência em programação também poderão colaborar por meio de:

- relatos de erro;
- sugestões;
- testes de usabilidade;
- documentação de casos reais;
- feedback sobre comandos de voz;
- revisão de traduções e clareza.

## Princípios para módulos comunitários

Um módulo comunitário deverá:

- possuir finalidade documentada;
- informar quais permissões utiliza;
- declarar dependências;
- evitar coleta desnecessária de dados;
- não incluir credenciais;
- não executar ações ocultas;
- devolver resultados estruturados;
- tratar erros;
- registrar versão e autoria;
- respeitar o controle do usuário.

A distribuição de código executável exige cuidados. A IRIS não deverá instalar ou executar módulos desconhecidos sem apresentar origem, permissões e riscos.

## Revisão e confiança

No futuro, a plataforma poderá adotar mecanismos como:

- repositórios oficiais;
- revisão de código;
- assinatura ou checksum;
- manifesto de permissões;
- classificação de confiança;
- versões compatíveis;
- relatório de dependências;
- validação automatizada.

Esses mecanismos ainda não foram definidos.

## Como criar um módulo

O contrato local inicial está definido em [`modules/README.md`](../modules/README.md). Cada módulo utiliza uma pasta em `modules/installed` com `module.json`, `README.md` e, quando houver runtime Python, `main.py`.

A chave pública identifica atualizações, relações de pai usam outra chave pública e a IRIS gera a interface a partir das variáveis do manifesto. A versão atual aceita somente texto não sensível e não oferece Vault.

O exemplo em `modules/examples/minimal` pode ser copiado para testes. A existência desse contrato local não significa que distribuição, assinatura, permissões ou instalação remota já estejam concluídas.

## Como baixar e instalar um módulo

<!-- Conteúdo futuro: o fluxo de distribuição, verificação e instalação ainda não foi definido. -->

## Contribuições de documentação

Os arquivos da pasta `documentation/` fazem parte do produto.

Ao alterar um comportamento, o contribuidor deve atualizar o documento correspondente. A documentação precisa informar claramente quando uma função está pronta, parcial ou planejada.

## Convivência

A comunidade deve priorizar:

- respeito;
- comunicação objetiva;
- explicação das decisões;
- inclusão de novos participantes;
- revisão construtiva;
- privacidade;
- segurança do usuário;
- compatibilidade com a proposta do projeto.

A IRIS pretende ser extensível sem deixar de ser compreensível.
