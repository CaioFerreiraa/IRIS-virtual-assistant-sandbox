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

O conceito faz parte da arquitetura e do artigo, mas o cofre ainda não foi implementado.

O serviço atual de credenciais é inicial e não representa armazenamento seguro completo.

Até a implementação:

- não salve chaves no SQLite;
- não inclua segredo em código;
- não envie credencial ao Git;
- não mostre valor integral;
- não registre segredo em log;
- use variáveis de ambiente apenas como solução temporária de desenvolvimento.

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

O SQLite poderá guardar metadados:

- nome;
- serviço;
- módulo associado;
- identificador;
- data;
- status;
- referência segura.

O valor secreto deve ser protegido fora de texto puro.

## Arquitetura futura

<!-- Conteúdo futuro: mecanismo de armazenamento ainda não definido. -->

## Integração com o Windows

<!-- Conteúdo futuro: uso de Credential Manager, DPAPI ou alternativa ainda não decidido. -->

## Modelo de dados

<!-- Conteúdo futuro: tabelas e relacionamentos ainda não definidos. -->

## Interface de senhas

<!-- Conteúdo futuro: fluxo visual ainda não definido. -->

## Contrato para módulos

<!-- Conteúdo futuro: forma de solicitar e receber credenciais ainda não definida. -->

## Ciclo de vida

<!-- Conteúdo futuro: criação, leitura, rotação, revogação e exclusão ainda não definidos. -->

## Ameaças e proteção

<!-- Conteúdo futuro: modelo de ameaças ainda não documentado. -->

## Backup e recuperação

<!-- Conteúdo futuro: estratégia ainda não definida. -->

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
