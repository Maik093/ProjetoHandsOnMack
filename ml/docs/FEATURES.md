# Catálogo de Features — Dataset ML Interlagos

| Coluna | Origem Gold | Granularidade original | Transformação | Tipo | Classe |
|---|---|---|---|---|---|
| pilot_race_key | fct_piloto_corrida | piloto-corrida | preservar | BIGINT | ID |
| race_key | fct_piloto_corrida | piloto-corrida | preservar | BIGINT | ID |
| driver_key | fct_piloto_corrida | piloto-corrida | preservar | BIGINT | ID |
| team_key | fct_piloto_corrida | piloto-corrida | preservar | BIGINT | ID |
| season | dim_corrida | corrida | preservar | INTEGER | Contexto |
| round | dim_corrida | corrida | preservar | INTEGER | Contexto |
| race_name | dim_corrida | corrida | preservar | VARCHAR | Contexto |
| full_name | dim_piloto | piloto | preservar | VARCHAR | Contexto |
| constructor_name | dim_equipe | equipe | preservar | VARCHAR | Contexto |
| grid | fct_piloto_corrida | piloto-corrida | preservar | INTEGER | Feature |
| ritmo_representativo_pct | fct_piloto_corrida | piloto-corrida | preservar | DOUBLE | Feature |
| voltas_analisadas | fct_piloto_corrida | piloto-corrida | preservar | INTEGER | Feature |
| voltas_disponiveis | fct_piloto_corrida | piloto-corrida | preservar | INTEGER | Feature |
| cobertura_ritmo_pct | fct_piloto_corrida | piloto-corrida | preservar | DOUBLE | Feature |
| amostra_reduzida | fct_piloto_corrida | piloto-corrida | preservar | BOOLEAN | Feature |
| qtd_pit_stops | fct_pit_stops | pit stop | COUNT por piloto-corrida | INTEGER | Feature |
| duracao_mediana_pit_convencional | fct_pit_stops | pit stop | MEDIAN dos stops <=60s | DOUBLE | Feature |
| qtd_stints | fct_stints | stint | COUNT por piloto-corrida | INTEGER | Feature |
| qtd_compostos_distintos | fct_stints | stint | COUNT DISTINCT | INTEGER | Feature |
| primeiro_composto | fct_stints | stint | composto do stint 1 | VARCHAR | Feature |
| composto_mais_utilizado | fct_stints | stint | maior soma de voltas; empate lexicográfico | VARCHAR | Feature |
| voltas_stint_medio | fct_stints | stint | AVG de voltas_observadas | DOUBLE | Feature |
| air_temp_media | fct_clima | medição | AVG por corrida | DOUBLE | Feature |
| track_temp_media | fct_clima | medição | AVG por corrida | DOUBLE | Feature |
| humidity_media | fct_clima | medição | AVG por corrida | DOUBLE | Feature |
| pressure_media | fct_clima | medição | AVG por corrida | DOUBLE | Feature |
| wind_speed_medio | fct_clima | medição | AVG por corrida | DOUBLE | Feature |
| rainfall_ocorreu | fct_clima | medição | qualquer chuva -> 1 | BOOLEAN | Feature |
| vitoria | position em fct_piloto_corrida | piloto-corrida | position == 1 | BOOLEAN | Target |

## Excluídas

| Coluna | Motivo |
|---|---|
| position | usada somente para criar `vitoria` |
| posicoes_ganhas | transformação direta do resultado |
| points | resultado esportivo |
| race_time | desempenho final |
| laps | redundante para este objetivo |
| status | muito próximo do desfecho |
| circuit_name | constante em Interlagos |
| date | não necessária na primeira versão |
| tyre_life_inicial | fora do escopo inicial |
| tyre_life_final | fora do escopo inicial |
