# Testes de módulos

Catálogo de demonstração dos contratos atualmente suportados pela IRIS. Este módulo raiz também é executável e organiza os submódulos de teste.

## O que este módulo testa

- manifesto versão 1 e sincronização por `module_public_key`;
- módulo raiz que também possui submódulos;
- ícone do Material Icons;
- execução pela função `execute`;
- argumento opcional recebido por voz ou por chamada direta;
- resposta estruturada com `success` e `message`;
- variável de texto opcional e editável;
- variável de texto obrigatória e editável;
- variável obrigatória e não editável, definida pelo manifesto;
- alteração das configurações na rota do próprio módulo;
- validação de campo obrigatório antes da execução;
- persistência das preferências no SQLite;
- suporte a auto start por `start()` e encerramento por `stop()`;
- registro de sucesso no histórico.

## Como testar

1. Abra esta rota e altere os campos da aba `Configurações`.
2. Salve e execute `Testes de módulos` pela Home.
3. Confirme se a mensagem apresenta os três valores.
4. Apague o campo obrigatório e tente salvar para observar a validação.
5. Ative `Iniciar com a IRIS`, reinicie o aplicativo e confira o estado do runtime.

## Submódulos

- `Contratos de entrada`: grupo para os nomes de entry point;
- `Argumentos`: busca atual com `search_arguments`;
- `Argumentos compatíveis`: compatibilidade com `searchArguments`;
- `Tipos de resposta`: `message`, `result`, `opened` e retorno simples;
- `Falhas`: falha controlada e exceção.

## Limitações

O auto start deste catálogo somente altera um estado em memória e retorna imediatamente. Ele não cria processo, porta, arquivo ou conexão de rede. Casos de manifesto inválido continuam cobertos pelos testes automatizados, pois manter um módulo propositalmente corrompido no catálogo deixaria a instalação sempre indisponível.
