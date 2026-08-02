# Módulos

## Conceito

Módulos são as capacidades da IRIS.

Cada módulo representa:

- uma categoria;
- uma tarefa;
- uma integração;
- uma ação local;
- um caminho até uma ação executável.

Exemplos conceituais:

```text
Abrir
└── App
    └── Spotify

Agenda
├── Consultar
└── Criar evento
```

Nem todo item precisa executar uma ação. Alguns módulos existem apenas para organizar submódulos.

## Módulos e submódulos

Módulos e submódulos usam a mesma entidade `Module`.

A hierarquia é formada por:

```text
parent_module_id
```

Quando o campo é vazio, o módulo está na raiz. Quando contém outro identificador, o módulo é filho daquele registro.

Essa abordagem permite vários níveis de profundidade.

## Campos técnicos

### `name`

Nome apresentado ao usuário.

### `call_name`

Nome padrão usado para localizar o módulo por texto ou voz.

### `custom_call_name`

Nome personalizado definido futuramente pelo usuário.

Quando existir, poderá funcionar como alias.

### `description`

Explica a finalidade do módulo.

### `request_method`

Define o tipo de execução.

A implementação atual reconhece principalmente:

- `PYTHON`;
- `GET`.

O nome `GET` atualmente abre uma URL no navegador. A separação entre abertura de URL e requisição HTTP real ainda precisa ser corrigida.

### `request_url`

Contém o destino da execução.

Para Python, pode ser um caminho de importação:

```text
modules.default_modules.open.app.main
```

Para URL, pode ser:

```text
http://127.0.0.1:4101/web/verde
```

### `is_executable`

Indica se o módulo pode executar uma ação.

Um módulo organizacional deve permanecer como não executável.

### `parent_module_id`

Relaciona o módulo ao pai.

## Caminho de módulo

O caminho representa a posição completa.

Exemplo:

```text
Abrir > App > Spotify
```

O caminho ajuda:

- pesquisa;
- exibição;
- diferenciação de nomes iguais;
- seleção progressiva;
- execução;
- logs.

## Pesquisa por comando

A tela principal recebe texto e atualiza a lista de sugestões.

No fluxo futuro de voz, a mesma pesquisa deverá acontecer a cada atualização parcial.

Exemplo:

```text
abrir
```

Pode retornar todos os caminhos contendo “abrir”.

```text
abrir app
```

Deve priorizar caminhos que contenham os dois termos.

```text
abrir app spotify
```

Deve priorizar o caminho completo correspondente.

A pesquisa precisa ser determinística. O mesmo comando deve produzir a mesma ordenação quando o conjunto de módulos não mudou.

## Seleção automática

No fluxo planejado:

- o primeiro item da lista será pré-selecionado;
- quando a fala terminar, o primeiro resultado poderá ser executado;
- a palavra “enviar” também poderá concluir;
- um único resultado não deve ser executado antes do usuário terminar a frase.

Essa regra evita que “abrir” execute algo antes que o usuário diga “abrir app Spotify”.

## Execução Python

O `ModuleRunner` importa dinamicamente o módulo indicado por `request_url`.

Ele procura uma função nesta ordem:

1. `execute`;
2. `run`;
3. `main`.

A função pode receber um argumento.

Exemplo:

```python
def execute(argument: str | None = None) -> dict:
    return {
        "success": True,
        "message": "Ação concluída.",
    }
```

## Pesquisa de argumentos

Um módulo pode oferecer pesquisa complementar.

Nomes aceitos atualmente:

```python
search_arguments
searchArguments
```

Exemplo:

```python
def search_arguments(query: str = "") -> list[dict[str, str]]:
    return [
        {
            "label": "Spotify",
            "value": "C:\\Caminho\\Spotify.exe",
            "description": "Aplicativo",
        }
    ]
```

A interface pode apresentar a lista antes de executar.

## Resultado

O resultado recomendado é:

```python
{
    "success": True,
    "message": "Spotify aberto.",
}
```

Chaves utilizadas pelo núcleo:

- `success`;
- `message`;
- `result`;
- `opened`.

Uma falha controlada pode retornar:

```python
{
    "success": False,
    "message": "Aplicativo não encontrado.",
}
```

Uma exceção deve ser usada quando o fluxo não consegue produzir uma resposta válida.

## Logs

Toda execução deve gerar log.

O registro contém:

- módulo;
- status;
- mensagem;
- data;
- rotina opcional.

O log não deve conter credenciais ou dados sensíveis.

## Comunicação HTTP

A arquitetura do projeto prevê comunicação por HTTP para permitir módulos em diferentes linguagens.

O fluxo conceitual é:

```text
Núcleo IRIS
    ↓ requisição
Serviço do módulo
    ↓ execução
API externa ou recurso local
    ↓ resposta
Núcleo IRIS
```

A implementação HTTP completa ainda não está finalizada. Atualmente existe um módulo FastAPI de teste e abertura de URLs.

No futuro, será necessário definir:

- métodos suportados;
- payload;
- autenticação;
- timeout;
- health check;
- formato de resposta;
- inicialização do processo;
- encerramento;
- portas;
- tratamento de indisponibilidade.

## Módulos padrão

A inicialização atual registra módulos de demonstração, incluindo categorias como:

- Assistente;
- Agenda;
- Arquivos;
- Navegador;
- Sistema;
- Imagens;
- Abrir.

Alguns são apenas estruturas. Outros possuem execução de teste.

## Independência

Um módulo deve evitar conhecer:

- componentes Flet;
- rotas visuais;
- tabelas internas sem contrato;
- cores;
- estado global da tela.

Ele deve receber entrada, executar uma responsabilidade e devolver resultado.

## Segurança

Um módulo pode ter acesso ao computador e a serviços externos.

Por isso, módulos devem declarar:

- finalidade;
- permissões;
- dependências;
- dados utilizados;
- destino de rede;
- ações destrutivas;
- credenciais necessárias.

A instalação de módulos comunitários ainda não possui mecanismo de confiança definido.

## Evolução futura

Ainda precisam ser definidos:

- manifesto;
- versão;
- dependências;
- instalação;
- atualização;
- remoção;
- assinatura;
- permissões;
- compatibilidade;
- documentação embutida;
- inicialização de módulos em outras linguagens.
