# Fluxo do sistema e roadmap

## Objetivo deste documento

Este documento descreve:

- o fluxo atual da aplicação;
- como os módulos são acionados;
- como a comunicação deverá evoluir;
- quais são os próximos marcos do projeto.

## Fluxo atual de inicialização

```text
main.py
   ↓
init_db()
   ↓
Criação e compatibilidade do SQLite
   ↓
Seed dos módulos padrão
   ↓
Registry de modules/installed
   ↓
Inicialização do Flet
   ↓
Montagem da interface
   ↓
Carregamento da rota inicial
```

O gerenciador de voz é preparado automaticamente. Backends Python de módulos raiz também podem iniciar isoladamente quando o manifesto oferece auto start e o usuário habilita a preferência. O scheduler ainda não é iniciado automaticamente.

## Fluxo atual de comando

```text
Usuário digita
   ↓
Input principal
   ↓
Filtro de módulos
   ↓
Seleção de caminho
   ↓
Resolução para module_id
   ↓
HomeService
   ↓
CommandProcessor
   ↓
ModuleRepository
   ↓
ModuleRunner ou abertura de URL
   ↓
Resultado
   ↓
Log
   ↓
Toaster e histórico
```

### 1. Entrada

O usuário escreve no campo principal ou escolhe uma sugestão.

### 2. Pesquisa

A interface consulta os caminhos dos módulos e apresenta opções compatíveis.

### 3. Validação

O sistema verifica:

- se existe comando;
- se o módulo foi encontrado;
- se ele é executável;
- se há destino configurado;
- se o método é suportado.

### 4. Argumento

Alguns módulos precisam de um item adicional.

Exemplo:

```text
Abrir > App
```

Pode solicitar qual programa deve ser aberto.

### 5. Execução

A Home usa background e o núcleo delega para:

- entry point Python;
- abertura de URL;
- futuramente requisição HTTP;
- futuramente processo externo.

### 6. Resultado

O módulo devolve uma resposta estruturada.

### 7. Histórico

O sistema registra sucesso ou erro.

### 8. Feedback

A interface mostra toaster e disponibiliza a execução no histórico.

## Comunicação atual dos módulos

### Python local

O entry point é importado no processo da IRIS.

Vantagens:

- integração simples;
- baixa latência;
- acesso direto a bibliotecas Python.

Limitações:

- compartilha o processo;
- erro grave pode afetar a aplicação;
- código desconhecido representa risco;
- não atende módulos em outras linguagens.

### URL de teste

O método atual chamado `GET` abre uma URL no navegador.

Ele serve ao protótipo, mas ainda não implementa o contrato HTTP descrito na arquitetura.

## Comunicação planejada

Para permitir módulos em outras linguagens, cada módulo poderá executar como serviço local ou remoto autorizado.

Fluxo:

```text
IRIS
   ↓ HTTP
Módulo
   ↓
Regra ou integração
   ↓
Serviço externo
   ↓
Módulo
   ↓ resposta padronizada
IRIS
```

Um contrato futuro deverá definir:

- health check;
- endpoint de execução;
- endpoint de argumentos;
- payload;
- timeout;
- erros;
- autenticação;
- versão;
- inicialização;
- encerramento.

## Fluxo atual de voz

```text
Microfone
   ↓
RealtimeSTT
   ↓
Faster-Whisper
   ↓ texto parcial
Input Flet
   ↓
Filtro progressivo
   ↓
Primeiro item pré-selecionado
   ↓ silêncio ou “enviar”
CommandProcessor
   ↓
Módulo
```

A palavra “IRIS” ativa a interação e é retirada do comando enviado para pesquisa.

## Marcos concluídos

- [x] Estrutura modular em camadas.
- [x] Interface desktop inicial.
- [x] Tema e identidade visual.
- [x] Header, sidebar e roteamento.
- [x] Banco SQLite.
- [x] Modelos de módulo, rotina e log.
- [x] Hierarquia de módulos.
- [x] Seed inicial.
- [x] Pesquisa e seleção de módulos.
- [x] Execução de entry point Python.
- [x] Pesquisa de argumentos.
- [x] Registro de logs.
- [x] Tela de histórico.
- [x] Toaster, tabela e diálogo reutilizáveis.
- [x] `requirements.txt`.

## Próximo marco: documentação

- [x] Criar documentação Markdown.
- [x] Criar rota visual de documentação.
- [x] Renderizar Markdown na interface.
- [x] Adicionar navegação lateral.
- [x] Permitir busca em modal.
- [ ] Refinar navegação por âncoras internas.
- [ ] Definir atualização e cache.
- [ ] Permitir acesso dos agentes aos mesmos arquivos.

## Próximo marco: voz

- [x] Integrar RealtimeSTT.
- [x] Integrar Faster-Whisper.
- [x] Criar serviço de captura básico.
- [x] Criar transcrição parcial em tempo real.
- [x] Detectar “IRIS” pela transcrição.
- [x] Atualizar input por callback seguro.
- [x] Atualizar dropdown progressivamente.
- [x] Estabilizar transcrição por silêncio.
- [x] Concluir por “enviar”.
- [x] Criar configurações de voz persistidas.
- [x] Tratar desligamento do microfone.
- [ ] Testar desempenho em CPU.
- [ ] Medir precisão da ativação e falsos positivos com usuários.
- [x] Listar microfones disponíveis no formulário.

## Próximo marco: módulos HTTP

- [ ] Separar `OPEN_URL` de `GET`.
- [ ] Definir contrato de requisição.
- [ ] Definir resposta padrão.
- [ ] Definir health check.
- [ ] Definir timeout.
- [ ] Criar gerenciador de processos.
- [ ] Inicializar módulos necessários.
- [ ] Encerrar módulos ao fechar.
- [ ] Testar módulo em outra linguagem.

## Próximo marco: rotinas

- [ ] Criar tela.
- [ ] Criar editor de sequência.
- [ ] Validar cron.
- [ ] Implementar scheduler.
- [ ] Definir falha e continuidade.
- [ ] Registrar execução completa.
- [ ] Recuperar agendamentos após reinício.

## Próximo marco: cofre

- [ ] Definir armazenamento seguro.
- [ ] Definir modelo de metadados.
- [ ] Criar tela de credenciais.
- [ ] Criar injeção por módulo.
- [ ] Ocultar valores.
- [ ] Criar remoção e rotação.
- [ ] Auditar logs.

## Próximo marco: comunidade

- [x] Definir manifesto local de módulo versão 1.
- [x] Descobrir pastas isoladamente.
- [x] Sincronizar por chave pública.
- [x] Criar tela nativa de módulo e configurações de texto.
- [x] Registrar falhas técnicas em `module.log`.
- [ ] Definir empacotamento.
- [ ] Definir repositório de catálogo.
- [ ] Definir instalação.
- [ ] Definir verificação.
- [ ] Definir atualização.
- [ ] Definir remoção.
- [ ] Definir permissões.

## Pós-MVP

- suporte a Linux;
- suporte a macOS;
- internacionalização;
- distribuição com instalador;
- atualização automática;
- sincronização opcional;
- catálogo comunitário;
- assinatura de módulos;
- modelos de wake word treinados;
- testes de usabilidade ampliados.

## Fora do escopo atual

- inteligência artificial generativa integrada ao núcleo;
- controle automático de qualquer site sem API ou módulo;
- versão mobile completa;
- execução segura de código desconhecido como sandbox;
- automação irrestrita sem confirmação;
- substituição de plataformas de automação residencial.
