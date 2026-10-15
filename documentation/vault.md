# Cofre de credenciais e BYOK

## O que é BYOK

BYOK significa *Bring Your Own Key*.

Na IRIS, isso significa que cada usuário fornece suas próprias:

- chaves de API;
- credenciais;
- tokens;
- autorizações;
- contas de integração.

A plataforma não deve compartilhar uma chave global entre todos os usuários.

## Por que utilizar BYOK

O modelo oferece:

- controle individual;
- separação entre usuários;
- revogação pelo próprio usuário;
- transparência sobre serviços utilizados;
- redução de credenciais compartilhadas;
- independência de um provedor central da IRIS.

## Exemplo

Um módulo de agenda poderá exigir uma autorização do Google Calendar.

O usuário:

1. escolhe o módulo;
2. fornece ou autoriza a credencial;
3. associa a credencial ao módulo;
4. pode revogar quando desejar.

A IRIS não deve expor o valor em logs ou telas comuns.

## Estado atual

Vault Keys é a primeira versão de variáveis globais locais, cadastradas em
Configurações → Vault Keys. O valor é criptografado no SQLite com
`cryptography.Fernet`. A chave Fernet é gerada quando o primeiro valor é
gravado e fica em
`.iris_vault.key`, na raiz do projeto, ignorada pelo Git. A implementação segue
o [contrato oficial do Fernet](https://cryptography.io/en/50.0.2/fernet/).

É uma proteção local básica para o MVP (produto mínimo viável), **não uma
solução de segurança pronta para produção**. Quem obtiver o banco e o arquivo
da chave poderá ler os valores. Módulos Python precisam ser revisados e confiáveis.

## Princípios obrigatórios

### Menor privilégio

Cada módulo deve receber apenas a credencial necessária.

### Separação

Módulos diferentes não devem acessar todos os segredos por padrão.

### Ocultação

A interface deve mascarar valores.

### Revogação

O usuário deve remover uma credencial.

### Rotação

O sistema deve permitir substituição sem recriar toda a configuração.

### Auditoria

A plataforma pode registrar o uso de uma referência, mas nunca o segredo.

### Criptografia adequada

Não criar algoritmo próprio.

## Dados que podem ser armazenados no banco

A tabela `vault_keys` guarda metadados e `encrypted_value` nulo ou como valor
Fernet criptografado. Não há coluna com segredo em texto puro. A lista usada
pela interface não inclui valor nem conteúdo criptografado.

## Arquitetura futura

O MVP usa um serviço direto e um repository. Não há providers, rotação,
autenticação real, permissões por usuário, captura não declarada de respostas
HTTP ou cache de valores descriptografados. Um módulo HTTP ou entry point
Python pode solicitar uma gravação explícita no Vault sob as condições abaixo.

## Integração com o Windows

Windows Credential Manager ficará para uma versão futura. DPAPI e serviços
externos também não fazem parte desta versão.

## Modelo de dados

`vault_keys` contém `id`, `name`, `description`, `encrypted_value`,
`allow_iris_update`, `created_date` e `edited_date`. A flag vem desligada.
`Module.vault_keys_json` guarda uma lista JSON simples de nomes. Não existe
relação N:N: os módulos que usam cada chave são calculados por essa lista.
Sincronizar manifestos não cria automaticamente chaves.

## Interface de senhas

A aba **Configurações → Vault Keys** substitui o placeholder de senhas. A tabela
mostra nome, descrição, valor mascarado (`••••••••`), módulos que usam,
permissão de alteração e ações. Sem módulos associados, mostra “Nenhum módulo”.
Não há botão de revelar ou copiar. O formulário usa duas colunas: nome,
valor e permissão ficam na primeira; a descrição ocupa sozinha a segunda. O
cadastro aceita descrição opcional. Na edição, o nome fica visualmente desabilitado.
Se houver valor, o campo de senha mostra um marcador censurado fixo, nunca o
segredo real. Manter o marcador preserva o valor criptografado; apagá-lo e
salvar deixa a chave sem valor. Também é possível digitar um novo valor.
Uma chave sem valor aparece como `—` na tabela e não é entregue aos módulos.
A pesquisa da tabela não consulta o valor.
A exclusão permite continuar mesmo com módulos afetados, após confirmação.

## Contrato para módulos

Declare `vault_keys` no nível raiz, mantendo `schema_version: 1`. É uma lista
opcional de strings em maiúsculas, sem duplicados e sem metadados. Quando
omitida, equivale a `[]`. Cada nome segue `^[A-Z_][A-Z0-9_]*$`.

### HTTP

Exemplo completo para uma pasta contendo também `README.md`:

```json
{
    "schema_version": 1,
    "module": {
        "module_public_key": "example.notes",
        "name": "Criar nota",
        "call_name": "criar nota",
        "parent_public_key": null,
        "readme": "README.md"
    },
    "runtime": null,
    "vault_keys": ["NOTES_ACCESS_KEY"],
    "variables": [],
    "http_request": {
        "method": "POST",
        "url": "http://127.0.0.1:8765/api/notes",
        "argument_enabled": true,
        "params": [],
        "authorization": {"type": "none"},
        "headers": [{
            "key": "X-IRIS-Vault",
            "value": "{{vk.NOTES_ACCESS_KEY}}",
            "description": "Chave global injetada na execução.",
            "enabled": true
        }],
        "body": {"mode": "raw_json", "content": "{\"text\":\"{{argument}}\"}"},
        "scripts": {"pre_request": "", "post_response": ""}
    }
}
```

`{{vk.NOME}}` é substituído nos campos textuais habilitados de URL, parâmetros,
headers (cabeçalhos) e body (corpo), somente na execução. `{{argument}}` continua
reservado ao argumento. Um placeholder não declarado interrompe a execução.
Na interface, digitar `vk.` abre as sugestões de chaves declaradas e
configuradas para o módulo. A seleção insere a referência completa, por exemplo
`{{vk.NOTES_ACCESS_KEY}}`. Uma referência inexistente deixa o fundo do campo
vermelho. Campos que contêm `{{argument}}` usam fundo azul acinzentado pastel.
Uma chave declarada e ausente gera “A Vault Key NOTES_ACCESS_KEY não foi
configurada.”, sem enviar o placeholder literal. Authorization continua
aceitando somente `{"type":"none"}`; não há fluxo Bearer específico.
Referências podem substituir valores sensíveis, mas segredos literais
continuam proibidos no manifesto e nas personalizações HTTP.

Uma requisição HTTP pode declarar `response_vault` com `key` e `path`,
por exemplo `{"key": "TOKEN_NOTAS", "path": "data.token"}`. O caminho
usa nomes de propriedades JSON separados por pontos; listas e expressões
JSONPath não são suportadas. A chave deve constar em `vault_keys`, existir
no Vault e permitir alteração pela IRIS. Essa condição é conferida antes do
envio. Em resposta bem-sucedida, o campo precisa ser texto não vazio; só
então o valor é criptografado no Vault. A resposta exibida e o histórico
não revelam o valor capturado, inclusive quando uma resposta de erro
contiver o mesmo campo. Sem `response_vault`, a resposta não altera o Vault.

### Python

Manifesto completo acompanhado de `README.md` e `main.py`:

```json
{
    "schema_version": 1,
    "module": {
        "module_public_key": "example.python",
        "name": "Exemplo Python",
        "call_name": "exemplo python",
        "parent_public_key": null,
        "readme": "README.md"
    },
    "runtime": {"type": "python", "entrypoint": "main.py", "supports_auto_start": false},
    "vault_keys": ["MINHA_CHAVE"],
    "variables": []
}
```

```python
def execute(argument=None, variables=None, vault=None):
    token = (vault or {}).get("MINHA_CHAVE")
    if not token:
        return {
            "success": False,
            "message": "Configure MINHA_CHAVE nas Vault Keys.",
        }
    # Use token na integração; nunca devolva ou registre seu valor.
    return {"success": True, "message": "Chave disponível para a integração."}
```

Somente funções que aceitam `vault` ou `**kwargs` recebem esse dicionário. Ele
contém somente nomes declarados e existentes, descriptografados naquela
execução. Ausentes não aparecem: use `.get()` como usaria `os.getenv()`.
Entrypoints antigos continuam compatíveis. O Vault não entra em `variables`,
não altera `os.environ` e não é entregue a callbacks de busca ou auto start.
Execuções diretas, em segundo plano e de rotinas usam o mesmo processador.

Para guardar um valor obtido na execução Python, o entry point pode retornar
`{"success": True, "vault_update": {"name": "TOKEN_NOTAS", "value": token}}`.
A chave de destino precisa estar declarada no `vault_keys` do módulo,
previamente cadastrada pelo usuário e com **IRIS pode alterar** ativado.
Uma falha, chave não declarada, ausente ou sem permissão impede a gravação.
O processador remove `vault_update` antes de retornar ou registrar o
resultado e oculta o novo valor caso ele apareça em outro campo. Não devolva
nem registre o token por outros meios no próprio módulo.

## Ciclo de vida

1. O usuário cadastra nome, valor opcional, descrição opcional e permissão de
   alteração pela IRIS, desligada por padrão. Quando há valor, o serviço
   criptografa antes de salvar.
2. Listagens e formulários consultam somente metadados, sem descriptografar.
3. Na execução, somente nomes declarados pelo módulo são resolvidos. Os valores
   ficam em variáveis locais daquela execução, sem cache global.
4. Editar substitui o valor criptografado; Novo valor vazio limpa o atual.
   O usuário sempre pode editar, independentemente de `allow_iris_update`.
5. Excluir exige confirmação e informa os módulos afetados. HTTP falha na
   próxima utilização; Python recebe um dicionário sem o nome ausente.

O nome é único, normalizado para maiúsculas e segue `^[A-Z_][A-Z0-9_]*$`.
Depois de criar, ele não pode mudar: exclua e cadastre novamente para renomear.
`update_value_by_iris(name, new_value)` exige `allow_iris_update=true`.
O processador usa esse método para `vault_update` de módulos Python e o
serviço HTTP para `response_vault`.

## Ameaças e proteção

A proteção depende do arquivo local e do acesso ao computador. Não há
isolamento de código Python nem controle por usuário. Os caminhos de execução
ocultam valores conhecidos do Vault em resultados e mensagens de erro, mas o
autor do módulo deve impedir escrita em logs ou arquivos próprios.

## Backup e recuperação

**Perder `.iris_vault.key` impede a leitura dos valores existentes.** Guarde o
banco e o arquivo da chave em backup privado. Gerar outra chave não recupera
os valores antigos. Arquivo ausente, inválido ou valor corrompido gera mensagem
sem o segredo nem o conteúdo criptografado. Listar e excluir não exige leitura
dos valores.

## Regras para logs

Nunca registrar:

- token;
- senha;
- chave;
- segredo de cliente;
- refresh token;
- cabeçalho Authorization;
- URL com segredo;
- corpo de autenticação.

Mensagens recomendadas:

```text
Credencial não encontrada.
Credencial expirada.
Autorização recusada.
```

Não recomendada:

```text
Token abc123... inválido.
```

## Responsabilidade do usuário

O usuário é responsável por:

- utilizar credenciais autorizadas;
- respeitar os termos do serviço;
- revogar acessos indevidos;
- não compartilhar chaves;
- compreender permissões.

A IRIS deve facilitar esse controle e não ocultar quais módulos utilizam credenciais.

## Demonstração Notas

Cadastre `LOGIN_NOTAS` e `SENHA_NOTAS` com `admin` e sem permissão
de alteração pela IRIS. Cadastre `TOKEN_NOTAS` sem valor inicial e com
**IRIS pode alterar** ativado. Nomes digitados em minúsculas são normalizados
para maiúsculas. O submódulo Login nas notas mostra uma requisição HTTP
`POST /api/login` com `{{vk.LOGIN_NOTAS}}` e `{{vk.SENHA_NOTAS}}` no corpo
JSON. Seu `response_vault` envia `data.token` para `TOKEN_NOTAS`. Criar, editar e deletar
notas enviam esse token no header `X-IRIS-Vault`; Abrir notas não usa Vault.
O backend de demonstração aceita somente `admin`/`admin`; essas credenciais
fixas não são adequadas para produção. Um novo login invalida o token
anterior, e reiniciar o backend exige novo login. A API de notas exige
`X-IRIS-Vault` ou cookie de sessão válido; a página web redireciona visitantes
sem sessão para `/login`. Não há seed de Vault Keys.

Veja [Banco de dados](database.md), [Módulos](modules.md) e
[Desenvolvimento de módulos](module-development.md).
