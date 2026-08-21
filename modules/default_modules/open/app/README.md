# Abrir aplicativo ou item da Área de Trabalho

Este submódulo pesquisa itens da Área de Trabalho e solicita que o usuário escolha qual deseja abrir.

## O que pode ser verificado

- runtime Python legado;
- função `search_arguments` com filtragem por texto;
- sugestões com rótulo, valor e descrição;
- execução com argumento obrigatório;
- validação para impedir caminhos fora da Área de Trabalho;
- mensagens claras para pasta ausente, item inexistente e falha do sistema operacional;
- retorno estruturado com `success` e `opened`;
- registro da execução no histórico.

## Dependências e permissões

Usa apenas recursos do sistema operacional. Abrir um item pode iniciar outro aplicativo e depende das associações configuradas no computador.

## Limitações

A busca mostra no máximo 12 itens e não percorre subpastas. O módulo foi projetado inicialmente para desktop Windows, com alternativas para macOS e Linux.
