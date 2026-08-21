# Argumentos

Submódulo que implementa o contrato atual de busca de argumentos.

## O que este módulo testa

- detecção automática da função `search_arguments`;
- abertura do segundo campo da Home antes da execução;
- busca em background sem bloquear a interface;
- filtragem por rótulo e valor;
- resultados com `label`, `value` e `description`;
- seleção de sugestão;
- digitação manual de um valor;
- preservação de acentos e UTF-8;
- validação de argumento vazio ou desconhecido;
- log de sucesso e log de exceção.

## Como testar

Escolha o módulo e pesquise por `primeira`, `beta` ou `ação`. Os valores válidos enviados ao runtime são `alpha`, `beta` e `ação`. Um texto diferente gera uma mensagem de erro e um registro no histórico.
