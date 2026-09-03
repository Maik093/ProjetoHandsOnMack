import streamlit as st
from src.data_loader import load_all_datasets
from src.race_analysis import winners, driver_podiums, grid_analysis, grid_correlations, movement_summary
from src.ui import page_header, season_filter, apply_seasons, dataframe
from src.visualizations import scatter, bar

page_header("Corridas e Resultados", "Vitórias, pódios, grid, resultado e movimentação.")

data = load_all_datasets()
resultados = data["resultados"]

seasons = season_filter(resultados, key="race_seasons")
df = apply_seasons(resultados, seasons)

wins = winners(df)
podiums = driver_podiums(df)
grid = grid_analysis(df)
corr = grid_correlations(grid)
movement = movement_summary(grid)

c1, c2, c3 = st.columns(3)
c1.metric("Vitórias", len(wins))
c2.metric("Spearman grid × resultado", f"{corr['spearman']:.3f}")
c3.metric("Observações", corr["n"])

st.subheader("Vencedores")
dataframe(wins)

st.subheader("Desempenho por piloto")
dataframe(podiums.head(15))

st.subheader("Grid × posição final")
st.plotly_chart(
    scatter(
        grid, "grid", "position",
        "Relação entre posição de largada e resultado final",
        hover_data=["season", "driver_id", "status"],
        labels={"grid": "Posição de largada", "position": "Posição final"}
    ).update_yaxes(autorange="reversed"),
    use_container_width=True
)

a, b = st.columns(2)
with a:
    st.metric("Pearson", f"{corr['pearson']:.3f}")
    st.metric("Spearman", f"{corr['spearman']:.3f}")
with b:
    st.subheader("Movimentação")
    dataframe(movement)

st.caption("A posição de largada é uma vantagem relevante, mas não determina isoladamente o resultado.")
