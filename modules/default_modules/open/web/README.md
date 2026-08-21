# Abrir Web

Submódulo organizacional para páginas locais de demonstração.

## O que pode ser verificado

- um módulo pai não executável;
- submódulos que usam o método legado `GET`;
- abertura de URL no navegador padrão;
- hierarquia `Abrir / Web / Cor`.

## Dependência

As páginas verde e vermelha exigem que o servidor FastAPI de demonstração esteja disponível em `127.0.0.1:4101`.

## Limitação importante

No fluxo legado da IRIS, `GET` abre a URL no navegador. Ele não realiza uma requisição HTTP e não valida o conteúdo da resposta.
