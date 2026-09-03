import streamlit as st
from src.ui import page_header

page_header("Insights e Recomendações", "Síntese das evidências da EDA.")

st.markdown("## Hipóteses e evidências")

cards = [
    (
        "Hipótese 1 — Posição de largada",
        "SUSTENTADA",
        "Spearman grid × resultado = 0,497 na amostra de 202 pilotos-corrida; "
        "70% das vitórias partiram da pole e 80% da primeira fila."
    ),
    (
        "Hipótese 2 — Ritmo de corrida",
        "FORTEMENTE SUSTENTADA",
        "Spearman ritmo × resultado = 0,721 com ritmo disponível e 0,735 na "
        "amostra robusta de 183 pilotos-corrida."
    ),
    (
        "Hipótese 3 — Grid × ritmo",
        "SUSTENTADA",
        "Spearman = 0,657 na matriz consolidada; aproximadamente 0,680 na amostra robusta."
    ),
    (
        "Hipótese 4 — Quantidade de pit stops",
        "NÃO SUSTENTADA ISOLADAMENTE",
        "Spearman quantidade de pits × resultado = -0,176."
    ),
    (
        "Hipótese 5 — Duração do pit",
        "FRACA",
        "Spearman duração mediana do pit convencional × resultado = 0,212."
    ),
]

for title, status, evidence in cards:
    with st.container(border=True):
        st.markdown(f"### {title}")
        st.write(f"**Evidência:** {status}")
        st.write(evidence)

st.markdown("## Recomendações estratégicas")

recommendations = [
    ("1. Maximizar a competitividade em ritmo de corrida",
     "Priorizar decisões que favoreçam a manutenção de ritmo competitivo ao longo da corrida."),
    ("2. Buscar uma posição de largada competitiva",
     "Tratar a classificação como etapa relevante sem comprometer o acerto para o ritmo de corrida."),
    ("3. Não definir previamente uma quantidade ideal de pit stops",
     "Usar uma estratégia adaptativa, considerando pneus, ritmo, clima e acontecimentos da prova."),
    ("4. Avaliar a eficiência das paradas dentro do contexto",
     "Separar paradas convencionais de eventos excepcionais antes de avaliar eficiência operacional."),
    ("5. Adaptar a estratégia de pneus",
     "Não há evidência de um composto ou sequência universalmente superior em Interlagos."),
    ("6. Tratar o clima como gatilho estratégico",
     "2024 ilustra como chuva e pneus intermediários/molhados podem mudar o contexto da prova."),
]

for title, text in recommendations:
    st.markdown(f"**{title}**")
    st.write(text)

st.markdown("## Conclusão")
st.success(
    """
    **Ritmo de corrida → posição de largada → contexto estratégico de pit stops,
    pneus e clima.**

    Essa hierarquia é descritiva e associativa. Ela não constitui uma fórmula
    determinística de vitória.
    """
)

st.markdown("## Limitações")
for item in [
    "Cobertura histórica desigual entre datasets.",
    "2020 removido das fontes FastF1 por inconsistência com Interlagos.",
    "weather_time_seconds não possui timestamp equivalente direto nas voltas Jolpica.",
    "Tyre life é idade acumulada do pneu.",
    "Eventos coletivos extremos foram preservados, não apagados.",
    "Correlações não demonstram causalidade.",
]:
    st.write("• " + item)

st.markdown("## Próximos passos")
st.write(
    "A EDA recomenda uma camada Gold analítica, feature engineering e modelagem. "
    "Antes de ML, deve-se definir o momento da previsão para evitar leakage: "
    "variáveis observadas durante a corrida não devem entrar em um modelo que "
    "pretenda prever o resultado antes da largada."
)
