# Contratos de entrada

Submódulo organizacional que agrupa as três funções reconhecidas pelo runner.

## O que este módulo testa

- submódulo com `runtime: null`;
- `is_executable: false` explícito;
- item organizacional que também possui filhos;
- terceiro nível de hierarquia na sidebar;
- breadcrumb e navegação entre pai e filhos;
- bloqueio de execução de um item sem runtime.

## Filhos

O runner procura funções nesta ordem: `execute`, `run` e `main`. Cada filho fornece somente uma delas, permitindo confirmar cada fallback isoladamente.
