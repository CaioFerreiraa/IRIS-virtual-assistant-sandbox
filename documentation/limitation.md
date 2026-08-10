# Limitações e requisitos

## Escopo da primeira versão

A primeira versão da IRIS é um MVP desktop desenvolvido para Windows.

Embora as tecnologias utilizadas permitam estudar outros ambientes, não fazem parte do escopo inicial:

- Linux;
- macOS;
- Android;
- iOS;
- aplicação web;
- execução distribuída entre vários dispositivos.

Compatibilidade futura dependerá de testes e adaptações.

## Idioma

O código utiliza identificadores em inglês, seguindo convenções comuns de desenvolvimento.

A interface e a documentação pública da primeira versão estão disponíveis somente em português do Brasil.

Isso inclui:

- menus;
- mensagens;
- toasters;
- títulos;
- validações;
- comandos documentados;
- textos de ajuda.

Internacionalização não está implementada.

## Requisitos de software

O ambiente atual utiliza:

- Windows;
- Python 3.11;
- Flet 0.85.3;
- SQLAlchemy 2.0.51;
- Alembic 1.18.5;
- FastAPI 0.138.1;
- Uvicorn 0.49.0;
- HTTPX 0.28.1.

As dependências estão listadas em `requirements.txt`.

Instalação para desenvolvimento:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

## Requisitos de hardware

Para a aplicação básica:

- computador compatível com Windows;
- processador capaz de executar Python e Flet;
- memória suficiente para interface e módulos;
- armazenamento para aplicação e banco local.

Para voz:

- microfone;
- driver de áudio compatível;
- capacidade de processamento para o modelo escolhido;
- espaço para baixar modelos de transcrição.

O desempenho do reconhecimento dependerá do modelo, CPU, GPU, memória, ruído, microfone e configurações.

## Internet

A interface e o banco podem funcionar localmente.

Internet poderá ser necessária para:

- instalar dependências;
- baixar modelos de voz;
- acessar módulos comunitários;
- utilizar APIs externas;
- autenticar serviços;
- atualizar a plataforma.

Módulos locais podem funcionar sem conexão, dependendo de sua finalidade.

## Integrações

A IRIS não consegue controlar automaticamente qualquer aplicativo ou site.

Uma integração exige pelo menos uma destas condições:

- API disponível;
- webhook;
- protocolo documentado;
- biblioteca compatível;
- comando local permitido;
- módulo desenvolvido para o serviço.

Alguns sistemas:

- não oferecem API;
- bloqueiam automação;
- exigem licença;
- possuem autenticação complexa;
- limitam chamadas;
- não permitem uso por terceiros;
- alteram seus contratos.

A existência de um serviço não garante compatibilidade.

## Módulos externos

Módulos podem depender de:

- programas instalados;
- permissões do Windows;
- variáveis de ambiente;
- chaves de API;
- contas;
- bibliotecas adicionais;
- portas locais;
- serviços em execução.

A plataforma deverá apresentar essas dependências, mas o contrato definitivo de distribuição ainda não foi criado.

## Reconhecimento de voz

O reconhecimento de voz possui modo básico com Faster-Whisper e modo em tempo real com RealtimeSTT. A experiência final ainda depende de validação prática em diferentes máquinas.

Limitações esperadas:

- atraso em máquinas menos potentes;
- erros com ruído;
- dificuldade com nomes próprios;
- resultados parciais que mudam durante a fala;
- consumo de CPU ou GPU;
- necessidade de configurar o microfone;
- risco de falsos positivos na palavra de ativação.

A voz vem desativada por padrão. O primeiro uso pode baixar modelos grandes. A interface lista os microfones por solicitação do usuário, mas a descoberta ainda depende do PortAudio e dos drivers disponibilizados pelo sistema operacional.

## Rotinas

O banco possui estrutura inicial para rotinas, mas o scheduler completo ainda não está disponível.

Ainda precisam ser definidos:

- editor visual;
- validação de cron;
- comportamento após falha;
- execução em segundo plano;
- recuperação após reinício;
- concorrência;
- cancelamento;
- limites de segurança.

## Credenciais

O conceito BYOK faz parte da proposta, mas o cofre seguro ainda não está implementado.

Enquanto não houver armazenamento protegido:

- credenciais não devem ser inseridas no banco;
- segredos não devem ser incluídos no repositório;
- tokens não devem aparecer em logs;
- testes devem usar valores falsos.

## Segurança de módulos

Executar um módulo Python significa executar código no computador do usuário.

Antes de oferecer instalação comunitária, a IRIS precisará definir mecanismos de confiança e revisão.

A versão atual não deve ser considerada uma sandbox de segurança para código desconhecido.

## Banco local

O SQLite simplifica a instalação, mas possui limitações:

- não é indicado para grande volume concorrente;
- o arquivo pode ser apagado ou corrompido;
- backups ainda não possuem fluxo visual;
- o caminho atual depende do diretório de execução;
- migrações precisam ser cuidadosamente testadas.

## Distribuição

O projeto ainda está em ambiente de desenvolvimento.

Não há garantia de:

- instalador definitivo;
- atualização automática;
- assinatura de executável;
- recuperação automática;
- suporte comercial;
- compatibilidade com toda máquina Windows.

## Limites de responsabilidade

A IRIS executa ações configuradas pelo usuário e pelos módulos instalados.

Módulos que alteram arquivos, enviam mensagens, controlam sistemas ou consomem APIs devem apresentar confirmação e documentação adequadas.

A plataforma não deve ocultar ações potencialmente destrutivas.
