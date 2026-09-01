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
- “Criar nota” envia o texto do argumento para `POST /api/notes`.
- “Editar nota” usa o argumento como ID em `PUT /api/notes/{id}`.
- “Deletar nota” usa o argumento como ID em `DELETE /api/notes/{id}`.

Se o serviço estiver desligado, habilite “Iniciar com a IRIS” neste módulo e
reinicie a aplicação. Falhas de inicialização aparecem na aba “Erro” e no
`module.log` do módulo raiz.

## Limitações

- As notas existem somente em memória e são apagadas sempre que o backend é
  reiniciado.
- Não há autenticação, HTTPS, usuários, cookies ou persistência permanente.
- O texto possui limite de 500 caracteres.
- A porta configurável por `IRIS_NOTES_PORT` existe exclusivamente para testes;
  o uso normal permanece em `8765`.
- A edição pela ação da IRIS aceita somente o ID e produz um texto fixo. A
  interface HTML permite informar o novo texto completo.
