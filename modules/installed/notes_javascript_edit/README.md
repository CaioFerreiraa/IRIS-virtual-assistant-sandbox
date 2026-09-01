# Editar nota

## O que este módulo faz

Envia uma requisição HTTP declarativa para:

```http
PUT http://127.0.0.1:8765/api/notes/{{argument}}
Content-Type: application/json
```

O argumento representa exclusivamente o ID numérico da nota. Nesta primeira
versão existe somente um argumento string, portanto o body é fixo:

```json
{
    "text": "Nota {{argument}} atualizada pela IRIS"
}
```

Para o argumento `3`, a IRIS usa `/api/notes/3` e envia o texto “Nota 3
atualizada pela IRIS”. Não há um segundo campo para informar texto livre.

Uma atualização válida retorna status `200`. ID inválido retorna `400`; nota
inexistente retorna `404`; texto inválido retorna `400`.

O backend do módulo raiz “Notas” precisa estar online. Se houver erro de
conexão, habilite “Iniciar com a IRIS” no módulo raiz e reinicie a aplicação.
