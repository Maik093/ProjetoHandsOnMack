# Modelagem ML — Dataset de Interlagos

## 1. Objetivo

O objetivo da modelagem é identificar quais condições, características e comportamentos estão associados à vitória de um piloto no Grande Prêmio do Brasil, considerando exclusivamente as corridas realizadas no Autódromo de Interlagos.

A unidade de análise é **1 piloto × 1 corrida**.

O problema será tratado como uma classificação binária:

- `vitoria = True`: piloto terminou a corrida na posição 1;
- `vitoria = False`: piloto não terminou na posição 1.

Nesta etapa, o objetivo é analítico e explicativo. As variáveis de desempenho de corrida podem, portanto, ser utilizadas para investigar características associadas às vitórias. Caso futuramente o objetivo seja transformado em uma previsão **pré-corrida**, será necessária uma nova avaliação de disponibilidade temporal das features para evitar vazamento de informação.

---

## 2. Escopo do dataset

O dataset utilizado na modelagem é:

```text
ml/dataset/dataset_ml_interlagos.parquet
```

O dataset possui granularidade de piloto × corrida e considera exclusivamente o período de **2018 a 2025**, conforme a definição do Dataset ML Enriquecido.

A Gold permanece como camada de origem e não deve ser alterada durante a preparação ou modelagem.

---

## 3. Target

A variável alvo é:

```text
vitoria
```

Derivação:

```text
vitoria = position == 1
```

A coluna `position` é utilizada somente para derivar o target e **não deve ser utilizada como feature**.

Distribuição esperada no dataset atual:

- 140 registros;
- 7 vitórias;
- 133 não vitórias;
- 5% de registros positivos.

A baixa quantidade de exemplos positivos é uma limitação importante e deve ser considerada tanto na validação quanto na interpretação dos resultados.

---

## 4. Features selecionadas

As seguintes variáveis formam o conjunto inicial de features da modelagem.

### 4.1 Desempenho e posição

| Feature | Descrição |
|---|---|
| `grid` | Posição de largada do piloto |
| `ritmo_representativo_pct` | Ritmo representativo do piloto na corrida, calculado segundo a metodologia definida na EDA |
| `voltas_stint_medio` | Média de voltas observadas por stint |

O `ritmo_representativo_pct` é uma das principais variáveis analíticas do dataset e deve ser interpretado conforme sua definição na EDA: valores negativos indicam ritmo melhor que a referência comparável e valores positivos indicam ritmo pior.

### 4.2 Estratégia de pit stops

| Feature | Descrição |
|---|---|
| `qtd_pit_stops` | Quantidade de pit stops do piloto |
| `duracao_mediana_pit_convencional` | Mediana da duração dos pit stops convencionais |

`qtd_stints` não será utilizada na primeira versão por apresentar redundância extrema com `qtd_pit_stops`.

### 4.3 Pneus e stints

| Feature | Descrição |
|---|---|
| `qtd_compostos_distintos` | Quantidade de compostos distintos utilizados |
| `primeiro_composto` | Composto utilizado no primeiro stint |
| `composto_mais_utilizado` | Composto com maior quantidade de voltas observadas |
| `voltas_stint_medio` | Média de voltas observadas por stint |

As métricas de duração dos stints utilizam **voltas observadas**, não `tyre_life`.

### 4.4 Condições climáticas

As variáveis climáticas são agregadas no nível da corrida e posteriormente associadas aos registros piloto × corrida.

| Feature | Descrição |
|---|---|
| `air_temp_media` | Temperatura média do ar na corrida |
| `track_temp_media` | Temperatura média da pista na corrida |
| `humidity_media` | Umidade média na corrida |
| `pressure_media` | Pressão média na corrida |
| `wind_speed_medio` | Velocidade média do vento na corrida |
| `rainfall_ocorreu` | Indicador de ocorrência de chuva |

As variáveis climáticas representam contexto da corrida. Como o mesmo valor pode ser repetido para os pilotos de uma mesma corrida, sua interpretação deve considerar essa característica.

Não será realizada uma associação artificial entre cada medição climática e cada volta do piloto, pois a EDA não estabeleceu uma correspondência temporal confiável entre as fontes.

---

## 5. Features de controle

As seguintes variáveis permanecem no dataset, mas não farão parte do primeiro conjunto de features:

- `voltas_analisadas`
- `voltas_disponiveis`
- `cobertura_ritmo_pct`
- `amostra_reduzida`

Essas variáveis são importantes para avaliar a qualidade e a cobertura das observações de ritmo, mas podem introduzir redundância ou representar características da disponibilidade dos dados em vez de fatores diretamente relacionados à vitória.

Elas poderão ser avaliadas posteriormente em uma análise de sensibilidade.

---

## 6. Variáveis excluídas

As seguintes colunas não serão utilizadas como features na primeira versão.

### 6.1 Variáveis diretamente relacionadas ao resultado

- `position`
- `posicoes_ganhas`
- `points`
- `race_time`
- `laps`
- `status`

`position` é utilizada exclusivamente para derivar `vitoria`.

`posicoes_ganhas` também não será utilizada porque é calculada a partir de `grid` e `position`, ficando diretamente relacionada ao resultado final.

`points`, `race_time`, `laps` e `status` representam informações do resultado ou do encerramento da corrida e não fazem parte do conjunto inicial de explicadores.

### 6.2 Identificadores e contexto

Não serão utilizados como features numéricas:

- `pilot_race_key`
- `race_key`
- `driver_key`
- `team_key`
- `season`
- `round`
- `race_name`
- `full_name`
- `constructor_name`
- `circuit_name`

Essas variáveis permanecem importantes para rastreabilidade, segmentação, validação e interpretação dos resultados.

`circuit_name` é constante dentro do escopo de Interlagos e, portanto, não acrescenta informação discriminativa ao modelo.

---

## 7. Redundância entre variáveis

A EDA específica do dataset ML identificou algumas correlações elevadas entre features.

Principais casos:

| Feature A | Feature B | Spearman |
|---|---|---:|
| `qtd_pit_stops` | `qtd_stints` | 0,997 |
| `cobertura_ritmo_pct` | `voltas_stint_medio` | 0,903 |
| `voltas_analisadas` | `voltas_stint_medio` | 0,852 |
| `cobertura_ritmo_pct` | `qtd_pit_stops` | -0,832 |
| `track_temp_media` | `humidity_media` | -0,821 |
| `voltas_analisadas` | `cobertura_ritmo_pct` | 0,818 |
| `cobertura_ritmo_pct` | `qtd_stints` | -0,817 |
| `voltas_analisadas` | `voltas_disponiveis` | 0,802 |

### Decisão

`qtd_stints` será excluída da primeira versão, pois apresenta correlação praticamente perfeita com `qtd_pit_stops`.

As demais redundâncias não resultarão automaticamente na exclusão das variáveis. A decisão poderá ser revisada durante a modelagem, especialmente caso prejudique a interpretabilidade ou estabilidade dos modelos.

---

## 8. Tratamento de valores nulos

A presença de valores nulos deve ser preservada conforme o significado da variável.

Principais ocorrências identificadas na EDA:

- `duracao_mediana_pit_convencional`: 14 nulos (10,00%);
- `ritmo_representativo_pct`: 8 nulos (5,71%);
- `cobertura_ritmo_pct`: 8 nulos (5,71%);
- `composto_mais_utilizado`: 3 nulos (2,14%);
- `primeiro_composto`: 3 nulos (2,14%);
- `voltas_stint_medio`: 3 nulos (2,14%).

Não será aplicada uma imputação genérica de todos os valores nulos para zero.

Por exemplo, a ausência de `duracao_mediana_pit_convencional` pode representar a inexistência de um pit stop convencional. Essa situação é diferente de uma duração real igual a zero.

A estratégia de tratamento será aplicada no pipeline de preparação dos dados e documentada antes do treinamento.

---

## 9. Variáveis categóricas

As variáveis categóricas inicialmente selecionadas são:

- `primeiro_composto`
- `composto_mais_utilizado`

Essas variáveis deverão ser transformadas para representação numérica antes do treinamento.

A estratégia inicial deverá preservar as categorias observadas e evitar a criação de uma ordem artificial entre compostos.

`rainfall_ocorreu` é uma variável booleana e poderá ser convertida diretamente para representação binária.

---

## 10. Construção de X e y

A separação para modelagem será:

```text
X = conjunto de features selecionadas
y = vitoria
```

A coluna `vitoria` não poderá permanecer em `X`.

Também não deverão fazer parte de `X` as variáveis utilizadas diretamente para construir o target.

A preparação deverá ocorrer de forma reprodutível, mantendo separadas as etapas de transformação dos dados e treinamento dos modelos.

---

## 11. Estratégia de validação

A unidade lógica do dataset é piloto × corrida, porém os registros de uma mesma corrida compartilham contexto.

Isso é particularmente relevante para as variáveis climáticas, que são características da corrida e aparecem repetidas para os pilotos participantes.

Por esse motivo, não deverá ser utilizada uma divisão aleatória simples dos registros.

A variável:

```text
race_key
```

será utilizada como **grupo de validação**.

O objetivo é garantir que os pilotos de uma mesma corrida não sejam artificialmente distribuídos entre treinamento e validação.

Exemplo conceitual:

```text
CORRIDA A → treino
CORRIDA B → treino
CORRIDA C → validação
```

e não:

```text
Piloto 1 da corrida A → treino
Piloto 2 da corrida A → validação
```

Como existem apenas 7 corridas com vitória no período analisado, qualquer avaliação terá elevada variabilidade. Os resultados deverão ser interpretados como evidência exploratória e não como uma estimativa robusta de desempenho em produção.

---

## 12. Cuidados com desbalanceamento

O target apresenta:

```text
Não vitória: 133
Vitória:       7
```

Portanto, existe forte desbalanceamento de classes.

A acurácia isoladamente não será considerada uma métrica suficiente.

Na etapa de modelagem deverão ser avaliadas métricas adequadas ao problema de classificação desbalanceada e, principalmente, a capacidade do modelo de identificar a classe positiva.

O pequeno número absoluto de vitórias também limita a capacidade de generalização e aumenta a variabilidade das métricas.

---

## 13. Risco de vazamento de informação

O conceito de vazamento deve ser avaliado de acordo com o objetivo da análise.

### Objetivo atual

O objetivo atual é identificar características **associadas às vitórias históricas**.

Por isso, variáveis de desempenho de corrida, como:

- `ritmo_representativo_pct`;
- `qtd_pit_stops`;
- `qtd_stints` ou seus substitutos;
- características dos pneus;
- clima;

podem ser utilizadas na análise.

### Possível objetivo futuro: previsão pré-corrida

Caso o projeto passe a responder:

> "Antes da corrida, qual piloto tem maior probabilidade de vencer?"

será necessário revisar todas as features e manter somente informações disponíveis antes do início da corrida.

Portanto, a definição atual não deve ser interpretada automaticamente como um dataset de previsão pré-corrida.

---

## 14. Limitações

As principais limitações conhecidas são:

1. Apenas 7 vitórias no período analisado.
2. Forte desbalanceamento entre classes.
3. Os pilotos da mesma corrida compartilham contexto.
4. As variáveis climáticas são características da corrida e são repetidas entre pilotos.
5. Algumas features possuem valores nulos.
6. Existem redundâncias entre variáveis.
7. Correlações exploratórias não demonstram causalidade.
8. O dataset foi construído para análise histórica de condições associadas à vitória, não para previsão pré-corrida.

Essas limitações deverão acompanhar a interpretação dos resultados da modelagem.

---

## 15. Próxima etapa

Com o contrato metodológico definido, a próxima etapa será criar o pipeline de preparação dos dados para modelagem.

A sequência será:

```text
Dataset ML
    ↓
Seleção das features
    ↓
Tratamento dos nulos
    ↓
Codificação das categóricas
    ↓
Separação X / y
    ↓
Validação agrupada por race_key
    ↓
Baseline
    ↓
Treinamento dos modelos
    ↓
Avaliação
    ↓
Interpretação dos resultados
```

Nesta etapa não serão alteradas as tabelas Gold nem o dataset ML original.

O pipeline de preparação deverá produzir uma entrada reprodutível para os modelos e preservar `race_key` para a estratégia de validação por grupos.
