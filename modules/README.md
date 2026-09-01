# Desenvolvimento de módulos da IRIS

## Estrutura obrigatória

Cada módulo instalado ocupa uma pasta própria dentro de `modules/installed`:

```text
modules/
└── installed/
    └── weather/
        ├── module.json
        ├── README.md
        └── main.py
```

`module.json` declara o módulo. `README.md` explica seu uso em Markdown puro. `main.py` é necessário quando o módulo declara runtime Python. A interface de configuração é construída pela IRIS com controles Flet. Um módulo pode servir uma página externa como parte de sua própria ação, mas não fornece nem injeta controles na tela Flet da IRIS.

## Exemplo completo de `module.json`

```json
{
    "schema_version": 1,
    "module": {
        "module_public_key": "weather",
        "name": "Clima",
        "call_name": "clima",
        "icon": "partly_cloudy_day",
        "parent_public_key": null,
        "description": "Consulta informações de clima.",
        "readme": "README.md",
        "is_executable": true
    },
    "runtime": {
        "type": "python",
        "entrypoint": "main.py",
        "supports_auto_start": false
    },
    "variables": [
        {
            "key": "default_city",
            "label": "Cidade padrão",
            "description": "Cidade utilizada quando nenhuma cidade for informada.",
            "type": "text",
            "required": true,
            "user_editable": true,
            "default_value": ""
        },
        {
            "key": "api_version",
            "label": "Versão da API",
            "description": "Valor técnico definido pelo módulo.",
            "type": "text",
            "required": true,
            "user_editable": false,
            "default_value": "v1"
        }
    ]
}
```

Os quatro campos originais da raiz são obrigatórios. O campo `http_request` é opcional. `runtime` pode ser `null` para módulos organizacionais ou HTTP. `module.is_executable` é opcional: quando ausente, vale `true` se existir runtime Python ou `http_request`, e `false` caso contrário.

`module.icon` recebe o nome de uma ligature do Material Icons, em letras minúsculas, números e underscores, por exemplo `partly_cloudy_day`. Quando o campo não é informado, a IRIS usa `extension` para manter compatibilidade com manifestos anteriores. A fonte Material Symbols Rounded é distribuída localmente em `assets/fonts` e a interface não depende dos ícones internos do Flet para representar módulos.

## Chave pública

`module_public_key` é o identificador estável do módulo. Ela é obrigatória, única e não deve mudar depois da primeira sincronização.

São aceitas somente letras minúsculas, números, pontos, hífens e underscores, sem espaços. Exemplos válidos:

```text
weather
weather.forecast
open.web
```

O ID numérico continua pertencendo ao SQLite. Não use nome, `call_name`, caminho ou ID para identificar uma atualização do manifesto.

## Hierarquia

Use `parent_public_key` para declarar o pai:

```json
"parent_public_key": "weather"
```

Um módulo raiz usa `null`. A referência precisa apontar para uma chave pública registrada ou para outro manifesto válido. Autorreferências, pais ausentes e ciclos invalidam o módulo. Módulos filhos não podem declarar auto start próprio.

## Variáveis editáveis

A versão 1 aceita somente `type: "text"`. Quando `user_editable` é `true`, a IRIS cria automaticamente um campo Flet. Quando é `false`, não existe campo editável e o runtime recebe sempre o `default_value` do manifesto.

As funções `execute`, `run` ou `main` podem receber as configurações sem depender da interface:

```python
def execute(
    argument: str | None = None,
    variables: dict[str, str] | None = None,
) -> dict:
    city = (argument or (variables or {}).get("default_city", "")).strip()
    return {"success": True, "message": f"Cidade: {city}"}
```

Chaves são únicas dentro do módulo e usam o mesmo conjunto simples de caracteres da chave pública. Campos obrigatórios são validados antes de salvar e antes de executar. Definições removidas do manifesto ficam inativas no banco; valores existentes não são apagados automaticamente.

## Argumentos e solicitação condicional

Um módulo pode fornecer `search_arguments(query)` ou o fallback legado `searchArguments(query)`. A presença dessa função faz a IRIS oferecer busca e sugestões de argumentos.

Por padrão, todo módulo que oferece busca solicita um argumento antes de executar. Quando uma configuração pode substituir o argumento, o runtime pode decidir de forma explícita:

```python
def should_request_argument(
    variables: dict[str, str] | None = None,
) -> bool:
    return not bool((variables or {}).get("default_city", "").strip())
```

O fallback camelCase `shouldRequestArgument` também é reconhecido. Sem uma função de busca, o resultado dessa decisão é ignorado. O callback deve ser rápido, não realizar rede e depender somente das configurações recebidas.

## README

O README deve usar Markdown em UTF-8, sem HTML incorporado. O caminho é relativo à pasta do módulo e não pode escapar dela. Explique finalidade, argumentos, variáveis, dependências, permissões e limitações. Links não são abertos automaticamente pela tela do módulo.

## Runtime e auto start

O runtime suportado nesta versão é:

```json
{
    "type": "python",
    "entrypoint": "main.py",
    "supports_auto_start": true
}
```

Um módulo executável fornece `execute()`, `run()` ou `main()`. Um backend com `supports_auto_start: true` também fornece `start()`. A preferência “Iniciar com a IRIS” é salva pelo usuário e só vale na próxima inicialização.

`start()` deve retornar rapidamente. Se criar um `subprocess.Popen`, pode devolver esse handle para que a IRIS encerre somente o processo que ela iniciou. Para recursos no próprio processo, o módulo pode fornecer `stop()`.

O catálogo `notes.javascript` demonstra como um `start()` Python mínimo pode
iniciar um backend Node.js separado. O runtime do manifesto permanece Python;
não existe `runtime.type: "node"`. Os filhos HTTP continuam cadastrados pelo
registry comum, sem migration ou seed específico.

## Requisição HTTP opcional

Uma requisição simples pode ser declarada sem `main.py`:

```json
"runtime": null,
"http_request": {
    "method": "GET",
    "url": "https://api.example.com/items",
    "argument_enabled": true,
    "params": [
        {
            "key": "search",
            "value": "{{argument}}",
            "description": "Texto pesquisado.",
            "enabled": true
        }
    ],
    "authorization": {"type": "none"},
    "headers": [],
    "body": {"mode": "none", "content": ""},
    "scripts": {"pre_request": "", "post_response": ""}
}
```

Os métodos aceitos são `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD` e `OPTIONS`. A URL precisa começar com `http://` ou `https://`. Params e Headers recebem itens com `key`, `value`, `description` e `enabled`. O body aceita `none`, `raw_json`, `raw_text` e `form_urlencoded`.

O placeholder literal `{{argument}}` é substituído na URL, nos parâmetros, nos cabeçalhos e no body. O argumento HTTP é somente uma string; seu último valor é persistido ao salvar a aba ou executar a requisição e recarregado na aba “Execução”. Essa aceitação não depende de `search_arguments()`, que permanece disponível para módulos Python.

O `module.json` fornece a definição inicial distribuível. Na aba “Execução”, o usuário pode personalizar método, URL, argumento habilitado, argumento, parâmetros, Authorization, cabeçalhos, body e scripts. Depois do primeiro salvamento, o registry preserva a definição local; “Voltar ao module.json” reaplica o manifesto atual sem apagar o último argumento. Authorization aceita apenas `{"type":"none"}` e não pode conter credenciais. Scripts no manifesto precisam permanecer vazios; textos de script personalizados podem ser salvos e exibidos localmente, mas nunca são executados.

Não combine runtime Python e `http_request` no mesmo módulo. Use Python para múltiplas requisições, regras complexas ou qualquer lógica personalizada. O `GET` legado persistido em `Module.request_method` continua abrindo uma URL no navegador e não é uma requisição HTTP declarativa.

## `module.log`

Cada pasta é descoberta isoladamente. A IRIS acrescenta informações a `module.log` quando ocorre falha de:

- descoberta ou leitura do manifesto;
- validação do manifesto e da hierarquia;
- importação do entry point;
- configuração do contrato;
- inicialização por auto start.

O arquivo inclui data e hora, etapa, tipo da exceção, mensagem e traceback. Erros normais de execução e requisições não são escritos nele; eles seguem o histórico normal da IRIS. Se o arquivo local não puder ser criado, a aplicação usa seu logger geral e continua inicializando.

## Dados proibidos nesta versão

Não declare nem armazene senhas, tokens, logins, chaves de API, credenciais, dados privados, variáveis secretas ou valores criptografados. O Vault ainda não existe e texto no SQLite não é uma solução segura. Manifestações explícitas de variável secreta, privada ou criptografada são rejeitadas.

## Como testar antes de distribuir

1. copie `modules/examples/minimal` para uma pasta temporária;
2. ajuste a chave pública para um valor único;
3. valide o JSON e confirme que README e entry point existem;
4. execute `python -m unittest tests.test_module_manifest`;
5. execute `python -m unittest tests.test_module_registry`;
6. use um diretório e um SQLite temporários para testes próprios;
7. teste o fluxo válido, valores obrigatórios, importação quebrada e auto start;
8. execute a suíte completa com `python -m unittest discover -s tests -p "test_*.py"`.

O exemplo Python mínimo está em [`examples/minimal`](examples/minimal) e o exemplo HTTP em [`examples/http_minimal`](examples/http_minimal). Eles não são descobertos nem instalados automaticamente.
