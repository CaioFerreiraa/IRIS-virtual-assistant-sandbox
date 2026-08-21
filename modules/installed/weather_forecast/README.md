# Previsão do tempo

Módulo de caminho feliz que consulta os endpoints públicos do Open-Meteo para transformar um nome de local em coordenadas e obter a previsão meteorológica.

## Como informar o local

Há duas formas, em ordem de prioridade:

1. informar uma cidade, município ou código postal como argumento da requisição;
2. preencher `Local padrão` na aba `Configurações` da rota deste módulo.

Quando `Local padrão` está vazio, `should_request_argument(variables)` faz a Home abrir o campo de argumento. Se uma chamada direta ainda chegar sem as duas formas, a execução é interrompida com a orientação para informar o local ou configurar a rota. Quando o local padrão está preenchido, selecionar o módulo executa a previsão diretamente. O argumento da requisição sempre substitui temporariamente o local padrão, sem alterar o valor salvo.

## Exemplos

- comando com argumento: `previsão Campinas`;
- busca manual no campo de argumentos: `São Paulo`;
- configuração persistente: definir `Local padrão` como `Recife`.

## O que este módulo testa

- manifesto instalado e runtime Python;
- variável opcional e editável `default_location`;
- variável obrigatória e editável `forecast_days`;
- decisão condicional por `should_request_argument(variables)`;
- solicitação do argumento quando a Home detecta `search_arguments`;
- sugestões remotas de cidades com rótulo, valor e descrição;
- geocodificação por nome ou código postal;
- cache em memória da localização selecionada;
- requisição HTTP real em background;
- timeout e erros de conexão sem bloquear nem derrubar a UI;
- validação de local ausente, local desconhecido e quantidade de dias;
- condições atuais e resumo diário;
- tradução dos códigos meteorológicos WMO para português;
- resposta estruturada com `success`, `message` e `result`;
- registro de sucesso ou erro no histórico;
- ausência de chave de API ou segredo.

## Configurações

### Local padrão

Texto opcional usado somente quando a execução não recebe argumento. Pode ser alterado ou apagado na rota do módulo.

### Dias da previsão

Número inteiro entre 1 e 7. O valor padrão é 3.

## Serviços externos

- geocodificação: [Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api);
- previsão: [Open-Meteo Weather Forecast API](https://open-meteo.com/en/docs).

Os endpoints públicos utilizados não exigem credencial no fluxo implementado. O uso continua sujeito à disponibilidade, licença e políticas do Open-Meteo.

## Limitações

- requer conexão com a internet;
- nomes ambíguos usam a opção escolhida na lista ou o primeiro resultado da geocodificação;
- a previsão é uma estimativa do modelo meteorológico e pode divergir das condições locais;
- o cache de localizações existe apenas durante o processo atual;
- o módulo não armazena histórico meteorológico próprio.
