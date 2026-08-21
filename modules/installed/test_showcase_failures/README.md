# Falhas

Submódulo que permite comparar os dois caminhos de erro de uma execução normal.

## O que este módulo testa

- falha controlada por retorno com `success: false`;
- notificação de erro usando a mensagem retornada;
- status `error` no histórico para uma falha controlada;
- exceção `RuntimeError` propagada pelo entry point;
- captura da exceção na fronteira da Home;
- log de erro criado mesmo quando a função lança;
- continuidade da aplicação depois da falha;
- nova execução após um erro;
- separação entre a aba `Log` e erros estruturais de manifesto.

## Como testar

Escolha `Falha controlada` e depois `Exceção`. Nos dois casos a janela deve continuar funcional e a aba `Log` deve receber uma entrada de erro. A execução normal não grava `module.log` e não torna o módulo indisponível.
