# Função execute

Submódulo executável que fornece somente a função `execute`, primeira opção procurada pelo runner.

## O que este módulo testa

- carregamento de um entry point Python por arquivo;
- seleção da função `execute`;
- assinatura que aceita apenas `argument`;
- argumento opcional;
- resposta com `success` e `message`;
- execução de um item no terceiro nível da hierarquia;
- criação de log de sucesso.

## Como testar

Selecione o módulo para executá-lo sem argumento. Por voz ou chamada direta, um texto adicional pode ser enviado e aparecerá na mensagem.
