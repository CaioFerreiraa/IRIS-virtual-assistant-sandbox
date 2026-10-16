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
`cryptography.Fernet`, sem uma segunda camada de criptografia nos valores.
Somente a chave mestra Fernet fica no **Windows Credential Manager** (Gerenciador
de Credenciais do Windows), protegida no contexto do usuário que executa a IRIS.
Ela é criada apenas quando o primeiro valor precisa ser criptografado e ainda
não há chave nem valores criptografados existentes. Cadastrar uma chave sem
valor não cria uma credencial. A implementação segue o
[contrato oficial do Fernet](https://cryptography.io/en/50.0.2/fernet/).

Essa proteção não isola segredos de código malicioso executado no contexto do
mesmo usuário do Windows. Módulos Python precisam ser revisados e confiáveis.

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

O acesso usa [keyring](https://github.com/jaraco/keyring/blob/v25.6.0/keyring/backends/Windows.py) com uma instância local e explícita de
`keyring.backends.Windows.WinVaultKeyring`, sem alterar o backend global de
outros componentes. Os identificadores fixos são serviço `IRIS.Vault` e usuário
lógico `master-key-v1`; eles não dependem do diretório de execução. A persistência
`local machine` mantém a credencial após reiniciar a IRIS e iniciar uma nova
sessão do mesmo usuário, na mesma máquina. Há somente uma credencial para a
chave mestra, compartilhada pelas Vault Keys e pelas instalações da IRIS desse
usuário. Não há credencial individual por variável.

O backend só é importado e inicializado quando uma operação exige criptografia.
Fora do Windows ou se o Credential Manager falhar, somente essa operação fica
indisponível, com mensagem em português. A abertura da aplicação, listagem,
pesquisa, sugestões, cadastro sem valor, edição de metadados com preservação do
valor, limpeza e exclusão continuam disponíveis. Nenhuma dessas operações
remove a chave mestra compartilhada. Não há alternativa por arquivo, texto puro
ou backend inseguro, nem implementação manual de DPAPI.

A criação e a migração usam um bloqueio compartilhado entre threads e um mutex
(bloqueio de exclusão mútua) nativo do Windows, nomeado por usuário, entre
processos e sessões. A seção protegida relê o armazenamento antes de decidir
criar a chave. Background e rotinas usam threads do processo desktop; o backend
Node.js de Notas não acessa o armazenamento da chave mestra.

### Migração automática do arquivo legado

A primeira operação que precisar da chave verifica `.iris_vault.key`, na raiz
do projeto (o argumento `key_path` do serviço só identifica esse arquivo legado).
Não há acesso ao Credential Manager nas migrations do Alembic, nem alteração
no esquema do banco.

1. Sem credencial no Windows, o serviço lê e valida a chave Fernet do arquivo.
2. Ele verifica todos os valores não nulos do banco com essa chave, descartando
   o texto descriptografado sem registrá-lo nem persistir sua versão em texto puro.
3. Grava exatamente a mesma chave no Credential Manager, sem recriptografar ou
   alterar os valores existentes no SQLite.
4. Relê a credencial e compara o conteúdo com a chave original.
5. Somente após essas verificações remove o arquivo legado.

Se houver interrupção após a gravação, a próxima tentativa reconhece a mesma
chave, repete as verificações e conclui a remoção sem sobrescrever a credencial.
Falhas de leitura, gravação, confirmação ou validação preservam o arquivo e os
dados. Se a remoção falhar, a credencial já confirmada permanece e a operação
informa que é necessário verificar as permissões e tentar novamente.

Uma credencial existente sempre tem seu formato validado. Se ela diferir da
chave legada, a migração para com uma mensagem de conflito: nenhuma credencial
é substituída e nenhum arquivo é apagado automaticamente. É necessário verificar
a origem do banco e das chaves. Isso também se aplica a duas instalações antigas
com chaves diferentes no mesmo usuário. Encerre versões antigas da IRIS antes
de migrar; elas ainda dependem do arquivo.

Se não houver credencial nem arquivo e já existirem valores criptografados,
a operação informa chave indisponível e **não gera uma substituta**. Se não
existirem valores, uma nova chave é gravada e sua leitura é confirmada antes
de criptografar o primeiro valor. Após a migração, a IRIS não recria nem usa
`.iris_vault.key` como alternativa de armazenamento.

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

O acesso à chave mestra depende do contexto do usuário do Windows. Essa
proteção não cria isolamento entre programas executados pelo mesmo usuário,
nem uma sandbox para módulos Python. Código malicioso nesse contexto pode
acessar os segredos. Os caminhos de execução
ocultam valores conhecidos do Vault em resultados e mensagens de erro, mas o
autor do módulo deve impedir escrita em logs ou arquivos próprios.

## Backup e recuperação

**Copiar somente o banco para outro computador ou usuário não garante recuperar
os valores.** A credencial original precisa estar disponível no contexto do
usuário do Windows que a criou. Perder essa chave mestra impede a leitura dos
valores; gerar outra não os recupera. Não há novo fluxo de exportação, backup,
rotação ou recuperação automática nesta versão.

Credencial ausente ou inválida, conflito de chaves, arquivo legado inválido e
valor corrompido geram mensagens sem o segredo, a chave mestra, o conteúdo
criptografado ou detalhes sensíveis de exceções. Listar, editar metadados,
limpar e excluir não exigem descriptografia. O arquivo legado só é removido
após a migração validada descrita acima.

## Validação manual no Windows

Use uma conta Windows de teste e apenas valores fictícios. Os testes automáticos
usam armazenamento em memória ou mocks e nunca acessam as credenciais reais.

1. Instale as dependências de `requirements.txt`. Em Configurações → Vault Keys,
   cadastre uma chave sem valor e depois preencha um valor fictício. Confirme
   a presença de `IRIS.Vault` no Gerenciador de Credenciais, sem revelar seu conteúdo.
2. Reinicie a IRIS e depois encerre e inicie a sessão Windows. Confirme que um
   módulo local de teste ainda recebe o valor e que resultados e logs o ocultam.
3. Em uma instalação legada de teste com dados fictícios, acione uma operação
   que use o Vault. Confirme que os valores continuam utilizáveis e que
   `.iris_vault.key` foi removido. Repita a operação e teste edição e limpeza.
4. Confira o login de Notas com as credenciais didáticas e o uso de `TOKEN_NOTAS`
   para criar, editar e excluir uma nota no backend local. A lista e o formulário
   devem continuar mostrando somente metadados e o marcador de valor oculto.

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
