# Relatório Final de Avaliação de Machine Learning — Interlagos

## 1. Objetivo

Esta etapa tem como objetivo aplicar técnicas de Machine Learning aos dados históricos do Grande Prêmio de São Paulo, em Interlagos, buscando identificar os fatores de desempenho, classificação, estratégia e contexto associados à vitória de um piloto.

A unidade de análise adotada é **piloto × corrida**.

O modelo desenvolvido nesta etapa possui natureza **histórica, explicativa e exploratória**, sendo utilizado também para avaliar o ordenamento relativo dos pilotos dentro de cada corrida.

O modelo atual **não deve ser interpretado como um modelo de previsão pré-corrida**, pois parte das features utilizadas somente se torna conhecida durante a realização da prova.

A aplicação ao contexto de Gabriel Bortoleto é realizada como apoio à análise de competitividade e construção de cenários, e não como estimativa determinística de sua probabilidade futura de vitória.

---

## 2. Dataset final para modelagem

O dataset de Machine Learning foi construído a partir das informações consolidadas na camada Gold do projeto.

### 2.1 Granularidade

Cada registro representa:

> **1 piloto em 1 corrida de Interlagos**

A chave lógica é composta pela corrida e pelo piloto, sendo utilizada também uma chave técnica denominada `pilot_race_key`.

### 2.2 Dimensão do dataset

O dataset final contém:

- **140 registros piloto-corrida**;
- **7 corridas**;
- **7 registros classificados como vitória**;
- **133 registros classificados como não vitória**.

As temporadas consideradas são:

- 2018;
- 2019;
- 2021;
- 2022;
- 2023;
- 2024;
- 2025.

A temporada de 2020 não possui uma corrida válida de Interlagos no recorte utilizado.

### 2.3 Variável alvo

A variável alvo é:

`vitoria`

Definição:

- `1`: piloto terminou a corrida na primeira posição;
- `0`: piloto não venceu a corrida.

A coluna `position` é utilizada exclusivamente para construção do target e não é disponibilizada ao modelo como feature.

---

## 3. Features utilizadas

Foram utilizadas **18 features**, sendo 16 numéricas e 2 categóricas.

As features representam diferentes dimensões da corrida:

- classificação/largada;
- ritmo de corrida;
- cobertura das informações de ritmo;
- pit stops;
- stints;
- pneus;
- condições meteorológicas.

Entre as variáveis utilizadas estão:

- `grid`;
- `ritmo_representativo_pct`;
- `voltas_analisadas`;
- `voltas_disponiveis`;
- `cobertura_ritmo_pct`;
- `qtd_pit_stops`;
- `duracao_mediana_pit_convencional`;
- `qtd_stints`;
- `qtd_compostos_distintos`;
- `primeiro_composto`;
- `composto_mais_utilizado`;
- `voltas_stint_medio`;
- `air_temp_media`;
- `track_temp_media`;
- `humidity_media`;
- `pressure_media`;
- `wind_speed_medio`;
- `rainfall_ocorreu`.

Variáveis diretamente relacionadas ao resultado final foram excluídas das features para evitar vazamento direto do target.

Entre elas:

- `position`;
- `posicoes_ganhas`;
- `points`;
- `race_time`;
- `laps`;
- `status`.

---

## 4. Pré-processamento

O pré-processamento foi incorporado a uma `Pipeline` do scikit-learn.

Para variáveis numéricas são aplicados:

1. imputação pela mediana;
2. padronização com `StandardScaler`.

Para variáveis categóricas são aplicados:

1. imputação pelo valor mais frequente;
2. codificação utilizando `OneHotEncoder`;
3. tratamento de categorias desconhecidas com `handle_unknown="ignore"`.

A utilização da Pipeline garante que os transformadores sejam ajustados somente com os dados apropriados de treinamento, reduzindo o risco de data leakage durante o pré-processamento.

---

## 5. Estratégia de treinamento, validação e teste

Foi utilizada uma separação temporal por corrida.

### 5.1 Desenvolvimento

Temporadas:

- 2018;
- 2019;
- 2021;
- 2022;
- 2023.

Total:

- **100 registros**;
- **5 corridas**;
- **5 vencedores**.

### 5.2 Teste final

Temporadas:

- 2024;
- 2025.

Total:

- **40 registros**;
- **2 corridas**;
- **2 vencedores**.

O conjunto de teste final permaneceu separado do processo de treinamento e tuning.

### 5.3 Justificativa

Uma divisão aleatória tradicional poderia colocar pilotos pertencentes à mesma corrida simultaneamente nos conjuntos de treinamento e validação.

Como os registros de uma mesma corrida compartilham condições de pista, clima, contexto competitivo e eventos, eles não devem ser considerados completamente independentes.

Por esse motivo, a validação durante o desenvolvimento utiliza agrupamento por `race_key`.

Foi utilizado:

`GroupKFold(n_splits=5)`

Dessa forma, os registros pertencentes à mesma corrida permanecem juntos em cada divisão.

---

## 6. Modelos avaliados

Foram avaliados três algoritmos de classificação:

### 6.1 Regressão Logística

Utilizada como baseline por apresentar:

- baixa complexidade;
- boa interpretabilidade;
- capacidade de produzir scores contínuos;
- referência linear para comparação.

### 6.2 Árvore de Decisão

Utilizada por:

- capturar relações não lineares;
- possuir interpretação relativamente simples;
- permitir análise de importância das features.

### 6.3 Random Forest

Utilizado por:

- combinar múltiplas árvores;
- capturar relações não lineares;
- reduzir a variância de uma única árvore;
- lidar adequadamente com interações entre diferentes features;
- fornecer medidas de importância das variáveis.

Devido ao forte desbalanceamento entre vencedores e não vencedores, os modelos foram configurados com tratamento de balanceamento de classes quando aplicável.

---

## 7. Tuning e validação

O tuning foi realizado utilizando `GridSearchCV`.

A validação utilizou `GroupKFold`, considerando `race_key` como agrupamento.

A métrica principal utilizada durante o tuning foi o **F1-score**, pois o problema apresenta forte desbalanceamento de classes.

Resultados de validação dos melhores parâmetros:

| Modelo | Melhor F1 médio na validação |
|---|---:|
| Regressão Logística | 0,5016 |
| Árvore de Decisão | 0,5000 |
| Random Forest | **0,6333** |

Os principais parâmetros selecionados para o Random Forest foram:

- `n_estimators = 300`;
- `max_depth = 3`;
- `min_samples_leaf = 1`;
- `class_weight = "balanced"`;
- `random_state = 42`.

---

## 8. Comparação dos modelos

Após o tuning, os modelos apresentaram os seguintes resultados no conjunto de desenvolvimento utilizado para comparação:

| Modelo | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|---:|
| Regressão Logística | 0,83 | 0,2273 | 1,00 | 0,3704 | 0,9116 |
| Árvore de Decisão | 0,94 | 0,4286 | 0,60 | 0,5000 | 0,7789 |
| Random Forest | **0,95** | **0,5000** | **0,80** | **0,6154** | **0,9537** |

O Random Forest apresentou o melhor equilíbrio entre F1-score e ROC-AUC entre os modelos avaliados, justificando sua seleção para a avaliação final.

A comparação de custo computacional será incorporada à matriz comparativa por meio da medição do tempo de treinamento e inferência dos modelos.

### 8.1 Matriz comparativa

| Modelo | Accuracy | Precision | Recall | F1 | ROC-AUC | Treino mediano (ms) | Inferência mediana (ms) | Interpretabilidade |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Logistic Regression | 0,8300 | 0,2273 | 1,0000 | 0,3704 | 0,9116 | 18,72 | 5,92 | Alta |
| Decision Tree | 0,9400 | 0,4286 | 0,6000 | 0,5000 | 0,7789 | **10,58** | **4,68** | Alta |
| Random Forest | **0,9500** | **0,5000** | **0,8000** | **0,6154** | **0,9537** | 584,97 | 68,72 | Média |

### 8.2 Custo computacional

O custo computacional foi medido em benchmark local utilizando os modelos com os melhores hiperparâmetros encontrados no processo de tuning.

Foram utilizadas 10 repetições por modelo sobre o conjunto de desenvolvimento, composto por 100 registros e 18 features. Para reduzir a influência de variações pontuais do ambiente de execução, a mediana dos tempos foi adotada como medida principal.

A Decision Tree apresentou o menor custo computacional, com aproximadamente 10,58 ms para treinamento e 4,68 ms para inferência. A Logistic Regression também apresentou baixo custo, com aproximadamente 18,72 ms para treinamento e 5,92 ms para inferência.

O Random Forest apresentou maior custo relativo, com aproximadamente 584,97 ms para treinamento e 68,72 ms para inferência. Esse comportamento é esperado devido à utilização de um ensemble com 300 árvores. Apesar de ser consideravelmente mais custoso que os demais modelos, seu tempo absoluto permaneceu inferior a um segundo para treinamento no dataset utilizado.

Os tempos representam medições realizadas no ambiente local do projeto e podem variar de acordo com hardware, sistema operacional, carga do computador e versões das bibliotecas. Por esse motivo, devem ser interpretados como referência comparativa entre os modelos neste ambiente, e não como benchmark universal.

### 8.3 Interpretabilidade e escolha do modelo

A Logistic Regression apresenta alta interpretabilidade, pois permite analisar a direção e magnitude dos coeficientes após o pré-processamento. A Decision Tree também apresenta alta interpretabilidade devido à possibilidade de inspecionar diretamente suas regras e decisões.

O Random Forest possui interpretabilidade relativa menor, pois sua decisão resulta da combinação de múltiplas árvores. Entretanto, permite análise de importância das features e apresentou o melhor equilíbrio entre as métricas avaliadas na comparação dos modelos tunados.

A escolha final do Random Forest foi baseada principalmente em seu F1 de 0,6154 e ROC-AUC de 0,9537 na avaliação comparativa, além de Recall de 0,8000. Embora tenha apresentado maior custo computacional e menor interpretabilidade relativa, esse custo permanece pequeno em termos absolutos para o volume atual de dados.

O custo computacional, portanto, não representou uma restrição relevante para a escolha do modelo neste projeto.

---

## 9. Avaliação final

O Random Forest selecionado foi treinado utilizando o conjunto completo de desenvolvimento e posteriormente avaliado no conjunto temporal de teste formado pelas temporadas de 2024 e 2025.

Resultados:

| Métrica | Resultado |
|---|---:|
| Accuracy | 0,95 |
| Precision | 0,00 |
| Recall | 0,00 |
| F1-score | 0,00 |
| ROC-AUC | 1,00 |

A matriz de confusão apresentou:

|  | Predito não vencedor | Predito vencedor |
|---|---:|---:|
| Real não vencedor | 38 | 0 |
| Real vencedor | 2 | 0 |

Apesar da Accuracy de 95%, o modelo não classificou nenhum piloto como vencedor utilizando o threshold padrão de 0,5.

Portanto, a Accuracy isoladamente seria uma métrica inadequada para avaliar o modelo neste problema.

O F1-score igual a zero evidencia a dificuldade da classificação binária causada pelo forte desbalanceamento e pela pequena quantidade de eventos positivos.

---

## 10. Interpretação do ROC-AUC

O ROC-AUC obtido no teste foi:

**1,00**

Esse resultado não deve ser interpretado como “100% de acerto”.

O ROC-AUC avalia a capacidade do modelo de ordenar registros positivos acima dos negativos considerando diferentes thresholds.

Como o conjunto de teste possui somente duas corridas e dois vencedores, o resultado deve ser tratado como evidência exploratória e não como demonstração de generalização robusta.

---

## 11. Avaliação por ranking

Como existe exatamente um vencedor em cada corrida, foi adicionada uma avaliação relativa por corrida.

As métricas utilizadas são:

- Top-1;
- Top-3;
- posição média do vencedor real;
- Mean Reciprocal Rank — MRR.

Resultados no conjunto de teste:

| Métrica | Resultado |
|---|---:|
| Corridas avaliadas | 2 |
| Top-1 | 2 de 2 |
| Top-3 | 2 de 2 |
| Posição média do vencedor | 1,0 |
| MRR | 1,0 |

Em 2024, Max Verstappen foi o vencedor real e recebeu o maior score do modelo dentro da corrida.

Em 2025, Lando Norris foi o vencedor real e também recebeu o maior score do modelo dentro da corrida.

Esses resultados não devem ser descritos como uma taxa comprovada de 100% de acerto, pois o conjunto de teste contém somente duas corridas.

---

## 12. Score do modelo e probabilidade

O valor retornado por `predict_proba` é armazenado como:

`score_modelo_vitoria`

O projeto evita apresentar esse valor diretamente como uma probabilidade calibrada de vitória.

O modelo utiliza balanceamento de classes e não foi submetido a um processo específico de calibração probabilística.

Consequentemente, o score é utilizado principalmente para:

- comparação relativa entre pilotos;
- ranking dentro de uma corrida;
- análise exploratória.

---

## 13. Interpretabilidade

A importância das features do Random Forest indicou como principais variáveis:

| Feature | Importância |
|---|---:|
| `ritmo_representativo_pct` | 30,38% |
| `grid` | 19,39% |
| `duracao_mediana_pit_convencional` | 15,38% |
| `voltas_disponiveis` | 9,58% |
| `voltas_stint_medio` | 5,78% |
| `voltas_analisadas` | 5,45% |

A principal variável identificada foi o ritmo representativo do piloto durante a corrida.

Entretanto, feature importance representa contribuição para o comportamento do modelo e **não deve ser interpretada como relação causal**.

---

## 14. Pipeline de inferência

O modelo final foi persistido como uma Pipeline completa utilizando `joblib`.

Artefatos:

`ml/models/random_forest_interlagos.joblib`

`ml/models/random_forest_interlagos_metadata.json`

O pipeline de inferência está implementado em:

`ml/inference/predict.py`

O processo permite:

1. carregar o modelo persistido;
2. carregar os metadados;
3. validar as features obrigatórias;
4. bloquear features associadas a leakage;
5. calcular `score_modelo_vitoria`;
6. criar ranking por corrida;
7. exportar o resultado.

O pipeline foi validado utilizando o conjunto de teste, reproduzindo os scores da avaliação final.

---

## 15. Aplicação ao contexto de Gabriel Bortoleto

Os resultados históricos foram utilizados para estruturar uma análise exploratória de cenários para Gabriel Bortoleto.

Os três fatores de maior importância utilizados no indicador simplificado são:

- ritmo representativo;
- posição de largada;
- duração mediana de pit stop.

As importâncias originais dessas três features são aproximadamente:

- ritmo: 30,38%;
- grid: 19,39%;
- pit stop: 15,38%.

Considerando somente essas três variáveis e normalizando suas importâncias relativas, os valores aproximados são:

- ritmo: 46,6%;
- grid: 29,8%;
- pit stop: 23,6%.

Para simplificar a comunicação do simulador, foram utilizados pesos arredondados:

- **45% ritmo**;
- **30% grid**;
- **25% pit stop**.

O indicador é uma **heurística de comparação de cenários**.

Ele não corresponde ao `score_modelo_vitoria` produzido diretamente pelo Random Forest e não representa uma probabilidade calibrada de vitória.

---

## 16. Limitações

As principais limitações identificadas são:

### Pequena quantidade de corridas

O dataset possui somente sete corridas válidas para modelagem.

### Poucos eventos positivos

Existem somente sete vencedores em todo o dataset.

O conjunto de teste contém apenas dois eventos positivos.

### Desbalanceamento

A vitória representa uma pequena parcela dos registros piloto-corrida.

### Features conhecidas durante a corrida

Algumas das features de maior importância, como ritmo, pit stops e stints, somente são conhecidas durante a realização da prova.

Por esse motivo, o modelo atual não deve ser apresentado como previsão pré-corrida.

### Importância não implica causalidade

As importâncias do Random Forest indicam contribuição para o modelo, e não relações causais entre as variáveis e a vitória.

---

## 17. Evolução futura — Modelo pré-corrida

Uma evolução natural do projeto é a criação de um segundo modelo utilizando exclusivamente informações disponíveis antes da largada.

Esse modelo poderia utilizar, por exemplo:

- posição de largada;
- desempenho na classificação;
- desempenho recente do piloto;
- desempenho recente da equipe;
- histórico anterior em Interlagos;
- desempenho em circuitos semelhantes;
- condições meteorológicas conhecidas ou previstas antes da corrida.

Essa abordagem permitiria separar formalmente duas finalidades:

**Modelo A — Histórico/Explicativo**

> Identificar fatores associados à vitória e avaliar o desempenho relativo observado durante a corrida.

**Modelo B — Preditivo Pré-Corrida**

> Estimar a competitividade relativa dos pilotos utilizando somente informações disponíveis antes da largada.

---

## 18. Conclusão

A aplicação de Machine Learning demonstrou que ritmo de corrida, posição de largada e execução estratégica estão entre os fatores mais relevantes na diferenciação histórica dos vencedores em Interlagos.

O Random Forest apresentou o melhor desempenho entre os algoritmos avaliados durante o processo de comparação e tuning.

Entretanto, a avaliação final também demonstrou a importância de não utilizar uma única métrica de forma isolada.

Embora a Accuracy tenha atingido 95% e o ROC-AUC tenha sido 1,00 no pequeno conjunto de teste, o F1-score igual a zero mostrou que o threshold padrão não foi capaz de identificar os vencedores como classe positiva.

A avaliação por ranking complementou essa análise e mostrou que, nas duas corridas do conjunto de teste, o vencedor real recebeu o maior score relativo do modelo.

Devido à pequena quantidade de corridas e vencedores disponíveis, esses resultados devem ser interpretados como exploratórios.

O principal valor do modelo atual está na identificação dos fatores associados à competitividade, na interpretação histórica dos resultados e no apoio à construção de cenários para Gabriel Bortoleto.

Como evolução futura, recomenda-se a construção de um segundo modelo exclusivamente pré-corrida.
