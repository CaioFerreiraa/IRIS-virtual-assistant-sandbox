# Tipos de resposta

Submódulo para comparar as formas de retorno interpretadas pela Home e pelo histórico.

## O que este módulo testa

- dicionário com `success: true` e `message`;
- dicionário com `success: true` e `result`;
- dicionário com `success: true` e `opened`;
- retorno Python simples do tipo string;
- normalização do retorno simples para `{"success": true, "result": ...}`;
- prioridade visual de `message`, depois `result`, depois `opened`;
- mensagem padrão `URL aberta` para a chave `opened`;
- conteúdo salvo no histórico em cada formato;
- busca de argumentos para escolher o cenário.

## Como testar

Selecione uma das quatro opções exibidas no campo de argumentos. O cenário `opened` apenas demonstra o contrato de resposta; ele não abre um recurso real.
