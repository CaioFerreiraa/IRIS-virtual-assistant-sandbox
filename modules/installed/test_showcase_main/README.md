# Função main

Submódulo executável que fornece apenas a função `main`, último fallback reconhecido.

## O que este módulo testa

- fallback do runner depois da ausência de `execute` e `run`;
- assinatura com argumento opcional;
- resposta estruturada com mensagem;
- execução e registro de sucesso.

## Resultado esperado

A notificação confirma que a função `main` foi chamada. O nome do arquivo e o nome da função podem coincidir sem exigir importação por caminho de pacote.
