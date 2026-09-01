# Exemplo HTTP mínimo

Este exemplo demonstra uma única requisição HTTP declarada no `module.json`, sem runtime Python. Ele não é instalado nem executado automaticamente.

Ao executar manualmente, a IRIS envia uma requisição `GET` ao endpoint público de demonstração do httpbin. O texto informado em “Argumento da execução” substitui `{{argument}}` no parâmetro `search`.

Para experimentar, copie esta pasta para `modules/installed` e reinicie a IRIS. A execução exige acesso à internet e depende da disponibilidade do serviço de demonstração.

Authorization com token, senha, API key ou outra credencial não é suportada nesta versão. Scripts de pré-requisição e pós-resposta também não são executados; os dois campos precisam permanecer vazios.
