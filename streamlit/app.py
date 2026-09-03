import streamlit as st
from src.data_loader import load_all_datasets

st.set_page_config(
    page_title="F1 Interlagos Analytics",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏎️ Formula 1 — Interlagos Analytics")
st.subheader("Análise histórica de desempenho, ritmo e estratégia")

st.markdown(
    """
    Aplicação analítica construída a partir da EDA do projeto de Formula 1 —
    Interlagos. O notebook permanece como fonte de verdade da metodologia;
    esta aplicação transforma os principais resultados em uma interface
    interativa e reutilizável.
    """
)

try:
    data = load_all_datasets()
except Exception as exc:
    st.error("Não foi possível carregar os dados do MinIO.")
    st.exception(exc)
    st.stop()

calendario = data["calendario"]
resultados = data["resultados"]
voltas = data["voltas"]
pit_stops = data["pit_stops"]
pneus = data["pneus"]
clima = data["clima"]
driver_mapping = data["driver_mapping"]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Período", f"{int(calendario.season.min())}–{int(calendario.season.max())}")
c2.metric("Corridas", f"{len(calendario):,}")
c3.metric("Pilotos-corrida", f"{len(resultados):,}")
c4.metric("Voltas", f"{len(voltas):,}")
c5.metric("Pit stops", f"{len(pit_stops):,}")

st.divider()

st.markdown("### Principais achados da EDA")

a, b, c = st.columns(3)
a.metric("Spearman ritmo × resultado", "0,721", help="189 pilotos-corrida com ritmo disponível.")
b.metric("Spearman grid × resultado", "0,497", help="202 pilotos-corrida.")
c.metric("Grid × ritmo", "0,657")

st.info(
    """
    **Prioridade descritiva identificada:** ritmo de corrida → posição de
    largada → contexto estratégico de pit stops, pneus e clima.

    Essas associações são históricas e não representam causalidade.
    """
)

st.markdown("### Navegação")
st.markdown(
    """
    Use o menu lateral para explorar:

    - **Visão Geral** — panorama das corridas e vencedores.
    - **Qualidade dos Dados** — cobertura, ausências, duplicidades e integridade.
    - **Corridas e Resultados** — vitórias, pódios, grid e movimentação.
    - **Ritmo de Corrida** — construção do ritmo representativo e sua relação com resultado.
    - **Pit Stops** — quantidade, duração, extremos e contexto.
    - **Pneus e Stints** — compostos, estratégias, stints e tyre life.
    - **Clima** — condições meteorológicas e contexto dos pneus.
    - **Análises Combinadas** — visão conjunta dos fatores.
    - **Estatística** — correlações, ranking e análise de sensibilidade.
    - **Insights** — hipóteses, recomendações e limitações.
    """
)

with st.expander("Fontes e cobertura"):
    st.write(
        "Datasets: calendario, resultados, voltas, pit_stops, pneus, clima e driver_mapping."
    )
    st.write(
        f"Driver mapping: {len(driver_mapping):,} pares FastF1/Jolpica carregados."
    )
    st.write(
        "A temporada 2020 permanece no calendário, mas não possui registros de resultados, "
        "voltas, pit stops, pneus ou clima do recorte de Interlagos utilizado."
    )
