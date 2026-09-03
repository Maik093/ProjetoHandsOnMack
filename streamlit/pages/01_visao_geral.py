import streamlit as st
from src.data_loader import load_all_datasets
from src.race_analysis import race_overview, driver_podiums, winners, winner_grid_summary
from src.ui import page_header, dataframe
from src.visualizations import bar

page_header("Visão Geral", "Panorama histórico das corridas de Interlagos.")

data = load_all_datasets()
resultados, calendario = data["resultados"], data["calendario"]

overview = race_overview(resultados)
wins = winners(resultados)
podiums = driver_podiums(resultados)
grid_summary = winner_grid_summary(wins)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Corridas no calendário", f"{len(calendario):,}")
c2.metric("Corridas com resultados", f"{len(overview):,}")
c3.metric("Vitórias analisadas", f"{len(wins):,}")
c4.metric("Pilotos com pódio", f"{(podiums['podios'] > 0).sum():,}")

st.plotly_chart(
    bar(podiums.head(10), "driver_id", "podios",
        "Top 10 pilotos por pódios em Interlagos",
        labels={"driver_id": "Piloto", "podios": "Pódios"}),
    use_container_width=True
)

left, right = st.columns(2)
with left:
    st.subheader("Vencedores por temporada")
    dataframe(wins)
with right:
    st.subheader("Posição de largada dos vencedores")
    st.plotly_chart(
        bar(
            grid_summary, "criterio", "vitorias",
            "Vitórias por faixa de posição de largada",
            labels={"criterio": "Critério", "vitorias": "Vitórias"},
            text="vitorias"
        ),
        use_container_width=True
    )

st.caption("Achado do notebook: 70% das vitórias partiram da pole e 80% da primeira fila.")
