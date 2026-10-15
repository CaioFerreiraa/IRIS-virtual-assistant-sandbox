# Login nas notas

## O que este módulo faz

Este submódulo declara uma requisição HTTP `POST` para o backend local de
Notas. Na aba “Execução”, o corpo JSON mostra as referências
`{{vk.LOGIN_NOTAS}}` e `{{vk.SENHA_NOTAS}}`; a configuração “Resposta → Vault”
mostra que `data.token` da resposta será salvo em `TOKEN_NOTAS`. Os valores
reais não aparecem na configuração, no resultado nem no log.

Cadastre as três chaves em **Configurações → Vault Keys** antes de executar:

- `LOGIN_NOTAS`: `admin` nesta demonstração;
- `SENHA_NOTAS`: `admin` nesta demonstração;
- `TOKEN_NOTAS`: pode começar sem valor, com **IRIS pode alterar** ativado.

Os nomes digitados em minúsculas (`login_notas`, `senha_notas` e
`token_notas`) são normalizados para maiúsculas pelo Vault. Não ative a
permissão de alteração pela IRIS nas duas chaves de entrada.

Inicie o serviço pelo módulo raiz Notas antes de executar este login. Depois,
“Criar nota”, “Editar nota” e “Deletar nota” usarão `TOKEN_NOTAS`. “Abrir notas”
não usa chave alguma, mas o navegador pedirá o login da página. Um novo login
substitui o token anterior; após reiniciar o backend, execute o login
novamente. As credenciais fixas são apenas didáticas, não adequadas para
produção.
