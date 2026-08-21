# Argumentos compatíveis

Submódulo dedicado aos fallbacks mantidos para módulos legados.

## O que este módulo testa

- função camelCase `searchArguments` em vez de `search_arguments`;
- função de busca sem parâmetro de consulta;
- resultados de busca como strings simples;
- normalização automática de cada string para rótulo e valor;
- entry point cujo parâmetro se chama `value`, não `argument`;
- envio posicional do argumento pelo runner;
- resposta estruturada e log de sucesso.

## Limitação intencional

Como `searchArguments` não recebe a consulta, a lista permanece igual durante a digitação. Esse comportamento existe somente para verificar a compatibilidade; módulos novos devem preferir `search_arguments(query)` e resultados estruturados.
