from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Gabriel Bortoleto | Interlagos",
    page_icon="🏁",
    layout="wide",
)


ROOT = Path(__file__).resolve().parents[2]

RESULTS_DIR = ROOT / "ml" / "results"


# ============================================================
# CAMINHOS
# ============================================================

FINAL_PREDICTIONS_PATH = (
    RESULTS_DIR
    / "final_test_predictions.csv"
)

FINAL_RACE_SUMMARY_PATH = (
    RESULTS_DIR
    / "final_test_race_summary.csv"
)


# ============================================================
# FUNÇÕES
# ============================================================

@st.cache_data
def carregar_csv(path):
    """
    Carrega CSV utilizado pela página.
    """

    path = Path(path)

    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path)


def classificar_cenario_grid(grid):
    """
    Classificação simples para interpretação do grid.
    """

    if grid <= 3:
        return "Muito favorável"

    if grid <= 6:
        return "Favorável"

    if grid <= 10:
        return "Intermediário"

    if grid <= 15:
        return "Desafiador"

    return "Muito desafiador"


def classificar_ritmo(ritmo):
    """
    Interpretação do ritmo relativo.

    Valores mais negativos representam ritmo
    relativamente mais competitivo.
    """

    if ritmo <= -1.5:
        return "Excelente"

    if ritmo <= -0.8:
        return "Competitivo"

    if ritmo <= 0:
        return "Próximo da referência"

    if ritmo <= 0.8:
        return "Abaixo da referência"

    return "Muito abaixo da referência"


def classificar_pit(pit):
    """
    Interpretação simplificada da duração mediana
    de pit stop convencional.
    """

    if pit <= 22.5:
        return "Muito competitivo"

    if pit <= 23.0:
        return "Competitivo"

    if pit <= 23.5:
        return "Intermediário"

    return "Pode comprometer a estratégia"


# ============================================================
# CARREGAMENTO
# ============================================================

final_predictions = carregar_csv(
    FINAL_PREDICTIONS_PATH
)

race_summary = carregar_csv(
    FINAL_RACE_SUMMARY_PATH
)


# ============================================================
# CABEÇALHO
# ============================================================

st.title("🏁 Gabriel Bortoleto — Cenários para Interlagos")

st.markdown(
    """
Esta página transforma os resultados históricos e de
Machine Learning em uma leitura orientada ao objetivo
do projeto:

**quais fatores devem ser priorizados para aumentar a
competitividade de Gabriel Bortoleto em Interlagos?**

A análise abaixo é **prescritiva e exploratória**.

Ela não representa uma previsão determinística de vitória
e não substitui informações reais de classificação,
treinos, estratégia, carro ou condições da corrida.
"""
)


# ============================================================
# 1. PRINCIPAIS FATORES
# ============================================================

st.header("1. O que mais importa no histórico analisado?")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "1º fator",
        "Ritmo de corrida",
    )

with col2:
    st.metric(
        "2º fator",
        "Posição de largada",
    )

with col3:
    st.metric(
        "3º fator",
        "Execução dos pit stops",
    )


st.markdown(
    """
A interpretação conjunta da EDA e do Random Forest
indica três prioridades principais:

**Ritmo representativo de corrida**

Foi a variável mais importante no modelo final.
Historicamente, vencedores apresentam ritmo relativo
superior ao restante do grid.

**Classificação**

O grid não determina sozinho o resultado, mas largar
na frente reduz a necessidade de recuperação e aumenta
a flexibilidade estratégica.

**Execução estratégica**

Pit stops, stints e pneus podem ampliar ou reduzir a
vantagem construída por ritmo e posição de largada.
"""
)


# ============================================================
# 2. REFERÊNCIA HISTÓRICA
# ============================================================

st.header("2. Perfil histórico de referência")

st.markdown(
    """
No conjunto utilizado na modelagem, os vencedores
apresentaram aproximadamente:

- **grid médio:** 2,8;
- **grid mediano:** 1;
- **ritmo representativo médio:** -1,48%;
- **ritmo representativo mediano:** -1,19%;
- **pit stop convencional mediano:** aproximadamente 22,7 s.

Já os não vencedores apresentaram, em média:

- grid próximo de 10,5;
- ritmo representativo próximo de 0%;
- pit stop convencional mediano próximo de 23,4 s.

Esses números não são metas rígidas. Eles funcionam como
**referências históricas** para contextualizar cenários.
"""
)


# ============================================================
# 3. SIMULADOR DE CENÁRIO
# ============================================================

st.header("3. Simulador exploratório de cenário")

st.info(
    """
O simulador abaixo é uma ferramenta de interpretação.

Ele compara um cenário hipotético com referências
históricas identificadas no projeto.

Não utiliza o modelo como previsão pré-corrida, pois parte
das variáveis — como ritmo e pit stops — só são conhecidas
durante ou após a corrida.
"""
)


col1, col2, col3 = st.columns(3)

with col1:

    grid = st.slider(
        "Posição de largada",
        min_value=1,
        max_value=20,
        value=10,
        step=1,
    )

with col2:

    ritmo = st.slider(
        "Ritmo relativo representativo (%)",
        min_value=-3.0,
        max_value=3.0,
        value=0.0,
        step=0.1,
    )

with col3:

    pit = st.slider(
        "Pit stop convencional mediano (s)",
        min_value=20.0,
        max_value=30.0,
        value=23.0,
        step=0.1,
    )


st.subheader("Leitura do cenário")


col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Grid",
        f"P{grid}",
        classificar_cenario_grid(
            grid
        ),
    )

with col2:
    st.metric(
        "Ritmo",
        f"{ritmo:.1f}%",
        classificar_ritmo(
            ritmo
        ),
    )

with col3:
    st.metric(
        "Pit stop",
        f"{pit:.1f}s",
        classificar_pit(
            pit
        ),
    )


# ============================================================
# 4. SCORE EXPLORATÓRIO DE CENÁRIO
# ============================================================

st.subheader("Indicador de competitividade do cenário")

st.markdown(
    """
Para facilitar a leitura executiva, construímos um
**indicador heurístico**, e não uma probabilidade de
vitória.

Ele resume três dimensões observadas como relevantes no
histórico: grid, ritmo e execução do pit stop.
"""
)


grid_score = max(
    0,
    min(
        100,
        (
            (20 - grid)
            / 19
        )
        * 100,
    ),
)

ritmo_score = max(
    0,
    min(
        100,
        (
            (3 - ritmo)
            / 6
        )
        * 100,
    ),
)

pit_score = max(
    0,
    min(
        100,
        (
            (30 - pit)
            / 10
        )
        * 100,
    ),
)


indicador = (
    grid_score * 0.30
    + ritmo_score * 0.45
    + pit_score * 0.25
)


st.progress(
    int(
        round(
            indicador
        )
    )
)

st.metric(
    "Indicador exploratório",
    f"{indicador:.1f}/100",
)


st.caption(
    """
O indicador acima é uma regra heurística construída para
apresentação e comparação de cenários.

Ele não é a saída probabilística do Random Forest e não
deve ser interpretado como chance percentual de vitória.
"""
)


# ============================================================
# 5. INTERPRETAÇÃO DO CENÁRIO
# ============================================================

st.header("4. O que o cenário sugere?")


recomendacoes = []


if grid <= 3:

    recomendacoes.append(
        "A posição de largada está alinhada ao perfil "
        "historicamente observado entre vencedores."
    )

elif grid <= 10:

    recomendacoes.append(
        "O grid ainda permite competitividade, mas aumenta "
        "a dependência de ritmo e execução estratégica."
    )

else:

    recomendacoes.append(
        "A posição de largada cria forte necessidade de "
        "recuperação durante a corrida."
    )


if ritmo <= -1.0:

    recomendacoes.append(
        "O ritmo relativo está próximo do padrão histórico "
        "observado entre vencedores."
    )

elif ritmo <= 0:

    recomendacoes.append(
        "O ritmo é competitivo, mas ainda abaixo da "
        "referência típica dos vencedores."
    )

else:

    recomendacoes.append(
        "O ritmo representa o principal ponto de atenção "
        "do cenário atual."
    )


if pit <= 23.0:

    recomendacoes.append(
        "A execução de pit stop está em uma faixa "
        "historicamente competitiva."
    )

else:

    recomendacoes.append(
        "Reduzir perdas nos pit stops pode ser importante "
        "para preservar posição e estratégia."
    )


for recomendacao in recomendacoes:

    st.write(
        f"• {recomendacao}"
    )


# ============================================================
# 6. CENÁRIOS ILUSTRATIVOS
# ============================================================

st.header("5. Comparação de cenários")

cenarios = pd.DataFrame(
    [
        {
            "Cenário": "Competitivo",
            "Grid": 3,
            "Ritmo relativo (%)": -1.5,
            "Pit mediano (s)": 22.5,
        },
        {
            "Cenário": "Intermediário",
            "Grid": 8,
            "Ritmo relativo (%)": -0.5,
            "Pit mediano (s)": 23.2,
        },
        {
            "Cenário": "Desafiador",
            "Grid": 15,
            "Ritmo relativo (%)": 0.8,
            "Pit mediano (s)": 24.0,
        },
    ]
)


st.dataframe(
    cenarios,
    use_container_width=True,
    hide_index=True,
)


st.markdown(
    """
Os cenários mostram que diferentes combinações podem
produzir contextos muito distintos.

Um bom grid pode perder valor se o ritmo de corrida for
fraco.

Da mesma forma, um grid intermediário pode ser parcialmente
compensado por ritmo forte e execução estratégica eficiente.
"""
)


# ============================================================
# 7. PRIORIDADES PARA BORTOLETO
# ============================================================

st.header("6. Prioridades estratégicas para Gabriel Bortoleto")


st.success(
    """
### Prioridade 1 — Maximizar ritmo sustentável

O resultado do modelo indica que ritmo representativo
é o principal fator associado ao desempenho.

A prioridade não deve ser apenas produzir uma volta
rápida, mas sustentar ritmo competitivo ao longo dos
stints.
"""
)


st.success(
    """
### Prioridade 2 — Reduzir dependência de recuperação

Uma classificação forte continua sendo importante.

Largar mais à frente reduz tráfego, risco de incidentes
e necessidade de ultrapassagens, além de aumentar as
opções estratégicas.
"""
)


st.success(
    """
### Prioridade 3 — Executar a estratégia sem perdas

Pit stops, escolha de pneus e duração dos stints não
substituem ritmo de corrida, mas podem determinar se uma
vantagem potencial será preservada ou perdida.
"""
)


st.success(
    """
### Prioridade 4 — Usar clima e Safety Car como contexto

Condições climáticas, chuva e neutralizações podem mudar
a dinâmica da corrida.

Esses fatores devem ser tratados como variáveis de cenário,
e não como garantia de vantagem.
"""
)


# ============================================================
# 8. O QUE O MODELO NÃO RESPONDE
# ============================================================

st.header("7. O que ainda não conseguimos prever?")


st.warning(
    """
O projeto atual não permite afirmar antecipadamente:

- a probabilidade real de Bortoleto vencer;
- o desempenho futuro do carro;
- a estratégia real das equipes adversárias;
- quando ocorrerá Safety Car;
- quando choverá;
- se haverá incidentes ou falhas mecânicas.

Além disso, parte das principais variáveis do modelo
atual só existe durante a corrida.

Portanto, o resultado deve ser apresentado como
**análise histórica e ferramenta de cenários**, e não
como previsão definitiva.
"""
)


# ============================================================
# 9. PRÓXIMA EVOLUÇÃO
# ============================================================

st.header("8. Próxima evolução do projeto")


st.markdown(
    """
Uma evolução natural seria desenvolver um segundo modelo
exclusivamente **pré-corrida**.

Esse modelo poderia utilizar apenas informações disponíveis
antes da largada, por exemplo:

- posição no grid;
- desempenho em classificação;
- desempenho recente do piloto;
- desempenho recente da equipe;
- características do circuito;
- previsão meteorológica;
- histórico em pistas semelhantes.

Assim teríamos duas perspectivas complementares:

**Modelo atual**

Análise histórica, explicativa e de ranking.

**Modelo futuro**

Estimativa pré-corrida baseada apenas em informações
disponíveis antes da largada.
"""
)


# ============================================================
# 10. CONCLUSÃO EXECUTIVA
# ============================================================

st.header("9. Conclusão executiva")


st.markdown(
    """
A principal conclusão do projeto é que uma eventual
vitória de Gabriel Bortoleto em Interlagos dependeria
de uma combinação de fatores.

O histórico analisado sugere que os maiores ganhos estão
associados a:

1. ritmo competitivo e sustentável;
2. posição de largada favorável;
3. pit stops eficientes;
4. boa gestão de pneus e stints;
5. adaptação ao contexto da corrida.

Portanto, a recomendação não é buscar uma única
"variável mágica".

A melhor estratégia é construir um cenário em que
**ritmo, classificação e execução estratégica trabalhem
em conjunto**.
"""
)


# ============================================================
# 11. EVIDÊNCIAS DO TESTE DO MODELO
# ============================================================

with st.expander(
    "Ver evidências utilizadas na modelagem"
):

    st.markdown(
        """
Os dados abaixo correspondem ao conjunto de teste final
do modelo e são apresentados somente como evidência
técnica da etapa de Machine Learning.
"""
    )

    if not race_summary.empty:

        st.markdown(
            "#### Resultado por corrida"
        )

        st.dataframe(
            race_summary,
            use_container_width=True,
            hide_index=True,
        )

    if not final_predictions.empty:

        st.markdown(
            "#### Scores dos pilotos"
        )

        st.dataframe(
            final_predictions,
            use_container_width=True,
            hide_index=True,
        )