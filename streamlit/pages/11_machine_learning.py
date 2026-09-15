from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Machine Learning | Interlagos",
    page_icon="🤖",
    layout="wide",
)


ROOT = Path(__file__).resolve().parents[2]

RESULTS_DIR = ROOT / "ml" / "results"

VISUALIZATION_DIR = (
    ROOT
    / "ml"
    / "visualization"
    / "outputs"
)


# ============================================================
# CAMINHOS DOS ARQUIVOS
# ============================================================

MODEL_COMPARISON_PATH = (
    RESULTS_DIR
    / "model_comparison.csv"
)

FINAL_METRICS_PATH = (
    RESULTS_DIR
    / "final_test_metrics.csv"
)

FINAL_PREDICTIONS_PATH = (
    RESULTS_DIR
    / "final_test_predictions.csv"
)

FINAL_RACE_SUMMARY_PATH = (
    RESULTS_DIR
    / "final_test_race_summary.csv"
)

FINAL_RANKING_PATH = (
    RESULTS_DIR
    / "final_test_ranking_metrics.csv"
)


GRAPH_MODEL_COMPARISON = (
    VISUALIZATION_DIR
    / "01_comparacao_modelos.png"
)

GRAPH_CONFUSION_MATRIX = (
    VISUALIZATION_DIR
    / "02_matriz_confusao.png"
)

GRAPH_ROC = (
    VISUALIZATION_DIR
    / "03_curva_roc.png"
)

GRAPH_FEATURE_IMPORTANCE = (
    VISUALIZATION_DIR
    / "04_importancia_features.png"
)


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

@st.cache_data
def carregar_csv(path):
    """
    Carrega um CSV utilizado pela página.
    """

    path = Path(path)

    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path)


def obter_valor(
    df,
    coluna,
    default=None,
):
    """
    Obtém o primeiro valor de uma coluna,
    caso ela exista no DataFrame.
    """

    if df.empty:
        return default

    if coluna not in df.columns:
        return default

    return df.iloc[0][coluna]


def percentual(
    valor,
    casas=1,
):
    """
    Formata valores de 0 a 1 como percentual.
    """

    if valor is None:
        return "-"

    try:
        return (
            f"{float(valor) * 100:.{casas}f}%"
        )
    except (TypeError, ValueError):
        return "-"


def numero(
    valor,
    casas=3,
):
    """
    Formata valores numéricos.
    """

    if valor is None:
        return "-"

    try:
        return f"{float(valor):.{casas}f}"
    except (TypeError, ValueError):
        return "-"


# ============================================================
# CARREGAMENTO
# ============================================================

model_comparison = carregar_csv(
    MODEL_COMPARISON_PATH
)

final_metrics = carregar_csv(
    FINAL_METRICS_PATH
)

final_predictions = carregar_csv(
    FINAL_PREDICTIONS_PATH
)

race_summary = carregar_csv(
    FINAL_RACE_SUMMARY_PATH
)

ranking_metrics = carregar_csv(
    FINAL_RANKING_PATH
)


# ============================================================
# CABEÇALHO
# ============================================================

st.title("🤖 Machine Learning — Interlagos")

st.markdown(
    """
Esta etapa utiliza os dados históricos de Interlagos para
identificar características associadas à vitória e avaliar
a capacidade do modelo de **ordenar os pilotos dentro de
cada corrida**.

O modelo deve ser interpretado como uma ferramenta
**histórica, explicativa e de ranking**.

Ele **não representa uma previsão pré-corrida determinística**
nem uma probabilidade calibrada de vitória.
"""
)


# ============================================================
# 1. OBJETIVO E DESENHO EXPERIMENTAL
# ============================================================

st.header("1. Objetivo da modelagem")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Granularidade",
        "Piloto × corrida",
    )

with col2:
    st.metric(
        "Target",
        "Vitória",
    )

with col3:
    st.metric(
        "Features",
        "18",
    )

with col4:
    st.metric(
        "Modelo final",
        "Random Forest",
    )


st.markdown(
    """
### Estratégia de divisão dos dados

Para reduzir risco de vazamento temporal e evitar que
pilotos da mesma corrida fossem distribuídos entre treino
e teste, foi utilizada uma divisão por temporadas.

**Desenvolvimento**

2018, 2019, 2021, 2022 e 2023

- 100 registros;
- 5 corridas;
- 5 vencedores.

**Teste final**

2024 e 2025

- 40 registros;
- 2 corridas;
- 2 vencedores.

O conjunto de teste foi mantido separado da etapa de
desenvolvimento e utilizado somente na avaliação final.
"""
)


# ============================================================
# 2. COMPARAÇÃO DOS MODELOS
# ============================================================

st.header("2. Comparação dos modelos")

st.markdown(
    """
Foram avaliados diferentes algoritmos de classificação,
considerando o forte desbalanceamento do target e a
estrutura dos dados por corrida.

O processo incluiu:

- Regressão Logística;
- Árvore de Decisão;
- Random Forest;
- validação agrupada por corrida;
- otimização de hiperparâmetros;
- comparação por métricas de classificação.
"""
)


if GRAPH_MODEL_COMPARISON.exists():
    st.image(
        str(GRAPH_MODEL_COMPARISON),
        caption="Comparação dos modelos avaliados.",
        use_container_width=True,
    )


if not model_comparison.empty:
    with st.expander(
        "Ver tabela de comparação dos modelos"
    ):
        st.dataframe(
            model_comparison,
            use_container_width=True,
            hide_index=True,
        )


st.info(
    """
O Random Forest foi selecionado como modelo final por
apresentar o melhor equilíbrio observado durante a etapa
de desenvolvimento e tuning.

A escolha não foi baseada apenas em Accuracy, pois essa
métrica pode ser enganosa em um problema com poucos
vencedores.
"""
)

st.subheader("Custo computacional e interpretabilidade")

st.markdown(
    """
Além das métricas preditivas, os modelos também foram comparados
quanto ao custo computacional e à interpretabilidade.

Os tempos abaixo foram medidos em benchmark local com:

- 100 registros do conjunto de desenvolvimento;
- 18 features;
- 10 repetições por modelo;
- mediana utilizada como medida principal.

Os valores representam este ambiente de execução e podem variar
de acordo com hardware, sistema operacional e carga da máquina.
"""
)

benchmark_df = pd.DataFrame(
    {
        "Modelo": [
            "Logistic Regression",
            "Decision Tree",
            "Random Forest",
        ],
        "Treino mediano (ms)": [
            18.72,
            10.58,
            584.97,
        ],
        "Inferência mediana (ms)": [
            5.92,
            4.68,
            68.72,
        ],
        "Interpretabilidade": [
            "Alta",
            "Alta",
            "Média",
        ],
    }
)

st.dataframe(
    benchmark_df,
    use_container_width=True,
    hide_index=True,
)

st.info(
    """
A Decision Tree apresentou o menor custo computacional,
seguida pela Logistic Regression.

O Random Forest apresentou custo superior devido à combinação
de 300 árvores, mas o treinamento permaneceu abaixo de 1 segundo
no dataset atual.

Mesmo com maior custo e interpretabilidade relativa menor,
o Random Forest foi mantido como modelo final por apresentar
o melhor equilíbrio entre F1, Recall e ROC-AUC durante a etapa
de desenvolvimento.
"""
)

# ============================================================
# 3. RESULTADO FINAL DE CLASSIFICAÇÃO
# ============================================================

st.header("3. Avaliação final — classificação")

accuracy = obter_valor(
    final_metrics,
    "accuracy",
)

precision = obter_valor(
    final_metrics,
    "precision",
)

recall = obter_valor(
    final_metrics,
    "recall",
)

f1 = obter_valor(
    final_metrics,
    "f1",
)

roc_auc = obter_valor(
    final_metrics,
    "roc_auc",
)


col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Accuracy",
        percentual(accuracy),
    )

with col2:
    st.metric(
        "Precision",
        percentual(precision),
    )

with col3:
    st.metric(
        "Recall",
        percentual(recall),
    )

with col4:
    st.metric(
        "F1-score",
        percentual(f1),
    )

with col5:
    st.metric(
        "ROC-AUC",
        numero(roc_auc),
    )


st.warning(
    """
### Por que Accuracy = 95% e F1 = 0?

No conjunto de teste existem apenas **2 vencedores em
40 registros**.

Utilizando o threshold padrão de 0,5, o Random Forest
não classificou nenhum piloto como vencedor.

Portanto:

- 38 não vencedores foram classificados corretamente;
- 2 vencedores foram classificados como não vencedores;
- Precision = 0;
- Recall = 0;
- F1-score = 0.

A Accuracy elevada é consequência do forte
desbalanceamento das classes e não deve ser interpretada
isoladamente como evidência de alta capacidade preditiva.
"""
)


# ============================================================
# 4. MATRIZ DE CONFUSÃO E ROC
# ============================================================

st.header("4. Diagnóstico do classificador")

col1, col2 = st.columns(2)

with col1:

    if GRAPH_CONFUSION_MATRIX.exists():
        st.image(
            str(GRAPH_CONFUSION_MATRIX),
            caption="Matriz de confusão.",
            use_container_width=True,
        )

with col2:

    if GRAPH_ROC.exists():
        st.image(
            str(GRAPH_ROC),
            caption="Curva ROC.",
            use_container_width=True,
        )


st.markdown(
    """
O **ROC-AUC de 1,0** mostra que, neste pequeno conjunto
de teste, o modelo conseguiu ordenar os vencedores acima
dos demais pilotos.

Isso não significa que o modelo possui 100% de precisão
preditiva.

O teste contém somente duas corridas independentes,
portanto a evidência ainda é limitada.
"""
)


# ============================================================
# 5. AVALIAÇÃO COMO RANKING
# ============================================================

st.header("5. Avaliação do ranking por corrida")

st.markdown(
    """
Como cada Grande Prêmio possui exatamente um vencedor,
também avaliamos o modelo como um problema de
**ordenamento dos pilotos dentro da própria corrida**.

Essa análise complementa as métricas tradicionais de
classificação.
"""
)


top1_accuracy = obter_valor(
    ranking_metrics,
    "top1_accuracy",
)

top3_accuracy = obter_valor(
    ranking_metrics,
    "top3_accuracy",
)

mean_winner_rank = obter_valor(
    ranking_metrics,
    "mean_winner_rank",
)

mrr = obter_valor(
    ranking_metrics,
    "mrr",
)


col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Top-1",
        percentual(top1_accuracy),
    )

with col2:
    st.metric(
        "Top-3",
        percentual(top3_accuracy),
    )

with col3:
    st.metric(
        "Rank médio vencedor",
        numero(
            mean_winner_rank,
            casas=1,
        ),
    )

with col4:
    st.metric(
        "MRR",
        numero(mrr),
    )


st.caption(
    """
Resultados calculados somente sobre as corridas de
teste de 2024 e 2025. A amostra de duas corridas é
insuficiente para afirmar generalização do desempenho.
"""
)


# ============================================================
# 6. RESULTADO POR CORRIDA
# ============================================================

st.header("6. Resultado nas corridas de teste")


if not race_summary.empty:

    colunas_desejadas = [
        "season",
        "race_name",
        "vencedor_real",
        "top1_modelo",
        "score_vencedor_real",
        "score_top1_modelo",
        "posicao_rank_vencedor_real",
        "acertou_top1",
        "acertou_top3",
    ]

    colunas_existentes = [
        coluna
        for coluna in colunas_desejadas
        if coluna in race_summary.columns
    ]

    tabela_corridas = (
        race_summary[
            colunas_existentes
        ].copy()
    )

    st.dataframe(
        tabela_corridas,
        use_container_width=True,
        hide_index=True,
    )


    st.success(
        """
Nas duas corridas utilizadas como teste final, o vencedor
real ocupou a primeira posição do ranking produzido pelo
modelo.

- 2024: Max Verstappen;
- 2025: Lando Norris.

Esse resultado deve ser apresentado como **2 acertos em
2 corridas de teste**, e não como "100% de precisão do
modelo".
"""
    )

else:

    st.warning(
        "Resumo das corridas de teste não encontrado."
    )


# ============================================================
# 7. SCORE DO MODELO
# ============================================================

st.header("7. Score do modelo × probabilidade")


st.markdown(
    """
O Random Forest produz um valor entre 0 e 1 através de
`predict_proba`.

Entretanto, neste projeto esse valor é apresentado como:

**`score_modelo_vitoria`**

e não como uma probabilidade real de vitória.

Isso ocorre porque não foi realizada uma etapa específica
de calibração probabilística e o conjunto disponível possui
poucos eventos positivos.

O score é utilizado principalmente para comparar e ordenar
pilotos dentro de uma corrida.
"""
)


# ============================================================
# 8. IMPORTÂNCIA DAS FEATURES
# ============================================================

st.header("8. Importância das características")


if GRAPH_FEATURE_IMPORTANCE.exists():
    st.image(
        str(GRAPH_FEATURE_IMPORTANCE),
        caption=(
            "Importância das features no "
            "Random Forest final."
        ),
        use_container_width=True,
    )


st.markdown(
    """
Os fatores com maior importância no modelo final foram:

1. **ritmo representativo da corrida**;
2. **posição de largada (grid)**;
3. **duração mediana dos pit stops convencionais**;
4. **cobertura e disponibilidade de voltas**;
5. **características dos stints e pneus**.

A importância de uma feature indica quanto ela foi usada
pelo modelo para separar os dados.

Ela **não demonstra causalidade**.
"""
)


# ============================================================
# 9. LIMITAÇÕES
# ============================================================

st.header("9. Limitações do modelo")


st.error(
    """
### Limitações que devem acompanhar a interpretação

**Poucos eventos independentes**

O dataset final possui somente 7 corridas e 7 vencedores.

**Teste reduzido**

A avaliação final contém somente 2024 e 2025.

**Desbalanceamento**

Existe apenas um vencedor por corrida.

**Variáveis disponíveis durante a corrida**

Ritmo, pit stops e stints são conhecidos durante ou após
o desenvolvimento do GP.

Por isso, o modelo atual não deve ser apresentado como
um sistema de previsão pré-corrida.

**Associação não é causalidade**

A importância das features mostra associação aprendida
pelo algoritmo, e não prova relações causais.
"""
)


# ============================================================
# 10. CONCLUSÃO
# ============================================================

st.header("10. Conclusão")


st.markdown(
    """
A modelagem mostra que a análise de uma corrida não deve
ser resumida somente à posição de largada.

No histórico analisado, o **ritmo representativo de
corrida** aparece como a característica mais importante
do Random Forest, seguido pelo grid e por fatores ligados
à execução estratégica.

O classificador apresenta limitações no threshold padrão
de 0,5, mas sua capacidade de ordenação mostrou resultado
promissor nas duas corridas reservadas para teste.

Assim, nesta etapa, o maior valor do modelo está em:

- explicar os fatores historicamente associados ao sucesso;
- ordenar pilotos dentro de um mesmo cenário de corrida;
- apoiar análises de cenários;
- fornecer base quantitativa para a análise direcionada
  ao Gabriel Bortoleto.
"""
)


# ============================================================
# 11. DADOS TÉCNICOS
# ============================================================

with st.expander(
    "Ver dados técnicos utilizados nesta página"
):

    st.markdown(
        "#### Métricas finais"
    )

    st.dataframe(
        final_metrics,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown(
        "#### Métricas de ranking"
    )

    st.dataframe(
        ranking_metrics,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown(
        "#### Predições do conjunto de teste"
    )

    st.dataframe(
        final_predictions,
        use_container_width=True,
        hide_index=True,
    )