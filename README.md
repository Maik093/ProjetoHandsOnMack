#Projeto Hands On Formula 1
Repositório para entrega do projeto de hands on do MBA de Engenharia de Dados do Mackenzie.

--------------------------------------------------------------------------------------------------------------------------------------------------------------------

*Integrantes:*

Gabriel Augusto Martins - RA: 10734520

Maik Moreno Souza - RA: 10735784

Rodrigo Menegatti Morante - RA: 10739705

Vinicius Lucas Trentino - RA: 10739016

--------------------------------------------------------------------------------------------------------------------------------------------------------------------

A partir de uma base histórica de resultados da Fórmula 1, buscamos identificar quais características de desempenho, estratégia e contexto estão mais associadas à vitória de um piloto no Grande Prêmio de São Paulo, em Interlagos.

O objetivo é compreender, com base em dados, quais fatores historicamente diferenciam pilotos vencedores dos demais competidores e utilizar essas evidências para analisar a competitividade de Gabriel Bortoleto em diferentes cenários de corrida.


--------------------------------------------------------------------------------------------------------------------------------------------------------------------

A Fórmula 1 é uma competição caracterizada por elevada complexidade e por margens reduzidas de desempenho entre pilotos e equipes. O resultado de uma corrida é influenciado por diversos fatores que ocorrem antes e durante a prova, como posição de largada, ritmo de corrida, estratégia adotada, condições climáticas, desgaste dos pneus, paradas nos boxes e eventos inesperados na pista.

No Grande Prêmio de São Paulo, realizado no Autódromo de Interlagos, essa complexidade é potencializada pelas características do circuito e pela possibilidade de variações nas condições de corrida. Como consequência, decisões tomadas ao longo de um fim de semana podem produzir impactos significativos no desempenho e na posição final de um piloto.

Nesse contexto, Gabriel Bortoleto enfrenta o desafio de competir em um cenário no qual seu desempenho não depende apenas de sua capacidade individual, mas também da combinação de diferentes fatores relacionados à corrida, ao ambiente e à estratégia da equipe.

Entretanto, analisar isoladamente indicadores como posição de largada, tempo de volta ou resultado final não permite compreender adequadamente quais fatores possuem maior relação com um bom desempenho em Interlagos. A interação entre essas variáveis torna difícil identificar quais condições historicamente favoreceram ganhos ou perdas de desempenho durante a prova.

Dessa forma, o problema central deste projeto está na dificuldade de compreender quais fatores possuem maior influência sobre o desempenho de um piloto no Grande Prêmio de São Paulo e como a combinação desses fatores pode afetar a competitividade de Gabriel Bortoleto em Interlagos.

--------------------------------------------------------------------------------------------------------------------------------------------------------------------
Coleta dos dados

1.Dataset bruto(raw data)

Foram coletados dados reais de Fórmula 1 em formato JSON, armazenados na camada Bronze do MinIO.

As bases utilizadas são:

Resultados das corridas: 2015–2025
Pit Stops: 2015–2025
Voltas: 2015–2025
Calendário: 2015–2025
Clima: 2018–2025
Pneus: 2018–2025


2.Lista/documentação das fonte dos dados

Fontes e requisições

| Dataset    | Fonte          | Requisição / Endpoint                                            | Período   |
| ---------- | -------------- | ---------------------------------------------------------------- | --------- |
| Resultados | Jolpica F1 API | `/ergast/f1/{ano}/{round}/results/`                              | 2015–2025 |
| Pit Stops  | Jolpica F1 API | `/ergast/f1/{ano}/{round}/pitstops/`                             | 2015–2025 |
| Voltas     | Jolpica F1 API | `/ergast/f1/{ano}/{round}/laps/`                                 | 2015–2025 |
| Calendário | Jolpica F1 API | `/ergast/f1/{ano}.json`                                          | 2015–2025 |
| Clima      | FastF1         | `get_session(ano, "São Paulo", sessão)` → `session.weather_data` | 2018–2025 |
| Pneus      | FastF1         | `get_session(ano, "São Paulo", sessão)` → `session.laps`         | 2018–2025 |

### Jolpica F1 API

Os dados de resultados, pit stops, voltas e calendário são coletados
por meio de requisições HTTP à Jolpica F1 API, utilizando os endpoints
correspondentes a cada dataset.

### FastF1

Os dados de clima e pneus são obtidos por meio da biblioteca FastF1.
A sessão do Grande Prêmio de São Paulo é carregada e os dados de
`weather_data` e `laps` são extraídos conforme o dataset.


3.Dicionário de dados (data dictionary)

Resultados

| Campo                     | Tipo    | Descrição                                        |
| ------------------------- | ------- | ------------------------------------------------ |
| `season`                  | INTEGER | Temporada da Fórmula 1                           |
| `round`                   | INTEGER | Número da etapa no campeonato                    |
| `race_name`               | VARCHAR | Nome do Grande Prêmio                            |
| `race_date`               | DATE    | Data da corrida                                  |
| `race_time`               | VARCHAR | Horário programado da corrida                    |
| `race_time_millis`        | BIGINT  | Horário da corrida convertido para milissegundos |
| `race_url`                | VARCHAR | URL de referência da corrida                     |
| `circuit_id`              | VARCHAR | Identificador do circuito                        |
| `circuit_name`            | VARCHAR | Nome do circuito                                 |
| `circuit_url`             | VARCHAR | URL de referência do circuito                    |
| `circuit_lat`             | DOUBLE  | Latitude do circuito                             |
| `circuit_long`            | DOUBLE  | Longitude do circuito                            |
| `circuit_locality`        | VARCHAR | Cidade/localidade do circuito                    |
| `circuit_country`         | VARCHAR | País do circuito                                 |
| `driver_id`               | VARCHAR | Identificador do piloto                          |
| `driver_number`           | INTEGER | Número do piloto                                 |
| `driver_code`             | VARCHAR | Código de três letras do piloto                  |
| `constructor_id`          | VARCHAR | Identificador da equipe                          |
| `constructor_name`        | VARCHAR | Nome da equipe                                   |
| `position`                | INTEGER | Posição final do piloto                          |
| `points`                  | DOUBLE  | Pontos obtidos na corrida                        |
| `grid`                    | INTEGER | Posição de largada                               |
| `laps`                    | INTEGER | Número de voltas completadas                     |
| `status`                  | VARCHAR | Status final do piloto na corrida                |
| `race_time_millis`        | BIGINT  | Tempo de corrida convertido para milissegundos   |
| `fastest_lap`             | INTEGER | Número da volta mais rápida                      |
| `fastest_lap_time`        | VARCHAR | Tempo da volta mais rápida                       |
| `fastest_lap_time_millis` | BIGINT  | Tempo da volta mais rápida em milissegundos      |
| `fastest_lap_rank`        | INTEGER | Classificação da volta mais rápida               |
| `average_speed`           | DOUBLE  | Velocidade média da volta mais rápida            |
| `source_url`              | VARCHAR | URL da fonte dos dados                           |


Pit Stops

| Campo              | Tipo    | Descrição                             |
| ------------------ | ------- | ------------------------------------- |
| `season`           | INTEGER | Temporada                             |
| `round`            | INTEGER | Número da etapa                       |
| `race_name`        | VARCHAR | Nome do Grande Prêmio                 |
| `race_date`        | DATE    | Data da corrida                       |
| `race_time`        | VARCHAR | Horário da corrida                    |
| `race_time_millis` | BIGINT  | Horário convertido para milissegundos |
| `race_url`         | VARCHAR | URL da corrida                        |
| `circuit_id`       | VARCHAR | Identificador do circuito             |
| `circuit_name`     | VARCHAR | Nome do circuito                      |
| `circuit_url`      | VARCHAR | URL do circuito                       |
| `circuit_lat`      | DOUBLE  | Latitude                              |
| `circuit_long`     | DOUBLE  | Longitude                             |
| `circuit_locality` | VARCHAR | Localidade                            |
| `circuit_country`  | VARCHAR | País                                  |
| `driver_id`        | VARCHAR | Identificador do piloto               |
| `lap`              | INTEGER | Volta em que ocorreu o pit stop       |
| `stop`             | INTEGER | Número do pit stop do piloto          |
| `pit_stop_time`    | TIME    | Horário em que ocorreu a parada       |
| `duration`         | DOUBLE  | Duração da parada em segundos         |
| `duration_millis`  | BIGINT  | Duração da parada em milissegundos    |

Calendário

| Campo                  | Tipo    | Descrição                             |
| ---------------------- | ------- | ------------------------------------- |
| `season`               | INTEGER | Temporada                             |
| `round`                | INTEGER | Número da etapa                       |
| `race_name`            | VARCHAR | Nome do Grande Prêmio                 |
| `race_date`            | DATE    | Data da corrida                       |
| `race_time`            | VARCHAR | Horário da corrida                    |
| `race_time_millis`     | BIGINT  | Horário convertido para milissegundos |
| `race_url`             | VARCHAR | URL da corrida                        |
| `circuit_id`           | VARCHAR | Identificador do circuito             |
| `circuit_name`         | VARCHAR | Nome do circuito                      |
| `circuit_url`          | VARCHAR | URL do circuito                       |
| `circuit_lat`          | DOUBLE  | Latitude                              |
| `circuit_long`         | DOUBLE  | Longitude                             |
| `circuit_locality`     | VARCHAR | Localidade                            |
| `circuit_country`      | VARCHAR | País                                  |
| `first_practice_date`  | DATE    | Data do primeiro treino               |
| `second_practice_date` | DATE    | Data do segundo treino                |
| `third_practice_date`  | DATE    | Data do terceiro treino               |
| `qualifying_date`      | DATE    | Data da classificação                 |
| `source_url`           | VARCHAR | URL da fonte                          |

Voltas

| Campo              | Tipo    | Descrição                       |
| ------------------ | ------- | ------------------------------- |
| `season`           | INTEGER | Temporada                       |
| `round`            | INTEGER | Número da etapa                 |
| `race_name`        | VARCHAR | Nome do Grande Prêmio           |
| `race_date`        | DATE    | Data da corrida                 |
| `race_time`        | VARCHAR | Horário da corrida              |
| `race_time_millis` | BIGINT  | Horário em milissegundos        |
| `total_laps`       | INTEGER | Total de voltas da corrida      |
| `circuit_id`       | VARCHAR | Identificador do circuito       |
| `circuit_name`     | VARCHAR | Nome do circuito                |
| `circuit_url`      | VARCHAR | URL do circuito                 |
| `circuit_lat`      | DOUBLE  | Latitude                        |
| `circuit_long`     | DOUBLE  | Longitude                       |
| `circuit_locality` | VARCHAR | Localidade                      |
| `circuit_country`  | VARCHAR | País                            |
| `lap`              | INTEGER | Número da volta                 |
| `driver_id`        | VARCHAR | Identificador do piloto         |
| `lap_time`         | VARCHAR | Tempo original da volta         |
| `position`         | INTEGER | Posição do piloto na volta      |
| `lap_time_seconds` | DOUBLE  | Tempo da volta em segundos      |
| `lap_time_millis`  | BIGINT  | Tempo da volta em milissegundos |

Clima

| Campo                  | Tipo    | Descrição                         |
| ---------------------- | ------- | --------------------------------- |
| `season`               | INTEGER | Temporada                         |
| `grand_prix`           | VARCHAR | Grande Prêmio                     |
| `circuit`              | VARCHAR | Circuito                          |
| `session`              | VARCHAR | Identificador da sessão           |
| `session_name`         | VARCHAR | Nome da sessão                    |
| `event_name`           | VARCHAR | Nome do evento                    |
| `location`             | VARCHAR | Localização                       |
| `event_date`           | DATE    | Data do evento                    |
| `weather_time_seconds` | DOUBLE  | Tempo da medição em segundos      |
| `weather_time_millis`  | BIGINT  | Tempo da medição em milissegundos |
| `air_temp`             | DOUBLE  | Temperatura do ar                 |
| `humidity`             | DOUBLE  | Umidade                           |
| `pressure`             | DOUBLE  | Pressão atmosférica               |
| `rainfall`             | BOOLEAN | Indicador de chuva                |
| `track_temp`           | DOUBLE  | Temperatura da pista              |
| `wind_direction`       | INTEGER | Direção do vento                  |
| `wind_speed`           | DOUBLE  | Velocidade do vento               |

Pneus

| Campo           | Tipo    | Descrição                 |
| --------------- | ------- | ------------------------- |
| `season`        | INTEGER | Temporada                 |
| `grand_prix`    | VARCHAR | Grande Prêmio             |
| `circuit`       | VARCHAR | Circuito                  |
| `session`       | VARCHAR | Sessão                    |
| `session_name`  | VARCHAR | Nome da sessão            |
| `event_name`    | VARCHAR | Nome do evento            |
| `location`      | VARCHAR | Localização               |
| `event_date`    | DATE    | Data do evento            |
| `driver_id`     | VARCHAR | Identificador do piloto   |
| `driver_number` | INTEGER | Número do piloto          |
| `lap_number`    | INTEGER | Número da volta           |
| `stint`         | INTEGER | Número do stint           |
| `compound`      | VARCHAR | Composto do pneu          |
| `tyre_life`     | INTEGER | Idade do pneu em voltas   |
| `fresh_tyre`    | BOOLEAN | Indica se o pneu era novo |

Scripts e processos de coleta

A coleta dos dados é realizada por scripts Python responsáveis por consultar as fontes de dados, processar as respostas e armazená-las inicialmente na camada Bronze do Data Lake.

O processo segue o fluxo:

Fonte de dados → Python → MinIO (Bronze)

Os scripts realizam as seguintes etapas:

Definição do período e dos parâmetros de coleta;
Consulta às fontes de dados;
Recebimento dos dados em formato JSON;
Validação da resposta da fonte;
Organização dos dados coletados;
Armazenamento do JSON bruto no MinIO, preservando os dados originais para posterior processamento.

Para os dados provenientes da Jolpica F1 API, os scripts realizam requisições HTTP aos endpoints correspondentes a cada dataset.

Para os dados de clima e pneus, é utilizada a biblioteca FastF1, que permite carregar as sessões dos eventos e extrair os dados de weather_data e laps.

Tecnologias utilizadas
Python — execução dos scripts de ingestão;
Requests — requisições HTTP à API;
FastF1 — coleta dos dados de sessões, clima e pneus;
Boto3 — comunicação com o armazenamento S3-compatible;
MinIO — armazenamento dos dados na camada Bronze;
JSON — formato dos dados brutos.
Organização da camada Bronze

Os dados são armazenados no MinIO de forma organizada por dataset e temporada, permitindo que os arquivos brutos sejam posteriormente utilizados pelos processos de transformação da camada Silver.

Princípio utilizado: a camada Bronze mantém os dados coletados o mais próximo possível do formato disponibilizado pela fonte, enquanto as conversões de tipos, padronizações e demais tratamentos são realizados posteriormente na camada Silver.


Critérios de seleção dos dados

Foram selecionados dados relevantes para análise do desempenho nas corridas de Fórmula 1, priorizando:

Fontes públicas e confiáveis, como a Jolpica F1 API e a biblioteca FastF1;
Qualidade e estrutura dos dados;
Possibilidade de integração entre os datasets;
Relevância para o projeto;
Período histórico disponível.

Os datasets selecionados abrangem resultados, voltas, pit stops, calendário, clima e pneus.


### Pré-processamento

Abordagens utilizadas:

Arquitetura Medallion: dados brutos mantidos na camada Bronze e tratados na camada Silver.
ELT: os dados são primeiro armazenados no MinIO e posteriormente transformados utilizando DuckDB.
Padronização e tipagem: conversão de tipos, TRIM() dos campos textuais e criação de campos derivados, como tempos em segundos e milissegundos.
Validação de qualidade: verificação de duplicidades utilizando chaves lógicas específicas para cada dataset.
PyArrow: utilizado para registrar os dados no DuckDB e gerar as tabelas processadas em parquet.

Justificativa:

A abordagem foi escolhida para preservar os dados originais na Bronze, permitindo rastreabilidade e reprocessamento, enquanto a Silver concentra a padronização, tipagem e validação dos dados para facilitar sua integração e utilização nas análises.

## Como executar

### 1. Clonar o repositório

```bash
git clone https://github.com/Maik093/ProjetoHandsOnMack.git
cd ProjetoHandsOnMack
```

### 2. Criar o ambiente

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Instalar requirements

```bash
pip install -r requirements.txt
```

### 4. Subir Docker

```bash
docker compose up -d
docker ps
```

### 5. Executar o pipeline

Os scripts devem ser executados na seguinte ordem:

**Ingestão → Bronze → Pré-processamento → Silver**

#### Scripts de ingestão

```powershell
python ingestao/jolpica/ingerir_calendario.py

python ingestao/jolpica/ingerir_resultado.py

python ingestao/jolpica/ingerir_voltas.py

python ingestao/jolpica/ingerir_pit_stops.py

python ingestao/fastf1/ingerir_clima.py

python ingestao/fastf1/ingerir_pneus.py
```

#### Scripts de pré-processamento

```powershell
python pre_processamento/silver_calendario.py

python pre_processamento/silver_resultados.py

python pre_processamento/silver_voltas.py

python pre_processamento/silver_pit_stops.py

python pre_processamento/silver_clima.py

python pre_processamento/silver_pneus.py

python pre_processamento/silver_consolidar_arquivos.py

python pre_processamento/silver_driver_mapping.py
```

Ao final dessa etapa, os dados tratados estarão disponíveis na camada Silver.

### 7. Executar a análise exploratória (EDA)

O projeto possui um notebook de Análise Exploratória de Dados (EDA), responsável por analisar os dados disponibilizados na camada Silver.

O EDA contempla análises relacionadas a:

qualidade e integridade dos dados;
resultados das corridas;
posição de largada e posição final;
ritmo de corrida;
pit stops;
pneus e stints;
condições climáticas;
análises combinadas;
análises estatísticas;
principais insights e conclusões.

Para iniciar o Jupyter Notebook:
```
jupyter notebook
```
notebooks/eda_f1_vfinal.ipynb


Importante: o notebook deve ser executado após a conclusão da ingestão e do pré-processamento, pois as análises utilizam os dados disponibilizados na camada Silver.

8. Configurar a aplicação Streamlit

A aplicação Streamlit utiliza os dados da camada Silver para disponibilizar uma interface interativa para exploração das análises.

Antes de executar a aplicação, crie o arquivo:
```
.streamlit/secrets.toml
```
Configure as informações de acesso ao MinIO:
```
[minio]
endpoint = "localhost:9000"
access_key = "admin"
secret_key = "minioadmin123"
use_ssl = false
```
9. Executar a aplicação Streamlit

Com o MinIO em execução e os dados disponíveis na camada Silver:
```
streamlit run streamlit/app.py
```


### 8. Construir a camada Gold

Após a conclusão da Silver, executar o processo de construção da camada Gold.

A documentação detalhada da modelagem da camada Gold está disponível em:

```text
gold/docs/MODELAGEM_GOLD.md
```

Executar:

```powershell
python gold/scripts/build_gold.py
```

### 9. Validar a camada Gold

Após a construção das tabelas Gold, executar as validações:

```powershell
python gold/scripts/validate_gold.py
pytest gold/tests -v
```

### 10. Construir o dataset de Machine Learning

Após a conclusão e validação da Gold, executar a construção do dataset utilizado na etapa de Machine Learning.

As documentações específicas de ML estão disponíveis na pasta:

```text
ml/docs/
```

Executar:

```powershell
python ml/feature_engineering/build_dataset_ml.py
```

### 11. Validar o dataset de Machine Learning

Após a construção do dataset ML:

```powershell
python ml/feature_engineering/valida_dataset_ml.py
```

### 12. Executar a EDA do dataset de Machine Learning

A EDA específica do dataset de ML deve ser executada antes da preparação dos dados para treinamento:

```powershell
python ml/feature_engineering/eda_dataset_ml.py
```

Essa etapa avalia a distribuição do target, associações entre as features, valores ausentes e possíveis redundâncias entre variáveis.

### 13. Preparar os dados para modelagem

Após a EDA do dataset ML:

```powershell
python ml/feature_engineering/prepare_model_data.py
```

### 14. Separar desenvolvimento e teste

A separação dos dados é realizada por corrida, mantendo as corridas do conjunto de teste isoladas das corridas utilizadas no desenvolvimento:

```powershell
python ml/modeling/split_data.py
```

### 15. Treinar os modelos iniciais

Executar o treinamento dos modelos utilizados na comparação inicial:

```powershell
python ml/modeling/train_models.py
```

### 16. Avaliar os modelos iniciais

Após o treinamento:

```powershell
python ml/modeling/evaluate_initial.py
```

### 17. Realizar o tuning dos modelos

Executar a etapa de otimização dos hiperparâmetros:

```powershell
python ml/modeling/tune_models.py
```

### 18. Avaliar o modelo final

Após o tuning, realizar a avaliação final utilizando o conjunto de teste isolado:

```powershell
python ml/modeling/evaluate_final.py
```

A avaliação final utiliza exclusivamente as temporadas de 2024 e 2025 como conjunto de teste, preservando a separação temporal em relação ao desenvolvimento do modelo.

Além das métricas tradicionais de classificação — Accuracy, Precision, Recall, F1-score e ROC-AUC — o projeto também avalia a capacidade do modelo de ordenar os pilotos dentro de cada corrida por meio das métricas Top-1, Top-3, posição média do vencedor e Mean Reciprocal Rank (MRR).

No teste final, o Random Forest apresentou Accuracy de 95% e ROC-AUC de 1,0. Entretanto, com o threshold padrão de 0,5, nenhum dos dois vencedores foi classificado na classe positiva, resultando em Precision, Recall e F1-score iguais a zero.

Esse resultado evidencia a importância de não interpretar a Accuracy isoladamente em um problema fortemente desbalanceado.

Na perspectiva de ranking, o vencedor real ocupou a primeira posição do score do modelo nas duas corridas reservadas para teste:

- 2024: Max Verstappen;
- 2025: Lando Norris.

Esse resultado corresponde a 2 acertos em 2 corridas de teste e deve ser interpretado com cautela devido ao tamanho reduzido da amostra. Não representa evidência de 100% de capacidade preditiva ou de generalização para novas corridas.

O valor produzido por `predict_proba` é apresentado no projeto como `score_modelo_vitoria`. O score é utilizado para comparação e ordenação dos pilotos e não deve ser interpretado como probabilidade calibrada de vitória.

### 19. Interpretar o modelo

Após a avaliação final, executar a interpretação do modelo para identificar os principais fatores associados à vitória:

```powershell
python ml/modeling/interpret_model.py
```

```powershell
python teste_stints.py
```

### 20. Pipeline de inferência

Após a avaliação final, o pipeline completo de Machine Learning é persistido para permitir sua reutilização sem necessidade de novo treinamento.

Artefatos:

```text
ml/models/random_forest_interlagos.joblib
ml/models/random_forest_interlagos_metadata.json
```

O arquivo `.joblib` contém a Pipeline completa do scikit-learn, incluindo pré-processamento e Random Forest treinado. Dessa forma, as mesmas transformações utilizadas no treinamento são reutilizadas durante a inferência.

A metadata registra versão, features utilizadas, temporadas de desenvolvimento e teste, hiperparâmetros, métricas, ambiente e limitações conhecidas.

A inferência em novos arquivos CSV ou Parquet pode ser executada por:

```powershell
python ml/inference/predict.py --input <arquivo_entrada> --output <arquivo_saida>
```

O pipeline realiza:

1. carregamento do modelo e da metadata;
2. validação das features de entrada;
3. bloqueio de variáveis identificadas como risco de data leakage;
4. aplicação do pipeline treinado;
5. geração do `score_modelo_vitoria`;
6. ranking dos pilotos dentro de cada corrida, quando as chaves necessárias estão disponíveis.

A reprodutibilidade do artefato persistido foi validada utilizando os 40 registros do conjunto de teste. Os scores reproduzidos pelo pipeline de inferência foram equivalentes aos scores gerados na avaliação final, considerando tolerância numérica de ponto flutuante.

### 21. Visualização da etapa de Machine Learning

A aplicação Streamlit foi ampliada com duas páginas específicas para a etapa de Machine Learning.

#### Machine Learning

```text
streamlit/pages/11_machine_learning.py
```

Apresenta:

- estratégia de divisão temporal;
- comparação dos modelos;
- métricas finais de classificação;
- matriz de confusão;
- curva ROC;
- avaliação por ranking;
- resultados das corridas de teste;
- importância das features;
- limitações e interpretação do modelo.

#### Gabriel Bortoleto

```text
streamlit/pages/12_bortoleto.py
```

Transforma os resultados históricos em uma análise direcionada ao problema de negócio, apresentando:

- principais fatores associados à competitividade;
- perfil histórico dos vencedores;
- simulador exploratório de cenários;
- indicador heurístico de competitividade;
- recomendações estratégicas;
- limitações da abordagem atual;
- proposta de evolução para um modelo exclusivamente pré-corrida.

O indicador apresentado no simulador é heurístico e não corresponde a uma probabilidade calibrada de vitória produzida pelo Random Forest.

### Limitações e interpretação final

As análises e a modelagem atual possuem caráter histórico, explicativo e exploratório.

Embora o modelo utilize classificação binária para o target `vitoria`, seu resultado também é analisado como ranking dos pilotos dentro de cada corrida.

Parte das principais features — como ritmo representativo, pit stops e características dos stints — somente é conhecida durante ou após a corrida. Portanto, o modelo atual não deve ser apresentado como um sistema de previsão pré-corrida.

Além disso, o conjunto utilizado na modelagem possui apenas 7 corridas e 7 eventos positivos de vitória, enquanto o teste final contém somente 2 corridas. Os resultados devem, portanto, ser interpretados como evidências experimentais dentro do recorte estudado, e não como garantia de generalização.

A importância das features representa associações aprendidas pelo modelo e não demonstra causalidade.

Para Gabriel Bortoleto, os resultados são utilizados para comparar cenários e identificar prioridades historicamente associadas à competitividade em Interlagos.

Uma evolução futura do projeto consiste na construção de um segundo modelo utilizando exclusivamente informações disponíveis antes da largada, permitindo investigar de forma metodologicamente adequada um cenário de previsão pré-corrida.






