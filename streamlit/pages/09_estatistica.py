import streamlit as st
from src.data_loader import load_all_datasets
from src.pace_analysis import build_lap_context, build_representative_pace
from src.pitstop_analysis import prepare_pitstops, pit_driver_race
from src.tyre_analysis import canonical_tyres, stint_validation, strategies
from src.weather_analysis import tyre_weather_context
from src.combined_analysis import build_base
from src.statistical_analysis import spearman_matrix, association_ranking, sensitivity
from src.ui import page_header, season_filter, apply_seasons, dataframe
from src.visualizations import heatmap, horizontal_ranking

page_header("Estatística", "Consolidação de correlações, ranking e sensibilidade.")

data = load_all_datasets()
results, laps, pits = data["resultados"], data["voltas"], data["pit_stops"]
tyres, weather, mapping = data["pneus"], data["clima"], data["driver_mapping"]

seasons = season_filter(results, key="stats_seasons")
results_f = apply_seasons(results, seasons)
laps_f = apply_seasons(laps, seasons)
pits_f = apply_seasons(pits, seasons)
tyres_f = apply_seasons(tyres, seasons)
weather_f = apply_seasons(weather, seasons)
mapping_f = apply_seasons(mapping, seasons)

ctx = build_lap_context(laps_f, pits_f)
_, pace = build_representative_pace(ctx, results_f)
pit_ctx = prepare_pitstops(pits_f, ctx)
pit_driver = pit_driver_race(pit_ctx, results_f, pace)
canon = canonical_tyres(tyres_f, mapping_f)
_, _, tyre_life = stint_validation(canon)
strategies_df, _ = strategies(tyre_life)
weather_context = tyre_weather_context(weather_f, canon)
base = build_base(results_f, pace, pit_driver, strategies_df, weather_context)

matrix = spearman_matrix(base)
ranking = association_ranking(base)
sens = sensitivity(base)

st.plotly_chart(heatmap(matrix, "Matriz de correlação de Spearman"), use_container_width=True)
dataframe(matrix.reset_index(names="variavel"))

st.subheader("Ranking das associações com a posição final")
st.plotly_chart(
    horizontal_ranking(
        ranking, "magnitude", "variavel",
        "Magnitude das associações com o resultado final",
        labels={"magnitude": "|Spearman|", "variavel": "Variável"}
    ),
    use_container_width=True
)
dataframe(ranking)

st.subheader("Análise de sensibilidade")
dataframe(sens)

st.info(
    "A correlação de Spearman é usada como medida de associação monotônica. "
    "O ranking não representa causalidade nem importância causal."
)
