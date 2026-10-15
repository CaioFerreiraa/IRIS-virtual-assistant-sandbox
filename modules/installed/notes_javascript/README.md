# Notas

## O que este módulo demonstra

Notas é um módulo comunitário didático que mantém notas em memória por meio de
um backend escrito em JavaScript. O processo Node.js fica separado do núcleo da
IRIS e expõe uma API HTTP exclusivamente em `127.0.0.1:8765`.

A arquitetura da demonstração é:

```text
IRIS → adaptador Python de inicialização → processo Node.js
IRIS → ModuleHttpRequest dos filhos → API HTTP local
Navegador → interface HTML → API HTTP local
```

O arquivo `main.py` não implementa regras de notas. Ele apenas localiza o
executável `node`, verifica a porta, inicia `server.js`, aguarda `/health` e
devolve o processo para o `ModuleRuntimeManager`. O runtime reconhecido pela
IRIS continua sendo Python; Node.js é um processo externo pertencente ao
módulo.

## Como iniciar

1. Instale Node.js e confirme que o comando `node` está disponível no `PATH`.
2. Abra o módulo raiz “Notas” na IRIS.
3. Na aba “Configurações”, habilite “Iniciar com a IRIS”.
4. Feche e abra novamente a IRIS.

O switch começa desligado e aparece somente neste módulo raiz. O servidor
escuta apenas em `127.0.0.1`, na porta `8765`. Ao fechar a IRIS, o
`ModuleRuntimeManager` encerra o processo iniciado por ela.

## Como testar os filhos

- “Abrir notas” verifica `/health` e abre `http://127.0.0.1:8765/`.
  Sem sessão no navegador, a página redireciona para `/login`.
- “Login nas notas” envia as chaves `LOGIN_NOTAS` e `SENHA_NOTAS` para
  `POST /api/login` e salva o token retornado em `TOKEN_NOTAS`.
- “Criar nota” envia o texto do argumento para `POST /api/notes`.
- “Editar nota” usa o argumento como ID em `PUT /api/notes/{id}`.
- “Deletar nota” usa o argumento como ID em `DELETE /api/notes/{id}`.

Antes de usar criar, editar ou deletar pela IRIS, configure as três Vault Keys
conforme o [README de Login nas notas](../notes_javascript_login/README.md) e
execute “Login nas notas”. “Abrir notas” não precisa de Vault Keys, mas o
navegador exige login próprio para acessar a página.

Se o serviço estiver desligado, habilite “Iniciar com a IRIS” neste módulo e
reinicie a aplicação. Falhas de inicialização aparecem na aba “Erro” e no
`module.log` do módulo raiz.

## Limitações

- As notas existem somente em memória e são apagadas sempre que o backend é
  reiniciado.
- O login de demonstração aceita somente usuário `admin` e senha `admin`.
  `/login` e `/health` são públicos; a página principal exige cookie de
  sessão e as rotas `/api/notes` exigem esse cookie ou `X-IRIS-Vault` válido.
  O cookie é HttpOnly e SameSite=Strict. O servidor local não usa HTTPS nem
  persiste usuários ou sessões; essa credencial fixa não é proteção de produção.
- O texto possui limite de 500 caracteres.
- A porta configurável por `IRIS_NOTES_PORT` existe exclusivamente para testes;
  o uso normal permanece em `8765`.
- A edição pela ação da IRIS aceita somente o ID e produz um texto fixo. A
  interface HTML permite informar o novo texto completo.

## Demonstração de Vault Keys

Não há cadastro automático nem seed. O Vault normaliza nomes digitados em
minúsculas para maiúsculas. “Login nas notas” declara `LOGIN_NOTAS`,
`SENHA_NOTAS` e `TOKEN_NOTAS`. Os outros três filhos HTTP declaram somente
`TOKEN_NOTAS` e enviam `X-IRIS-Vault: {{vk.TOKEN_NOTAS}}`. A IRIS grava o
token retornado apenas quando `TOKEN_NOTAS` existe e permite alteração pela
IRIS. O token é renovado a cada login e deixa de funcionar após reiniciar o
backend, até executar novo login.

O valor fica criptografado no SQLite com Fernet. A chave fica no arquivo local
`.iris_vault.key`: perdê-lo impede a leitura dos valores existentes. A proteção
é básica para o MVP e não é segurança de produção. Windows Credential Manager
ficará para uma versão futura.
