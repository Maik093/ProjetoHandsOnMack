# Modelagem ML — Interlagos

## 1. Arquitetura
A camada ML é derivada exclusivamente da Gold e não altera nenhuma tabela Gold.

```text
Gold -> agregações independentes -> dataset ML
```

## 2. Granularidade
Cada linha representa um piloto em uma corrida de Interlagos.
A chave lógica é `race_key + driver_key`; `pilot_race_key` é a chave técnica.

## 3. Agregação e fan-out
- `fct_voltas`: reduzida para piloto-corrida.
- `fct_pit_stops`: reduzida para piloto-corrida.
- `fct_stints`: reduzida para piloto-corrida.
- `fct_clima`: reduzida para corrida.
Somente depois essas relações são consolidadas.

Isso evita multiplicação de linhas causada por fatos com diferentes cardinalidades.

## 4. Target
`vitoria = position == 1`.
`position` é usada somente para criar o target.

## 5. Features
Largada: `grid`.

Ritmo: `ritmo_representativo_pct`, `voltas_analisadas`,
`voltas_disponiveis`, `cobertura_ritmo_pct`, `amostra_reduzida`.

Pit stops: `qtd_pit_stops`, `duracao_mediana_pit_convencional`.
Pit stops extremos permanecem preservados na Gold.

Estratégia: `qtd_stints`, `qtd_compostos_distintos`, `primeiro_composto`,
`composto_mais_utilizado`, `voltas_stint_medio`.

Clima: `air_temp_media`, `track_temp_media`, `humidity_media`,
`pressure_media`, `wind_speed_medio`, `rainfall_ocorreu`.

## 6. Regra de empate de composto
`composto_mais_utilizado` é o composto com maior soma de `voltas_observadas`.
Empates são resolvidos lexicograficamente, garantindo reprodutibilidade.

## 7. Nulos
Ausência de pit stop convencional não vira zero segundos.
Nulos semanticamente válidos são preservados.

`voltas_observadas` nunca é interpretada como `tyre_life`.

Clima não é relacionado temporalmente às voltas.

## 8. Variáveis excluídas
- `position`: define o target.
- `posicoes_ganhas`: deriva de `grid - position`.
- `points`: resultado esportivo.
- `race_time`: desempenho final.
- `laps`: redundante para o objetivo.
- `status`: próximo do desfecho/terminação.
- `circuit_name`: constante no escopo.
- `date`: contexto temporal não necessário na primeira versão.
- `tyre_life_inicial`, `tyre_life_final`: não utilizados nesta primeira versão.

## 9. Contexto e IDs
`pilot_race_key`, `race_key`, `driver_key`, `team_key` são identificadores.
`season`, `round`, `race_name`, `full_name`, `constructor_name` são contexto.
Eles não devem ser tratados automaticamente como features numéricas.

## 10. Leakage
Para o objetivo explicativo, ritmo, pit stops, stints e clima observados na
própria corrida podem ser features. Para uma futura previsão pré-corrida,
essas features pós-largada não seriam permitidas.

## 11. Futuro
A próxima etapa, após revisão do Dataset, poderá implementar classificação
binária interpretável. Não há treinamento nesta camada.
