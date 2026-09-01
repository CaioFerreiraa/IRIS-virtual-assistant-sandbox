# Deletar nota

## O que este módulo faz

Envia uma requisição HTTP declarativa sem body para:

```http
DELETE http://127.0.0.1:8765/api/notes/{{argument}}
```

O argumento representa exclusivamente o ID numérico da nota. Em caso de
sucesso, o backend retorna status `200`, mensagem de exclusão e os dados da nota
removida. ID inválido retorna `400` e nota inexistente retorna `404`.

O backend do módulo raiz “Notas” precisa estar online. Se houver erro de
conexão, habilite “Iniciar com a IRIS” no módulo raiz e reinicie a aplicação.
