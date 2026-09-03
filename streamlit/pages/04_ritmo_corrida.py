import streamlit as st
from src.data_loader import load_all_datasets
from src.pace_analysis import (
    build_lap_context, build_representative_pace,
    lap_distribution, lap_bands, extreme_laps, extreme_by_season,
    pit_lap_comparison, pace_correlations
)
from src.ui import page_header, season_filter, apply_seasons, dataframe
from src.visualizations import scatter, bar, line

page_header("Ritmo de Corrida", "Construção do ritmo representativo e relação com resultado.")

data = load_all_datasets()
voltas, pits, resultados = data["voltas"], data["pit_stops"], data["resultados"]

seasons = season_filter(voltas, key="pace_seasons")
voltas_f = apply_seasons(voltas, seasons)
pits_f = apply_seasons(pits, seasons)
resultados_f = apply_seasons(resultados, seasons)

@st.cache_data(show_spinner="Construindo contexto de ritmo...")
def calculate(voltas, pits, resultados):
    ctx = build_lap_context(voltas, pits)
    comparable, pace = build_representative_pace(ctx, resultados)
    return ctx, comparable, pace

ctx, comparable, pace = calculate(voltas_f, pits_f, resultados_f)
corr = pace_correlations(pace)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Voltas", f"{len(voltas_f):,}")
c2.metric("Voltas comparáveis", f"{len(comparable):,}")
c3.metric("Ritmo × resultado", f"{corr['all']['spearman']:.3f}")
c4.metric("Ritmo robusto × resultado", f"{corr['robust']['spearman']:.3f}")

st.subheader("Distribuição dos tempos de volta")
dist = lap_distribution(voltas_f)
dataframe(dist.rename_axis("estatística").reset_index(name="segundos"))

st.plotly_chart(
    bar(
        lap_bands(voltas_f), "faixa", "voltas",
        "Distribuição dos tempos de volta",
        labels={"faixa": "Faixa", "voltas": "Voltas"}
    ),
    use_container_width=True
)

st.subheader("Investigação dos extremos")
dataframe(extreme_by_season(voltas_f))
with st.expander("20 maiores tempos de volta"):
    dataframe(extreme_laps(voltas_f), height=430)

st.subheader("Impacto dos pit stops")
dataframe(pit_lap_comparison(ctx))

st.subheader("Ritmo representativo")
pace_plot = pace.dropna(subset=["ritmo_representativo_pct", "position"]).copy()
st.plotly_chart(
    scatter(
        pace_plot, "ritmo_representativo_pct", "position",
        "Ritmo representativo × posição final",
        color="season",
        hover_data=["driver_id", "voltas_analisadas", "cobertura_ritmo_pct"],
        labels={
            "ritmo_representativo_pct": "Ritmo relativo (%)",
            "position": "Posição final",
            "season": "Temporada",
        }
    ).update_yaxes(autorange="reversed"),
    use_container_width=True
)

top = (
    pace[pace["voltas_analisadas"] >= 20]
    .nsmallest(10, "ritmo_representativo_pct")
    .copy()
)
top["piloto_ano"] = top["driver_id"] + " — " + top["season"].astype(str)
st.plotly_chart(
    bar(
        top.sort_values("ritmo_representativo_pct", ascending=True),
        "ritmo_representativo_pct", "piloto_ano",
        "Top 10 desempenhos relativos em ritmo",
        labels={"ritmo_representativo_pct": "Ritmo relativo (%)", "piloto_ano": "Piloto — temporada"}
    ),
    use_container_width=True
)

st.info(
    f"Na amostra com ritmo disponível, Spearman = {corr['all']['spearman']:.3f} "
    f"(n={corr['all']['n']}). Na amostra robusta, Spearman = {corr['robust']['spearman']:.3f} "
    f"(n={corr['robust']['n']})."
)
