# Módulos

## Conceito

Módulos são as capacidades da IRIS. Um módulo pode organizar outros módulos, executar uma ação Python ou manter um backend iniciado junto com a aplicação.

Módulos e submódulos usam a mesma entidade `Module`. A hierarquia persistida usa `parent_module_id`, enquanto referências entre manifestos usam a chave pública estável `module_public_key`.

## Estado atual

A IRIS possui dois grupos de módulos:

- módulos padrão legados, cadastrados pelo seed com chaves públicas explícitas;
- módulos descobertos em `modules/installed`, declarados por manifesto.

Novos desenvolvimentos devem usar o manifesto. O guia completo e o exemplo mínimo estão em [`modules/README.md`](../modules/README.md).

## Estrutura de um módulo instalado

```text
modules/
└── installed/
    └── weather/
        ├── module.json
        ├── README.md
        └── main.py
```

O `README.md` utiliza Markdown puro. A interface é criada pela IRIS com controles Flet nativos; módulos não fornecem HTML ou controles visuais.

## Manifesto versão 1

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
        }
    ]
}
```

Os campos da raiz são obrigatórios. `runtime` pode ser `null` para módulos organizacionais. `module.is_executable` é opcional; quando ausente, seu valor é inferido pela presença de runtime.

O campo opcional `module.icon` armazena o nome de uma ligature do Material Icons. A ausência usa `extension`. O nome aceita letras minúsculas, números e underscores. O registry persiste esse valor para a Home, a sidebar e a tela do módulo.

## Chave pública

`module_public_key` é obrigatória, única e imutável depois do registro. A sincronização nunca utiliza nome, `call_name`, caminho ou ID do banco.

Formato aceito:

```text
^[a-z0-9._-]+$
```

Exemplos:

```text
weather
weather.forecast
open.web
```

O `id` numérico continua sendo controlado pelo SQLite e é usado pela interface e pela execução depois que o comando é resolvido.

## Descoberta segura e registry

`ModuleRegistryService` processa cada pasta isoladamente. O fluxo é:

1. localizar `module.json`;
2. ler e validar o JSON;
3. validar README, entry point, tipos e variáveis;
4. importar o entry point;
5. validar chaves duplicadas e hierarquia;
6. sincronizar o módulo pela chave pública;
7. sincronizar definições de variáveis;
8. marcar módulos ausentes ou inválidos como indisponíveis.

Uma pasta quebrada não impede a sincronização das demais nem a abertura da IRIS. Um módulo inválido novo não recebe registro normal. Se já existia, permanece no banco com preferências e valores preservados, mas fica indisponível.

O registry prepara um estado em memória com os diagnósticos. A sidebar consulta esse estado e o banco; ela não examina o sistema de arquivos em cada renderização.

## Validações

A versão atual rejeita:

- manifesto ausente ou JSON inválido;
- schema incompatível;
- campos obrigatórios ausentes ou com tipos incorretos;
- nome de ícone fora do formato aceito;
- chave pública ausente, vazia, inválida ou duplicada;
- pai ausente, autorreferência ou ciclo;
- README ausente ou fora da pasta;
- entry point ausente quando existe runtime;
- módulo executável sem `execute`, `run` ou `main`;
- auto start sem `start()` ou declarado por módulo filho;
- chave de variável duplicada ou inválida;
- tipo de variável diferente de texto;
- variável obrigatória não editável sem valor padrão;
- variáveis secretas, privadas, criptografadas ou com finalidade sensível.

## `module.log`

Falhas de descoberta, manifesto, importação, configuração e inicialização são acrescentadas a `module.log` dentro da pasta do módulo.

O arquivo contém data e hora, etapa, tipo da exceção, mensagem e traceback. O traceback não é mostrado na interface comum. Se o arquivo não puder ser criado, o logger geral recebe a falha como fallback.

Erros normais ocorridos ao executar uma ação continuam no histórico do SQLite e não são gravados em `module.log`.

## Variáveis

A definição vem do manifesto. Valores editados vêm do SQLite. A tela `/modules/{module_id}` cria campos somente quando `user_editable` é `true`.

Regras atuais:

- somente texto é suportado;
- configurações obrigatórias são validadas ao salvar e executar;
- valores não editáveis usam o `default_value` do manifesto;
- sincronização não substitui valores editados pelo usuário;
- definições removidas ficam inativas e não são apagadas automaticamente;
- valores não aparecem em logs;
- senhas, tokens, logins e outros segredos não podem ser armazenados.

## Nome de chamada e pesquisa

`call_name` é definido no manifesto e não é editável. `custom_call_name` é uma preferência opcional do usuário; um novo valor substitui o anterior, sem histórico ou tabela de aliases.

A Home pesquisa nome exibido, `call_name` e `custom_call_name`. Uma seleção resulta em `module_id`. Se o texto corresponder a mais de um módulo, a IRIS solicita uma escolha e não executa silenciosamente o primeiro resultado.

O ícone persistido acompanha o módulo nas sugestões e no campo da Home, na árvore da sidebar e no cabeçalho da rota selecionada.

## Execução Python

O entry point pode fornecer `execute`, `run` ou `main`. A função pode receber argumento e variáveis:

```python
def execute(
    argument: str | None = None,
    variables: dict[str, str] | None = None,
) -> dict:
    return {
        "success": True,
        "message": "Ação concluída.",
    }
```

A execução da Home ocorre em background e devolve o resultado à thread visual do Flet. Toda execução normal gera log no SQLite.

O comportamento legado `GET` ainda abre uma URL no navegador. Ele permanece separado do manifesto versão 1 e ainda não representa uma requisição HTTP completa.

## Auto start

`supports_auto_start` é capacidade do manifesto. `auto_start_enabled` é preferência persistida do usuário e aparece como “Iniciar com a IRIS”.

Somente módulos raiz válidos, com runtime Python, suporte declarado e preferência habilitada são iniciados. Cada backend inicia isoladamente em uma thread. Uma falha marca somente aquele backend como inválido e não interrompe os demais.

O contrato mínimo exige `start()`. `stop()` é opcional para recursos no processo. Se `start()` devolver um handle compatível com `subprocess.Popen`, a IRIS mantém esse handle e encerra somente o processo criado por ela.

## Segurança atual

Importar um módulo Python executa código no processo da IRIS. O registry evita que exceções comuns derrubem a inicialização, mas não é uma sandbox de segurança. Instalação, assinatura, permissões e distribuição comunitária confiável ainda precisam de um contrato futuro.
