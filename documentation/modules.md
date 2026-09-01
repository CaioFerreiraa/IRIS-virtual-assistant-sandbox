# Módulos

## Conceito

Módulos são as capacidades da IRIS. Um módulo pode organizar outros módulos, executar uma ação Python, declarar uma requisição HTTP simples ou manter um backend iniciado junto com a aplicação.

Módulos e submódulos usam a mesma entidade `Module`. A hierarquia persistida usa `parent_module_id`, enquanto referências entre manifestos usam a chave pública estável `module_public_key`.

## Estado atual

A IRIS possui dois grupos de módulos:

- módulos padrão legados, cadastrados pelo seed com chaves públicas explícitas;
- módulos descobertos em `modules/installed`, declarados por manifesto.

Novos desenvolvimentos devem usar o manifesto. O guia completo e o exemplo mínimo estão em [`modules/README.md`](../modules/README.md).

Os módulos padrão legados também possuem README. O seed registra o caminho desses arquivos sem tratá-los como módulos instalados por manifesto, preservando a compatibilidade do fluxo antigo e permitindo que a rota apresente a documentação.

## Catálogo de demonstração atual

O repositório inclui módulos instalados voltados a demonstração e testes manuais:

- `test.showcase`: catálogo raiz executável, configurações e auto start;
- `test.showcase.contracts`: grupo organizacional com filhos dedicados a `execute`, `run` e `main`;
- `test.showcase.arguments`: busca atual por `search_arguments(query)`;
- `test.showcase.arguments_compatibility`: fallbacks `searchArguments()` e argumento posicional;
- `test.showcase.responses`: respostas por `message`, `result`, `opened` e retorno simples;
- `test.showcase.failures`: falha controlada e exceção;
- `weather.forecast`: caminho feliz com geocodificação e previsão do Open-Meteo.
- `notes.javascript`: módulo raiz não executável que controla um backend Node.js
  por meio de auto start;
- `notes.javascript.open`: adaptador Python que verifica o backend e abre sua
  interface HTML;
- `notes.javascript.create`, `notes.javascript.edit` e
  `notes.javascript.delete`: filhos HTTP declarativos para demonstrar CRUD e
  substituição de `{{argument}}`.

Cada pasta possui um README próprio que enumera os comportamentos exercitados, forma de teste, dependências e limitações. Os casos de manifesto inválido permanecem na suíte automatizada para não manter o catálogo intencionalmente indisponível.

## Estrutura de um módulo instalado

```text
modules/
└── installed/
    └── weather/
        ├── module.json
        ├── README.md
        └── main.py
```

O `README.md` utiliza Markdown puro. A tela de configuração do módulo é criada
pela IRIS com controles Flet nativos. Um módulo pode, como comportamento próprio,
servir uma página externa no navegador; essa página não substitui nem injeta
controles na interface Flet.

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

Os quatro campos originais da raiz continuam obrigatórios. `http_request` é opcional e aditivo. `runtime` pode ser `null` para módulos organizacionais ou HTTP. `module.is_executable` é opcional; quando ausente, seu valor é inferido pela presença de runtime Python ou `http_request`.

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
7. sincronizar a requisição HTTP opcional e as definições de variáveis na mesma transação;
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
- método ou URL HTTP inválidos;
- runtime Python e `http_request` declarados simultaneamente;
- Authorization com segredo, cabeçalhos ou parâmetros sensíveis;
- scripts HTTP não vazios.

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

Na tela do próprio módulo, o botão “Executar” abre imediatamente um card de
resultado acima das abas. Durante o processamento, o card informa que a ação
está em andamento; ao concluir, apresenta o status de sucesso ou erro e o corpo
estruturado completo devolvido pelo módulo. Exceções são representadas no mesmo
card com `success: false`, sem expor traceback na interface.

O comportamento legado `GET` ainda abre uma URL no navegador. Ele permanece separado do manifesto versão 1 e ainda não representa uma requisição HTTP completa.

## Execução HTTP opcional

O manifesto versão 1 aceita o campo opcional `http_request` para uma única chamada simples. Métodos aceitos: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD` e `OPTIONS`. A definição pode usar parâmetros, cabeçalhos e body nos modos `none`, `raw_json`, `raw_text` ou `form_urlencoded`.

O placeholder literal `{{argument}}` pode aparecer na URL, nos parâmetros, nos cabeçalhos e no body. `argument_enabled` controla se a string pode ser informada; o último valor utilizado é salvo em `ModuleHttpRequest.argument` e recarregado na tela do módulo. Essa capacidade é independente de `search_arguments()`, que continua sendo um contrato dos módulos Python atuais.

O registry cria ou atualiza `ModuleHttpRequest` pelo `module_id` e preserva o argumento salvo durante ressincronizações. Enquanto `is_customized` for falso, a definição acompanha o `module.json`. Depois que o usuário salva uma personalização, o registry preserva método, URL, argumento habilitado, parâmetros, Authorization, cabeçalhos, body e scripts do banco. A ação “Voltar ao module.json” reaplica a definição atual do manifesto, mantém o último argumento e limpa o estado de personalização.

Um módulo novo copiado para `modules/installed` usa o mesmo fluxo de inicialização e não exige migration ou seed próprio. A restrição única de `module_id` impede mais de uma requisição principal por módulo.

Na interface, método, URL, argumento habilitado, argumento, parâmetros,
Authorization, cabeçalhos, body e scripts podem ser personalizados. Qualquer
alteração exibe a barra flutuante “Salvar requisição”; executar também salva
alterações pendentes e preserva o último argumento usado. Params e Headers são
editados em linhas com estado, chave, valor e descrição, enquanto o body separa
modo e conteúdo.
Authorization aceita apenas `{"type":"none"}` e credenciais continuam
proibidas. Scripts personalizados são armazenados e exibidos como texto, mas
não são executados. O manifesto distribuído continua exigindo scripts vazios.

Respostas HTTP são apresentadas de forma estruturada, com corpo limitado para exibição. O histórico persiste somente um resumo com método, status e duração; não salva corpo, cabeçalhos ou query string completos. Múltiplas requisições e lógica personalizada continuam sendo implementadas com Python.

### Previsão do tempo com Open-Meteo

O módulo atual `weather.forecast` realiza comunicação HTTP dentro do próprio runtime, fora da thread visual. Ele usa:

1. o argumento informado na requisição; ou
2. a variável opcional `default_location`, salva na rota do módulo.

`should_request_argument(variables)` abre o campo de argumento somente quando `default_location` está vazio. Se uma chamada direta chegar sem as duas formas, o módulo orienta o usuário a informar o local. `search_arguments` consulta a geocodificação do Open-Meteo e a execução consulta a previsão por coordenadas. A configuração `forecast_days` aceita de 1 a 7 dias. A integração não usa credenciais, mas depende de internet e da disponibilidade do serviço externo.

### Demonstração Notas com backend JavaScript

`notes.javascript` demonstra um backend comunitário externo sem introduzir um
runtime Node.js nativo na IRIS. O manifesto raiz continua declarando runtime
Python, e seu `main.py` apenas localiza o executável `node`, inicia `server.js`,
aguarda o health check e devolve o `subprocess.Popen` ao gerenciador atual.

O módulo raiz não é executável e concentra o switch “Iniciar com a IRIS”. Os
quatro filhos são executáveis: “Abrir notas” usa Python exclusivamente para
abrir o navegador, enquanto criar, editar e deletar usam `ModuleHttpRequest`.
O backend escuta somente em `127.0.0.1:8765`, usa módulos nativos do Node.js e
mantém os dados apenas em memória. Reiniciar o processo apaga todas as notas.

## Auto start

`supports_auto_start` é capacidade do manifesto. `auto_start_enabled` é preferência persistida do usuário e aparece como “Iniciar com a IRIS”.

Somente módulos raiz válidos, com runtime Python, suporte declarado e preferência habilitada são iniciados. Cada backend inicia isoladamente em uma thread. Uma falha marca somente aquele backend como inválido e não interrompe os demais.

O contrato mínimo exige `start()`. `stop()` é opcional para recursos no processo. Se `start()` devolver um handle compatível com `subprocess.Popen`, a IRIS mantém esse handle e encerra somente o processo criado por ela.

## Segurança atual

Importar um módulo Python executa código no processo da IRIS. O registry evita que exceções comuns derrubem a inicialização, mas não é uma sandbox de segurança. Instalação, assinatura, permissões e distribuição comunitária confiável ainda precisam de um contrato futuro.
