# Exemplo mínimo

Este módulo demonstra um entry point Python e uma variável de texto criada automaticamente pela IRIS.

## O que este exemplo demonstra

- manifesto versão 1;
- módulo raiz executável;
- função `execute(argument, variables)`;
- argumento opcional;
- variável de texto opcional e editável;
- resposta estruturada com `success` e `message`;
- README exibido na rota do módulo.

## Como usar

Copie a pasta para `modules/installed`, troque `module_public_key` por uma chave única e reinicie a IRIS. O campo `Prefixo` aparecerá na aba `Configurações`.

## Dependências e limitações

Ele não utiliza rede, credenciais ou processos em segundo plano. A pasta fica em `examples` e, por isso, não é instalada automaticamente.
