# EDA — Dataset ML Interlagos

EDA específica do dataset ML, focada na relação entre as features consolidadas e `vitoria`.

## 1. Escopo
- Fonte: `s3://f1-data-lake/ml/dataset/dataset_ml_interlagos.parquet`
- Período: 2018–2025
- Registros: 140
- Vitórias: 7
- Não vitórias: 133
- Taxa de vitória: 5.00%

## 2. Validação estrutural
| validacao                   |   valor |
|:----------------------------|--------:|
| total_linhas                |     140 |
| total_colunas               |      29 |
| duplicidades_race_driver    |       0 |
| duplicidades_pilot_race_key |       0 |
| position_presente           |       0 |
| vitoria_presente            |       1 |
| vitoria_nulos               |       0 |
| temporadas                  |       7 |
| corridas                    |       7 |
| pilotos                     |      39 |

## 3. Distribuição do target
| vitoria   |   registros |   percentual |
|:----------|------------:|-------------:|
| False     |         133 |           95 |
| True      |           7 |            5 |

A classe positiva é minoritária. Isso deve ser considerado na modelagem e na escolha das métricas.

## 4. Vitórias por temporada
|   season |   pilotos |   vitorias |   taxa_vitoria_pct |
|---------:|----------:|-----------:|-------------------:|
|     2018 |        20 |          1 |                  5 |
|     2019 |        20 |          1 |                  5 |
|     2021 |        20 |          1 |                  5 |
|     2022 |        20 |          1 |                  5 |
|     2023 |        20 |          1 |                  5 |
|     2024 |        20 |          1 |                  5 |
|     2025 |        20 |          1 |                  5 |

## 5. Features numéricas — vencedores x não vencedores
| feature                          | grupo          |   n |    media |   mediana |   desvio_padrao |      min |      max |
|:---------------------------------|:---------------|----:|---------:|----------:|----------------:|---------:|---------:|
| grid                             | vencedores     |   7 |   4.5714 |    1.0000 |          6.4254 |   1.0000 |  17.0000 |
| grid                             | nao_vencedores | 133 |  10.5113 |   11.0000 |          5.6416 |   0.0000 |  20.0000 |
| ritmo_representativo_pct         | vencedores     |   7 |  -1.3250 |   -1.1054 |          0.5001 |  -2.0991 |  -0.7670 |
| ritmo_representativo_pct         | nao_vencedores | 125 |   0.0350 |    0.1071 |          0.7926 |  -2.0061 |   2.4568 |
| voltas_analisadas                | vencedores     |   7 |  68.0000 |   68.0000 |          1.4142 |  66.0000 |  70.0000 |
| voltas_analisadas                | nao_vencedores | 133 |  59.8647 |   67.0000 |         18.9544 |   0.0000 |  70.0000 |
| voltas_disponiveis               | vencedores     |   7 |  70.7143 |   71.0000 |          0.7559 |  69.0000 |  71.0000 |
| voltas_disponiveis               | nao_vencedores | 133 |  62.4662 |   70.0000 |         19.5516 |   0.0000 |  71.0000 |
| cobertura_ritmo_pct              | vencedores     |   7 |  96.1654 |   97.1014 |          1.9370 |  92.9577 |  98.5915 |
| cobertura_ritmo_pct              | nao_vencedores | 125 |  95.6956 |   95.7746 |          2.4394 |  81.8182 | 100.0000 |
| qtd_pit_stops                    | vencedores     |   7 |   2.4286 |    2.0000 |          1.2724 |   1.0000 |   4.0000 |
| qtd_pit_stops                    | nao_vencedores | 133 |   2.3684 |    2.0000 |          1.2521 |   0.0000 |   5.0000 |
| duracao_mediana_pit_convencional | vencedores     |   6 |  22.6364 |   22.8255 |          1.0298 |  20.6620 |  23.5005 |
| duracao_mediana_pit_convencional | nao_vencedores | 120 |  23.8090 |   23.5575 |          2.6917 |  17.7510 |  35.7550 |
| qtd_stints                       | vencedores     |   7 |   3.4286 |    3.0000 |          1.2724 |   2.0000 |   5.0000 |
| qtd_stints                       | nao_vencedores | 133 |   3.3383 |    3.0000 |          1.3078 |   0.0000 |   6.0000 |
| qtd_compostos_distintos          | vencedores     |   7 |   1.8571 |    2.0000 |          0.3780 |   1.0000 |   2.0000 |
| qtd_compostos_distintos          | nao_vencedores | 133 |   1.9173 |    2.0000 |          0.5779 |   0.0000 |   3.0000 |
| voltas_stint_medio               | vencedores     |   7 |  23.3548 |   23.6667 |          8.8596 |  14.2000 |  35.5000 |
| voltas_stint_medio               | nao_vencedores | 130 |  20.0409 |   22.0000 |          8.2943 |   1.0000 |  35.5000 |
| air_temp_media                   | vencedores     |   7 |  21.4865 |   21.6627 |          2.1868 |  17.3480 |  23.7696 |
| air_temp_media                   | nao_vencedores | 133 |  21.4865 |   21.6627 |          2.0323 |  17.3480 |  23.7696 |
| track_temp_media                 | vencedores     |   7 |  41.0530 |   46.0491 |          9.4797 |  25.7697 |  51.5614 |
| track_temp_media                 | nao_vencedores | 133 |  41.0530 |   46.0491 |          8.8097 |  25.7697 |  51.5614 |
| humidity_media                   | vencedores     |   7 |  69.4125 |   70.5724 |         10.2396 |  58.1749 |  85.2587 |
| humidity_media                   | nao_vencedores | 133 |  69.4125 |   70.5724 |          9.5159 |  58.1749 |  85.2587 |
| pressure_media                   | vencedores     |   7 | 925.9826 |  926.4567 |          2.5471 | 922.1605 | 929.7086 |
| pressure_media                   | nao_vencedores | 133 | 925.9826 |  926.4567 |          2.3671 | 922.1605 | 929.7086 |
| wind_speed_medio                 | vencedores     |   7 |   1.2666 |    1.3093 |          0.5756 |   0.3918 |   2.1872 |
| wind_speed_medio                 | nao_vencedores | 133 |   1.2666 |    1.3093 |          0.5349 |   0.3918 |   2.1872 |

## 6. Associação numérica com `vitoria`
| feature                          |   n_disponivel |   pearson_com_vitoria |   spearman_com_vitoria |   abs_spearman |
|:---------------------------------|---------------:|----------------------:|-----------------------:|---------------:|
| ritmo_representativo_pct         |            132 |               -0.3657 |                -0.3198 |         0.3198 |
| grid                             |            140 |               -0.2238 |                -0.2245 |         0.2245 |
| duracao_mediana_pit_convencional |            126 |               -0.0947 |                -0.1732 |         0.1732 |
| voltas_disponiveis               |            140 |                0.0943 |                 0.1485 |         0.1485 |
| voltas_analisadas                |            140 |                0.0959 |                 0.1129 |         0.1129 |
| voltas_stint_medio               |            137 |                0.0880 |                 0.0935 |         0.0935 |
| cobertura_ritmo_pct              |            132 |                0.0438 |                 0.0484 |         0.0484 |
| qtd_compostos_distintos          |            140 |               -0.0231 |                -0.0315 |         0.0315 |
| qtd_stints                       |            140 |                0.0152 |                 0.0055 |         0.0055 |
| qtd_pit_stops                    |            140 |                0.0105 |                 0.0038 |         0.0038 |
| air_temp_media                   |            140 |               -0.0000 |                 0.0000 |         0.0000 |
| track_temp_media                 |            140 |                0.0000 |                 0.0000 |         0.0000 |
| humidity_media                   |            140 |                0.0000 |                 0.0000 |         0.0000 |
| pressure_media                   |            140 |               -0.0000 |                 0.0000 |         0.0000 |
| wind_speed_medio                 |            140 |                0.0000 |                 0.0000 |         0.0000 |

As correlações são medidas exploratórias de associação e não representam causalidade.

## 7. Features categóricas
| feature                 | primeiro_composto   |   registros |   vitorias |   taxa_vitoria_pct | composto_mais_utilizado   |
|:------------------------|:--------------------|------------:|-----------:|-------------------:|:--------------------------|
| primeiro_composto       | HARD                |           6 |          0 |               0.00 | nan                       |
| primeiro_composto       | INTERMEDIATE        |          18 |          1 |               5.56 | nan                       |
| primeiro_composto       | MEDIUM              |          42 |          2 |               4.76 | nan                       |
| primeiro_composto       | SOFT                |          62 |          3 |               4.84 | nan                       |
| primeiro_composto       | SUPERSOFT           |           9 |          1 |              11.11 | nan                       |
| primeiro_composto       | nan                 |           3 |          0 |               0.00 | nan                       |
| composto_mais_utilizado | nan                 |          13 |          1 |               7.69 | HARD                      |
| composto_mais_utilizado | nan                 |          18 |          1 |               5.56 | INTERMEDIATE              |
| composto_mais_utilizado | nan                 |          52 |          2 |               3.85 | MEDIUM                    |
| composto_mais_utilizado | nan                 |          51 |          3 |               5.88 | SOFT                      |
| composto_mais_utilizado | nan                 |           3 |          0 |               0.00 | SUPERSOFT                 |
| composto_mais_utilizado | nan                 |           3 |          0 |               0.00 | nan                       |

## 8. Missing values
| feature                          |   nulos |   pct_nulos |
|:---------------------------------|--------:|------------:|
| duracao_mediana_pit_convencional |      14 |       10    |
| cobertura_ritmo_pct              |       8 |        5.71 |
| ritmo_representativo_pct         |       8 |        5.71 |
| composto_mais_utilizado          |       3 |        2.14 |
| primeiro_composto                |       3 |        2.14 |
| voltas_stint_medio               |       3 |        2.14 |

### Missing x target
| feature                          |   nulos |   nulos_vencedores |   nulos_nao_vencedores |   taxa_vitoria_nulos_pct |   taxa_vitoria_disponiveis_pct |
|:---------------------------------|--------:|-------------------:|-----------------------:|-------------------------:|-------------------------------:|
| ritmo_representativo_pct         |       8 |                  0 |                      8 |                     0.00 |                           5.30 |
| cobertura_ritmo_pct              |       8 |                  0 |                      8 |                     0.00 |                           5.30 |
| duracao_mediana_pit_convencional |      14 |                  1 |                     13 |                     7.14 |                           4.76 |
| voltas_stint_medio               |       3 |                  0 |                      3 |                     0.00 |                           5.11 |
| primeiro_composto                |       3 |                  0 |                      3 |                     0.00 |                           5.11 |
| composto_mais_utilizado          |       3 |                  0 |                      3 |                     0.00 |                           5.11 |

## 9. Redundância
| feature_a           | feature_b           |   spearman |   abs_spearman |
|:--------------------|:--------------------|-----------:|---------------:|
| qtd_pit_stops       | qtd_stints          |     0.9966 |         0.9966 |
| cobertura_ritmo_pct | voltas_stint_medio  |     0.9025 |         0.9025 |
| voltas_analisadas   | voltas_stint_medio  |     0.8520 |         0.8520 |
| cobertura_ritmo_pct | qtd_pit_stops       |    -0.8316 |         0.8316 |
| track_temp_media    | humidity_media      |    -0.8214 |         0.8214 |
| voltas_analisadas   | cobertura_ritmo_pct |     0.8180 |         0.8180 |
| cobertura_ritmo_pct | qtd_stints          |    -0.8169 |         0.8169 |
| voltas_analisadas   | voltas_disponiveis  |     0.8021 |         0.8021 |

## 10. Preparação para modelagem
- O target é fortemente desbalanceado: apenas 7 vitórias.
- `position` não está presente e não deve ser reintroduzida como feature.
- Nulos devem ser tratados conforme a natureza de cada variável, sem imputação indiscriminada.
- `voltas_analisadas`, `voltas_disponiveis` e `cobertura_ritmo_pct` devem ser avaliadas quanto à redundância.
- `qtd_pit_stops` e `qtd_stints` devem ser avaliadas conjuntamente.
- Identificadores e colunas de contexto não devem entrar automaticamente como features numéricas.
- Devido ao pequeno número de positivos, resultados de modelagem podem ser instáveis.

## 11. Limitações
- 140 observações e apenas 7 eventos positivos.
- Associação não implica causalidade.
- A definição do momento da previsão deve ser estabelecida antes de qualquer modelagem preditiva para evitar uso indevido de variáveis pós-corrida.