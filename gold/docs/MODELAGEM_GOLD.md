# Modelagem da Camada Gold — Formula 1 / Interlagos

> **Documento técnico da camada Gold.**
>
> Este documento consolida a arquitetura definitiva, granularidades, regras de transformação, rastreabilidade com o EDA, prevenção de fan-out, política de SCD, validações e critérios de qualidade da camada Gold.
>
> A Gold é construída a partir da Silver já tratada. Portanto, não repete limpeza, padronização ou tipagem que já foram realizadas na Silver.

---

## 1. Objetivo

A Gold transforma a Silver em um modelo analítico dimensional e reutilizável.

A arquitetura final é:

```text
3 dimensões + 5 fatos
```

com `fct_piloto_corrida` como fato central.

Essa decisão é definitiva para o projeto.

---

# 2. Fontes Silver

Datasets utilizados:

- `calendario`
- `resultados`
- `voltas`
- `pit_stops`
- `pneus`
- `clima`
- `driver_mapping`

A EDA é utilizada como fonte dos requisitos analíticos da Gold.

---

# 3. Arquitetura definitiva

### Dimensões

- `dim_corrida`
- `dim_piloto`
- `dim_equipe`

### Fatos

- `fct_piloto_corrida`
- `fct_voltas`
- `fct_pit_stops`
- `fct_stints`
- `fct_clima`

O `fct_piloto_corrida` é o fato central.

---

# 4. Estruturas deliberadamente não criadas

| Estrutura | Motivo |
|---|---|
| `fct_resultados` | teria o mesmo grão de `fct_piloto_corrida`; resultado e desempenho ficam no fato central |
| `fct_pneus` | a estratégia de pneus é representada por `fct_stints` |
| `dim_temporada` | `season` permanece como atributo de `dim_corrida` |
| `dim_composto` | não necessária ao escopo atual |
| `dim_status` | não necessária ao escopo atual |
| `dim_circuito` | o projeto possui escopo exclusivo em Interlagos |
| SCD Type 2 | não necessário ao objetivo e à natureza histórica do projeto |

A ausência dessas estruturas é uma decisão explícita de modelagem.

---

# 5. Granularidades

| Tabela | Granularidade |
|---|---|
| `dim_corrida` | 1 corrida |
| `dim_piloto` | 1 piloto |
| `dim_equipe` | 1 equipe/construtor |
| `fct_piloto_corrida` | 1 piloto × 1 corrida |
| `fct_voltas` | 1 piloto × 1 corrida × 1 volta |
| `fct_pit_stops` | 1 pit stop |
| `fct_stints` | 1 piloto × 1 corrida × 1 stint |
| `fct_clima` | 1 medição climática |

Cada tabela possui um grão explícito.

Fatos com diferentes granularidades não devem ser combinados diretamente sem agregação prévia e justificativa.

---

# 6. Regra de consumo da Silver

Os atributos da Silver são selecionados diretamente quando não existe transformação analítica necessária.

A Gold não repete:

- `TRIM`;
- `CAST` de atributos de origem;
- conversões de datas;
- conversões de horários;
- limpeza de valores;
- padronizações já realizadas na Silver.

### CASTs

Os CASTs existentes são somente de contagens derivadas:

```sql
COUNT(*)::INTEGER
COUNT(DISTINCT ...)::INTEGER
```

Isso não representa uma re-tipagem de atributos da Silver.

As chaves técnicas criadas com `ROW_NUMBER()` já produzem identificadores inteiros adequados.

---

# 7. Dimensões

## 7.1 `dim_corrida`

**Origem:** `silver_calendario`

**PK:** `race_key`

**Natural key:**

```text
season + round
```

A dimensão contém os atributos necessários para contextualização da corrida e do circuito.

`season` permanece em `dim_corrida`; não existe `dim_temporada`.

A modelagem garante uma linha por `season + round`.

---

## 7.2 `dim_piloto`

**Origem:** `silver_resultados`

**PK:** `driver_key`

**Natural key:** `driver_id`

**SCD:** Type 1

A dimensão consolida a entidade piloto em uma linha por `driver_id`, utilizando os atributos disponíveis na Silver.

---

## 7.3 `dim_equipe`

**Origem:** `silver_resultados`

**PK:** `team_key`

**Natural key:** `constructor_id`

**SCD:** Type 1

A dimensão representa a entidade equipe/construtor.

---

# 8. Política de SCD

| Dimensão | Estratégia |
|---|---|
| `dim_corrida` | Sem SCD |
| `dim_piloto` | Type 1 |
| `dim_equipe` | Type 1 |

Não é utilizada estratégia SCD Type 2 neste projeto.

---

# 9. `fct_piloto_corrida`

**Grão:**

```text
1 piloto × 1 corrida
```

**PK técnica:** `pilot_race_key`

**FKs:**

```text
race_key
driver_key
team_key
```

**Origem:**

```text
silver_resultados
+
agregação de voltas
+
agregação de pit_stops
+
estratégia de pneus reconstruída em fct_stints
```

A fonte `pneus` participa indiretamente por meio da reconstrução de `fct_stints`.

## 9.1 Campos finais

```text
pilot_race_key
race_key
driver_key
team_key
grid
position
status
points
laps
race_time
posicoes_ganhas
ritmo_representativo_pct
voltas_analisadas
voltas_disponiveis
cobertura_ritmo_pct
amostra_reduzida
qtd_pit_stops
duracao_mediana_pit_convencional
qtd_stints
qtd_compostos_distintos
```

> `race_time_millis` não faz parte do schema final documentado.

## 9.2 Ganho/perda de posições

Quando `grid` e `position` são válidos:

```text
posicoes_ganhas = grid - position
```

A variável é derivada do resultado e não deve ser utilizada como feature explicativa em um modelo cujo objetivo seja explicar a vitória.

---

# 10. Prevenção de fan-out

As fontes detalhadas são agregadas independentemente:

```text
resultados → piloto-corrida
voltas     → piloto-corrida
pit_stops  → piloto-corrida
stints     → piloto-corrida
                    ↓
             joins 1:1 por
              piloto-corrida
```

Não deve ser realizado:

```text
resultados
    JOIN voltas
    JOIN pit_stops
    JOIN stints
```

mantendo as linhas detalhadas.

Essa regra evita multiplicação de registros e distorção de métricas.

---

# 11. `fct_voltas`

**Grão:**

```text
1 piloto × 1 corrida × 1 volta
```

**FKs:**

```text
race_key
driver_key
```

## 11.1 Campos finais

```text
race_key
driver_key
lap
lap_time_seconds
delta_ritmo_pct
pit_stop
evento_coletivo_extremo
volta_comparavel
```

## 11.2 Intermediários não persistidos

```text
delta_mediana_pct
delta_volta_pct
delta_contexto_volta_pct
```

Esses campos são utilizados durante o cálculo analítico, mas não precisam ser persistidos.

---

# 12. Metodologia de ritmo

A implementação preserva a sequência definida na EDA:

1. calcular a mediana do tempo de volta da corrida;
2. calcular a mediana por volta dentro da corrida;
3. identificar voltas com pit stop;
4. identificar eventos coletivos extremos quando `delta_contexto_volta_pct > 100`;
5. definir `volta_comparavel` como volta sem pit stop e sem evento coletivo extremo;
6. calcular a mediana de referência das voltas comparáveis;
7. calcular:

```text
delta_ritmo_pct =
lap_time_seconds / mediana_volta_comparavel - 1
```

8. calcular a mediana do delta por piloto-corrida:

```text
ritmo_representativo_pct
```

9. calcular:

```text
voltas_analisadas
```

como a quantidade de voltas comparáveis;

10. calcular:

```text
voltas_disponiveis
```

como a quantidade real de registros de `silver_voltas`;

11. calcular:

```text
cobertura_ritmo_pct =
voltas_analisadas / voltas_disponiveis × 100
```

12. classificar:

```text
amostra_reduzida =
voltas_analisadas < 20
```

O cálculo é uma transformação analítica da Gold e não uma nova limpeza da Silver.

---

# 13. `fct_pit_stops`

**Grão:**

```text
1 pit stop
```

**PK natural:**

```text
season + round + driver_id + stop
```

**FKs:**

```text
race_key
driver_key
```

## 13.1 Campos

```text
race_key
driver_key
stop
lap
duration_seconds
pit_stop_convencional
pit_stop_extremo
```

A duração da Silver é consumida diretamente como `duration_seconds`.

Classificação:

```text
duration_seconds <= 60 → convencional
duration_seconds > 60  → extremo
```

Pit stops extremos permanecem preservados e não são tratados automaticamente como erros.

---

# 14. `fct_stints`

**Grão:**

```text
1 piloto × 1 corrida × 1 stint
```

**PK natural:**

```text
season + round + driver_id + stint_number
```

**FKs:**

```text
race_key
driver_key
```

## 14.1 Campos

```text
race_key
driver_key
stint_number
compound
voltas_observadas
tyre_life_inicial
tyre_life_final
```

A fonte `pneus` contém registros por volta e sessão.

A transformação:

1. seleciona explicitamente `session = 'R'`;
2. utiliza `driver_mapping` para compatibilizar os identificadores FastF1 e Jolpica;
3. reconstrói os stints por piloto.

### `voltas_observadas`

```text
COUNT(DISTINCT lap_number)
```

Representa as voltas efetivamente observadas no stint.

Não deve ser confundida com `tyre_life`.

### Consistência

Se um mesmo stint apresentar mais de um composto, isso deve ser tratado como inconsistência e reprovar a validação, em vez de escolher arbitrariamente um valor.

---

# 15. `fct_clima`

**Grão:**

```text
1 medição climática em um instante da sessão
```

**PK técnica:** `weather_key`

**FK:** `race_key`

## 15.1 Campos

```text
weather_key
race_key
weather_time_seconds
air_temp
track_temp
humidity
pressure
wind_speed
rainfall
wind_direction
event_date
session
session_name
```

Os atributos climáticos são selecionados diretamente da Silver.

## 15.2 Independência temporal

Não existe relação confirmada entre uma medição climática e uma volta específica.

`weather_time_seconds` é relativo à sessão e não possui alinhamento temporal direto com as voltas utilizadas.

Portanto:

```text
fct_clima
```

permanece independente de `fct_voltas`.

Para gerar contexto climático no nível de corrida, primeiro deve-se agregar:

```text
fct_clima → race_key
```

e somente depois associar o resultado a `fct_piloto_corrida`.

Não deve ser realizado join direto das medições climáticas com o fato central.

---

# 16. PKs e FKs

| Tabela | PK | FKs |
|---|---|---|
| `dim_corrida` | `race_key` | — |
| `dim_piloto` | `driver_key` | — |
| `dim_equipe` | `team_key` | — |
| `fct_piloto_corrida` | `pilot_race_key` | `race_key`, `driver_key`, `team_key` |
| `fct_voltas` | `race_key + driver_key + lap` | `race_key`, `driver_key` |
| `fct_pit_stops` | `race_key + driver_key + stop` | `race_key`, `driver_key` |
| `fct_stints` | `race_key + driver_key + stint_number` | `race_key`, `driver_key` |
| `fct_clima` | `weather_key` | `race_key` |

---

# 17. Rastreabilidade EDA → Gold

| Regra/requisito | Implementação | Gold |
|---|---|---|
| Grão piloto-corrida | agregação antes dos joins | `fct_piloto_corrida` |
| Ganho/perda de posições | `grid - position` | `fct_piloto_corrida` |
| Evento coletivo extremo | `delta_contexto_volta_pct > 100` | `fct_voltas` |
| Volta comparável | sem pit stop e sem evento extremo | `fct_voltas` |
| Delta de ritmo | comparação com referência comparável | `fct_voltas` |
| Ritmo representativo | mediana por piloto-corrida | `fct_piloto_corrida` |
| Voltas analisadas | COUNT de voltas comparáveis | `fct_piloto_corrida` |
| Voltas disponíveis | COUNT de registros reais | `fct_piloto_corrida` |
| Cobertura de ritmo | analisadas / disponíveis × 100 | `fct_piloto_corrida` |
| Amostra reduzida | analisadas < 20 | `fct_piloto_corrida` |
| Pit stop convencional | duração <= 60s | `fct_pit_stops` |
| Pit stop extremo | duração > 60s | `fct_pit_stops` |
| Preservação dos extremos | nenhuma remoção | `fct_pit_stops` |
| Reconstrução de stint | sessão Race + agrupamento por stint | `fct_stints` |
| Voltas observadas | COUNT DISTINCT de voltas | `fct_stints` |
| Vida inicial/final | MIN/MAX de tyre_life | `fct_stints` |
| Clima independente | sem join por volta | `fct_clima` |
| Clima como contexto | agregação por `race_key` antes do join | `fct_clima` |

---

# 18. Valores ausentes

A Gold não realiza imputação genérica.

Valores nulos semanticamente válidos da Silver são preservados quando não impedem a construção da métrica.

Exemplo:

```text
ausência de pit stop convencional
≠
duração = 0
```

A finalidade é evitar transformar ausência real em informação artificial.

---

# 19. Qualidade e validações

As validações devem contemplar:

### Dimensões

- unicidade das PKs;
- unicidade das natural keys;
- consistência dos atributos.

### Fatos

- unicidade do grão;
- integridade das FKs;
- ausência de fan-out;
- consistência das métricas.

### Ritmo

- `voltas_analisadas <= voltas_disponiveis`;
- cobertura dentro dos limites esperados;
- consistência de `volta_comparavel`;
- consistência de eventos extremos;
- reconciliação de `ritmo_representativo_pct`.

### Pit stops

- classificação correta dos stops;
- preservação dos stops extremos;
- duração válida quando aplicável.

### Stints

- unicidade do stint;
- sequência dos stints;
- consistência do composto;
- coerência de `voltas_observadas`;
- ausência de múltiplos compostos dentro de um mesmo stint.

### Clima

- unicidade da chave climática;
- FK válida para corrida;
- preservação das medições.

---

# 20. Separação entre validações de construção e testes

As garantias da Gold são distribuídas entre diferentes mecanismos.

## `build_gold.py`

Responsável pela construção das views/materializações e pelas validações executadas durante o processo de build.

## `validate_gold.py`

Responsável pelas validações estruturais e de integridade da Gold materializada.

## `teste_validacao_gold.py`

Responsável pela validação analítica e reconciliação das métricas da Gold com os resultados/metodologias definidos no EDA.

## `test_gold.py`

Responsável pelos testes automatizados das regras críticas da Gold.

## `test_sql_contract.py`

Responsável pelos contratos estruturais dos SQLs, incluindo arquitetura, relações esperadas e proteção contra alterações indevidas.

Essa separação evita atribuir a um único script responsabilidades que pertencem ao conjunto de validações.

---

# 21. Rastreabilidade e reconciliação

A Gold foi comparada com as regras e resultados definidos na EDA.

Principais resultados:

- 202 registros piloto-corrida;
- 12.589 voltas disponíveis;
- 12.008 voltas analisadas/comparáveis;
- 189 registros com `ritmo_representativo_pct`;
- 512 pit stops;
- 70 pit stops extremos;
- 468 stints;
- nenhuma duplicidade no grão piloto-corrida;
- nenhuma divergência na reconciliação do ritmo;
- nenhuma divergência em `voltas_analisadas`;
- nenhuma divergência em `voltas_disponiveis`;
- 8 testes automatizados passando.

Esses resultados demonstram a aderência da implementação às regras analíticas utilizadas como requisito.

---

# 22. Contratos arquiteturais

Os testes de contrato devem proteger, no mínimo:

- existência das 3 dimensões;
- existência dos 5 fatos;
- ausência de estruturas arquiteturais descartadas;
- granularidades esperadas;
- relações entre fatos e dimensões;
- independência de `fct_clima` em relação a piloto e volta;
- ausência de CASTs indevidos sobre atributos de origem;
- preservação das regras críticas de pit stops e stints.

---

# 23. Materialização

DuckDB é utilizado como motor de leitura, transformação e validação.

Após as validações, as estruturas Gold são materializadas como Parquet no MinIO:

```text
s3://f1-data-lake/gold/
```

Arquivos:

```text
dim_corrida.parquet
dim_piloto.parquet
dim_equipe.parquet

fct_piloto_corrida.parquet
fct_voltas.parquet
fct_pit_stops.parquet
fct_stints.parquet
fct_clima.parquet
```

A Gold não cria uma segunda Silver e não altera os Parquets da Silver.

---

# 24. Checklist de critérios da Gold

## Arquitetura

- [x] Arquitetura dimensional definida
- [x] 3 dimensões
- [x] 5 fatos
- [x] Fato central definido
- [x] Estruturas deliberadamente não criadas documentadas

## Modelagem

- [x] Granularidade explícita
- [x] PKs definidas
- [x] FKs definidas
- [x] Natural keys definidas
- [x] Política de SCD definida
- [x] Ausência de SCD Type 2 documentada

## Transformações

- [x] Separação entre limpeza Silver e transformação Gold
- [x] Metodologia de ritmo documentada
- [x] Pit stops classificados
- [x] Pit stops extremos preservados
- [x] Stints reconstruídos
- [x] `voltas_observadas` diferenciada de `tyre_life`
- [x] Clima mantido independente
- [x] Regra de agregação do clima documentada
- [x] Nulos semanticamente válidos preservados

## Integridade

- [x] Prevenção de fan-out
- [x] Agregações independentes
- [x] Joins finais em granularidade compatível
- [x] Unicidade das chaves
- [x] Integridade referencial
- [x] Consistência dos grãos

## Rastreabilidade

- [x] Regras do EDA mapeadas para a Gold
- [x] Métricas de ritmo reconciliadas
- [x] Voltas disponíveis reconciliadas
- [x] Voltas analisadas reconciliadas
- [x] Pit stops reconciliados
- [x] Stints reconciliados

## Qualidade

- [x] Validação estrutural
- [x] Validação analítica
- [x] Testes automatizados
- [x] Contratos SQL
- [x] Materialização em Parquet
- [x] Persistência no MinIO

---

# 25. Regra de manutenção

Este documento deve permanecer alinhado ao fluxo:

```text
EDA
 ↓
Silver
 ↓
Gold
 ↓
ML
```

Caso uma decisão arquitetural seja alterada, a mudança deve ser refletida:

1. neste documento;
2. nos SQLs correspondentes;
3. nos testes;
4. nas validações;
5. nos artefatos materializados.

A Gold não deve ser modificada apenas para atender uma necessidade específica da camada ML sem avaliar o impacto sobre o modelo analítico já definido.

---

# 26. Status da camada Gold

```text
Arquitetura       ✓
Dimensões         ✓
Fatos             ✓
Granularidade     ✓
Transformações    ✓
Ritmo             ✓
Pit Stops         ✓
Stints/Pneus      ✓
Clima             ✓
PK/FK             ✓
SCD               ✓
Fan-out           ✓
Qualidade         ✓
Validação EDA     ✓
Testes            ✓
Contratos SQL     ✓
MinIO             ✓
```

**Status: camada Gold modelada, materializada e validada para o escopo atual do projeto.**
