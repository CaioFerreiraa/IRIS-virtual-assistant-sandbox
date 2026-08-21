# Função run

Submódulo executável que não possui `execute` e fornece somente `run`.

## O que este módulo testa

- fallback do runner para a segunda função reconhecida;
- assinatura com argumento opcional;
- resposta estruturada de sucesso;
- execução e log de um submódulo profundo.

## Resultado esperado

A notificação informa explicitamente que `run` foi chamada. A existência de `main.py` como arquivo não interfere na escolha, pois não existe uma função Python chamada `main` neste entry point.
