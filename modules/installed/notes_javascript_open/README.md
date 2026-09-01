# Abrir notas

## O que este módulo faz

Verifica `GET http://127.0.0.1:8765/health` e, quando o serviço está online,
abre `http://127.0.0.1:8765/` no navegador padrão.

O submódulo usa um entry point Python pequeno porque sua ação principal é abrir
o navegador. Ele não inicia nem implementa o backend JavaScript e não possui
auto start próprio.

## Argumento e resposta

Esta ação não recebe argumento nem envia body. Em caso de sucesso, retorna uma
mensagem estruturada e o endereço aberto.

Se o backend estiver offline, a ação orienta a habilitar “Iniciar com a IRIS”
no módulo raiz “Notas” e reiniciar a aplicação. Uma falha do navegador também é
retornada como erro normal da execução, sem tornar o módulo estruturalmente
inválido.
