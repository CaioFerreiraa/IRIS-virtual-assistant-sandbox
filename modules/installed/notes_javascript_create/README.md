# Criar nota

## O que este módulo faz

Envia uma requisição HTTP declarativa para:

```http
POST http://127.0.0.1:8765/api/notes
Content-Type: application/json
```

O argumento representa o texto completo da nota e substitui `{{argument}}` no
body configurado pelo manifesto:

```json
{
    "text": "{{argument}}"
}
```

Em caso de sucesso, o backend responde com status `201`, mensagem de criação e
a nota contendo ID numérico e texto. Texto ausente, vazio, inválido ou acima de
500 caracteres retorna status `400`.

O backend do módulo raiz “Notas” precisa estar online. Se houver erro de
conexão, habilite “Iniciar com a IRIS” no módulo raiz e reinicie a aplicação.
Antes de executar pela IRIS, configure as Vault Keys e execute “Login nas
notas”. Esta ação envia `TOKEN_NOTAS` no header `X-IRIS-Vault`; sem a chave
configurada, a requisição não é enviada.
