# Política de Segurança

## Versões suportadas

A IRIS ainda está em desenvolvimento e não possui uma versão estável suportada.
Correções de segurança são aplicadas na branch `main`; branches antigas podem
não receber atualizações.

## Relatar uma vulnerabilidade

Não abra uma issue pública com credenciais, dados pessoais, exploit funcional
ou instruções que exponham usuários.

Use o recurso privado **Report a vulnerability** da aba Security do repositório.
Se ele não estiver disponível, contate privadamente um mantenedor pelo canal
publicado em seu perfil do GitHub e compartilhe apenas o mínimo necessário para
estabelecer um canal seguro.

Inclua, quando possível:

- versão ou commit afetado;
- sistema operacional;
- impacto observado;
- passos mínimos para reprodução;
- mitigação conhecida;
- indicação de qualquer dado que possa ter sido exposto.

## Segurança de módulos

Módulos Python são importados e executados no mesmo processo da IRIS. O registry
isola falhas de inicialização, mas não restringe acesso a arquivos, rede,
processos ou recursos do sistema operacional.

Até que instalação, origem, permissões e verificação sejam implementadas:

- execute somente módulos que você escreveu ou revisou;
- não trate `module.log` como uma sandbox;
- não coloque tokens, senhas ou chaves no manifesto;
- não habilite auto start para código sem origem conhecida;
- não publique módulos que realizem ações ocultas.

Consulte [Limitações](documentation/limitation.md) e
[Desenvolvimento de módulos](documentation/module-development.md) para o estado
atual do contrato.
