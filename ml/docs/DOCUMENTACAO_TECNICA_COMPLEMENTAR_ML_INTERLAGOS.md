# Documentação Técnica Complementar — ML Interlagos

> Este arquivo é **complementar ao `DOC_ML.docx`**. O Word é o relatório acadêmico principal; este documento registra detalhes técnicos, decisões de implementação, rastreabilidade e resultados que não precisam aparecer no relatório.

## 1. Construção do Dataset ML

A camada ML é derivada exclusivamente da Gold e não altera nenhuma tabela Gold.

Fluxo:

```text
Gold → agregações independentes → Dataset ML
```

Granularidade final: **1 piloto × 1 corrida**.

Chave lógica: `race_key + driver_key`.  
Chave técnica: `pilot_race_key`.

Para evitar fan-out, as tabelas detalhadas são agregadas antes da consolidação:

| Origem | Granularidade original | Agregação |
|---|---|---|
| `fct_voltas` | piloto × corrida × volta | piloto × corrida |
| `fct_pit_stops` | pit stop | piloto × corrida |
| `fct_stints` | piloto × corrida × stint | piloto × corrida |
| `fct_clima` | medição | corrida |

## 2. Composição do Dataset

- 140 registros;
- 7 corridas;
- 7 vitórias;
- 133 não-vitórias;
- temporadas 2018, 2019, 2021, 2022, 2023, 2024 e 2025;
- 2020 não possui GP de Interlagos no escopo utilizado.

Distribuição da classe:

```text
Vitórias      = 7
Não-vitórias  = 133
Total         = 140
```

## 3. Catálogo técnico das features

### Identificadores e contexto

`pilot_race_key`, `race_key`, `driver_key` e `team_key` são identificadores.

`season`, `round`, `race_name`, `full_name` e `constructor_name` são informações de contexto.

Eles não devem ser tratados automaticamente como features numéricas.

### Features

**Qualificação**
- `grid`

**Desempenho**
- `ritmo_representativo_pct`

**Cobertura**
- `voltas_analisadas`
- `voltas_disponiveis`
- `cobertura_ritmo_pct`
- `amostra_reduzida`

**Pit stops**
- `qtd_pit_stops`
- `duracao_mediana_pit_convencional`

**Stints e pneus**
- `qtd_stints`
- `qtd_compostos_distintos`
- `primeiro_composto`
- `composto_mais_utilizado`
- `voltas_stint_medio`

**Clima**
- `air_temp_media`
- `track_temp_media`
- `humidity_media`
- `pressure_media`
- `wind_speed_medio`
- `rainfall_ocorreu`

Ao todo: **18 features**, sendo 16 numéricas e 2 categóricas.

## 4. Regras específicas

`vitoria = position == 1`.

`position` é utilizada somente para criar o target.

`duracao_mediana_pit_convencional` considera somente stops com duração `<= 60s`.

Pit stops acima de 60 segundos permanecem preservados e não são tratados automaticamente como erro.

`composto_mais_utilizado` é o composto com maior soma de `voltas_observadas`; empates são resolvidos lexicograficamente.

`voltas_observadas` não deve ser interpretada como `tyre_life`.

Valores ausentes semanticamente válidos são preservados. Ausência de pit stop convencional, por exemplo, não significa duração igual a zero.

## 5. Features excluídas

| Feature | Motivo |
|---|---|
| `position` | usada para criar `vitoria` |
| `posicoes_ganhas` | derivada diretamente do resultado |
| `points` | resultado esportivo |
| `race_time` | desempenho final |
| `laps` | redundante para o objetivo |
| `status` | próximo do desfecho |
| `circuit_name` | constante em Interlagos |
| `date` | não necessária na primeira versão |
| `tyre_life_inicial` | fora do escopo inicial |
| `tyre_life_final` | fora do escopo inicial |

## 6. Redundância identificada na EDA

Principais correlações de Spearman:

| Variáveis | Correlação |
|---|---:|
| `qtd_pit_stops` × `qtd_stints` | 0,9966 |
| `cobertura_ritmo_pct` × `voltas_stint_medio` | 0,9025 |
| `voltas_analisadas` × `voltas_stint_medio` | 0,8520 |
| `cobertura_ritmo_pct` × `qtd_pit_stops` | -0,8316 |
| `track_temp_media` × `humidity_media` | -0,8214 |
| `voltas_analisadas` × `cobertura_ritmo_pct` | 0,8180 |
| `cobertura_ritmo_pct` × `qtd_stints` | -0,8170 |
| `voltas_analisadas` × `voltas_disponiveis` | 0,8021 |

Por isso, feature importance não deve ser interpretada como efeito causal independente.

## 7. Associações exploratórias com a vitória

| Feature | Pearson | Spearman |
|---|---:|---:|
| `ritmo_representativo_pct` | -0,3657 | -0,3198 |
| `grid` | -0,2238 | -0,2245 |
| `duracao_mediana_pit_convencional` | -0,0947 | -0,1732 |
| `voltas_disponiveis` | 0,0943 | 0,1485 |
| `voltas_analisadas` | 0,0959 | 0,1129 |
| `voltas_stint_medio` | 0,0880 | 0,0935 |
| `cobertura_ritmo_pct` | 0,0438 | 0,0484 |
| `qtd_compostos_distintos` | -0,0231 | -0,0315 |
| `qtd_stints` | 0,0152 | 0,0055 |
| `qtd_pit_stops` | 0,0105 | 0,0038 |

A interpretação é exploratória devido aos poucos casos positivos.

## 8. Separação dos dados

### Development

2018, 2019, 2021, 2022 e 2023.

- 100 registros;
- 5 corridas;
- 5 vitórias;
- 95 não-vitórias.

### Teste

2024 e 2025.

- 40 registros;
- 2 corridas;
- 2 vitórias;
- 38 não-vitórias.

Não houve sobreposição de `race_key`.

A divisão foi feita por corrida e respeitando a ordem temporal.

## 9. Pré-processamento

O pré-processamento foi realizado dentro do `Pipeline`.

Features:

```text
16 numéricas
2 categóricas
```

Numéricas:

```text
SimpleImputer(strategy="median")
StandardScaler()
```

Categóricas:

```text
SimpleImputer(strategy="most_frequent")
OneHotEncoder(handle_unknown="ignore")
```

Isso evita ajuste global das transformações antes da validação.

## 10. Modelos e resultados iniciais

Modelos:

1. Regressão Logística;
2. Árvore de Decisão;
3. Random Forest.

| Modelo | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|---:|
| Logistic Regression | 0,8400 | 0,1765 | 0,6000 | 0,2727 | 0,8674 |
| Decision Tree | 0,8800 | 0,1818 | 0,4000 | 0,2500 | 0,6526 |
| Random Forest | 0,9400 | 0,3333 | 0,2000 | 0,2500 | 0,9558 |

## 11. Validação e tuning

Foi utilizado:

```text
GroupKFold(n_splits=5)
groups = race_key
```

O tuning utilizou Grid Search e teve como critério principal o F1 médio.

### Melhor Regressão Logística

```text
C = 0.1
class_weight = balanced
F1 médio = 0,5016
```

### Melhor Árvore

```text
max_depth = 3
min_samples_leaf = 4
class_weight = balanced
F1 médio = 0,5000
```

### Melhor Random Forest

```text
n_estimators = 300
max_depth = 3
min_samples_leaf = 1
class_weight = balanced
F1 médio = 0,6333
```

Comparação após tuning:

| Modelo | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|---:|
| Logistic Regression | 0,8300 | 0,2273 | 1,0000 | 0,3704 | 0,9116 |
| Decision Tree | 0,9400 | 0,4286 | 0,6000 | 0,5000 | 0,7789 |
| Random Forest | 0,9500 | 0,5000 | 0,8000 | 0,6154 | 0,9537 |

## 12. Configuração final

Random Forest:

```text
n_estimators = 300
max_depth = 3
min_samples_leaf = 1
class_weight = balanced
random_state = 42
```

O modelo final foi treinado no Development completo e avaliado exclusivamente no teste.

## 13. Resultado detalhado do teste

| Métrica | Resultado |
|---|---:|
| Accuracy | 0,9500 |
| Precision | 0,0000 |
| Recall | 0,0000 |
| F1 | 0,0000 |
| ROC-AUC | 1,0000 |

Matriz:

```text
              Previsto
              0    1
Real  0      38    0
      1       2    0
```

Com threshold 0,5, nenhum piloto foi classificado como vencedor.

## 14. Ranking de probabilidades

| Temporada | Vencedor real | Maior probabilidade | Ranking |
|---|---|---|---:|
| 2024 | Max Verstappen | Max Verstappen | 1º |
| 2025 | Lando Norris | Lando Norris | 1º |

Probabilidades dos vencedores:

```text
2024 = 0,335007
2025 = 0,426032
```

Assim, os dois vencedores ficaram em primeiro no ranking, embora ambos tenham permanecido abaixo do threshold de 0,5.

Este resultado não deve ser descrito como previsão do vencedor com 100% de precisão.

## 15. Interpretação da ROC-AUC e F1

ROC-AUC avalia a capacidade de ordenação/separação pelas probabilidades.

F1 depende da classificação binária após o threshold.

Portanto:

```text
ROC-AUC = 1,00
F1       = 0,00
```

não é uma contradição.

O resultado mostra bom ranqueamento relativo dentro desse teste muito pequeno, mas classificação binária inadequada no threshold padrão.

## 16. Feature importance

Principais importâncias:

| Rank | Feature | Importância |
|---:|---|---:|
| 1 | `ritmo_representativo_pct` | 30,38% |
| 2 | `grid` | 19,39% |
| 3 | `duracao_mediana_pit_convencional` | 15,38% |
| 4 | `voltas_disponiveis` | 9,58% |
| 5 | `voltas_stint_medio` | 5,78% |
| 6 | `voltas_analisadas` | 5,45% |
| 7 | `composto_mais_utilizado` | 2,81% |
| 8 | `primeiro_composto` | 1,75% |
| 9 | `qtd_compostos_distintos` | 1,71% |
| 10 | `cobertura_ritmo_pct` | 1,33% |

## 17. Importância por grupo

| Rank | Grupo | Importância |
|---:|---|---:|
| 1 | Desempenho | 30,38% |
| 2 | Qualificação | 19,39% |
| 3 | Cobertura do Ritmo | 16,35% |
| 4 | Pit Stops | 16,31% |
| 5 | Stints e Pneus | 13,37% |
| 6 | Clima | 4,20% |

A importância por grupo também deve ser interpretada considerando as correlações entre variáveis.

## 18. Comparações descritivas

### Ritmo

| Grupo | Média | Mediana |
|---|---:|---:|
| Vencedores | -1,4805% | -1,1925% |
| Não-vencedores | -0,0028% | 0,0842% |

Valores negativos representam ritmo melhor que a referência comparável.

### Grid

| Grupo | Média | Mediana |
|---|---:|---:|
| Vencedores | 2,8 | 1 |
| Não-vencedores | 10,48 | 11 |

### Pit stop convencional

| Grupo | Média | Mediana |
|---|---:|---:|
| Vencedores | 22,491 s | 22,657 s |
| Não-vencedores | 23,135 s | 23,368 s |

As comparações são descritivas e não estabelecem causalidade.

## 19. Natureza do modelo

O modelo atual deve ser entendido como:

> **Análise histórica e modelagem exploratória dos fatores associados à vitória em Interlagos.**

Não é um modelo de previsão pré-corrida.

Ritmo, pit stops, stints, compostos e cobertura de voltas são informações disponíveis durante ou após a corrida.

O `grid` também é posterior à sessão de classificação.

Para previsão pré-corrida seria necessário construir outro conjunto de features exclusivamente com informações disponíveis antes da largada.

## 20. Integridade do teste

O conjunto de teste deve permanecer intocado após a avaliação final.

Não utilizar 2024–2025 para:

- alterar hiperparâmetros;
- escolher threshold;
- repetir tuning;
- adicionar/remover features;
- justificar uma nova configuração;
- afirmar generalização ampla.

Qualquer nova alteração deve ser realizada no conjunto de desenvolvimento, mantendo uma avaliação independente.

## 21. Artefatos no MinIO

### Dataset

```text
s3://f1-data-lake/ml/dataset/dataset_ml_interlagos.parquet
```

### Preparação

```text
s3://f1-data-lake/ml/prepared/model_data_base.parquet
```

### Splits

```text
s3://f1-data-lake/ml/prepared/splits/development.parquet
s3://f1-data-lake/ml/prepared/splits/test.parquet
s3://f1-data-lake/ml/prepared/splits/development_groups.csv
s3://f1-data-lake/ml/prepared/splits/test_groups.csv
```

### Resultados

```text
s3://f1-data-lake/ml/results/tuning_results.csv
s3://f1-data-lake/ml/results/tuned_model_comparison.csv
s3://f1-data-lake/ml/results/final_test_metrics.csv
s3://f1-data-lake/ml/results/final_test_predictions.csv
s3://f1-data-lake/ml/results/final_test_race_summary.csv
s3://f1-data-lake/ml/results/feature_importance.csv
s3://f1-data-lake/ml/results/feature_importance_groups.csv
s3://f1-data-lake/ml/results/winners_vs_non_winners.csv
```

### Visualizações

```text
s3://f1-data-lake/ml/visualization/
```

Arquivos:

```text
01_comparacao_modelos.png
02_matriz_confusao.png
03_curva_roc.png
04_importancia_features.png
05_ritmo_vencedores_vs_nao_vencedores.png
06_grid_vencedores_vs_nao_vencedores.png
```

## 22. O que permanece somente na documentação técnica

Este arquivo concentra detalhes que não precisam estar no Word, principalmente:

- regras de construção e granularidade;
- catálogo técnico das features;
- exclusões;
- tratamento semântico de nulos;
- correlações e redundâncias;
- resultados intermediários;
- parâmetros dos grids de tuning;
- configuração final completa;
- detalhes do ranking por corrida;
- rastreabilidade dos artefatos;
- estrutura do MinIO;
- regras para preservar o teste;
- distinção entre análise histórica e previsão pré-corrida.

## 23. Melhorias futuras

- ampliar o número de corridas;
- avaliar novas temporadas;
- testar técnicas adicionais de interpretabilidade;
- avaliar permutation importance;
- estudar alternativas para o desbalanceamento;
- construir dataset específico para previsão pré-corrida;
- utilizar validação independente para decisões de threshold;
- desenvolver pipeline de inferência, se necessário.

---

## Status

**Etapa de ML concluída para o escopo atual:**

```text
Dataset
   ✓
EDA
   ✓
Separação temporal
   ✓
Pré-processamento
   ✓
Treinamento
   ✓
Validação
   ✓
Tuning
   ✓
Modelo final
   ✓
Avaliação final
   ✓
Interpretação
   ✓
Visualizações
   ✓
```

O `DOC_ML.docx` permanece como **relatório principal** e este arquivo como **documentação técnica complementar**.
