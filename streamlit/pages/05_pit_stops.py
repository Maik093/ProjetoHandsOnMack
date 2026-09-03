import streamlit as st
from src.data_loader import load_all_datasets
from src.pace_analysis import build_lap_context, build_representative_pace
from src.pitstop_analysis import (
    prepare_pitstops, pit_by_season, pit_driver_race,
    quantity_result, duration_result, pit_pace_correlations, extreme_context
)
from src.ui import page_header, season_filter, apply_seasons, dataframe
from src.visualizations import bar, scatter

page_header("Pit Stops", "Quantidade, duração, extremos e relação com desempenho.")

data = load_all_datasets()
pits, laps, results = data["pit_stops"], data["voltas"], data["resultados"]
seasons = season_filter(pits, key="pit_seasons")

pits_f, laps_f, results_f = apply_seasons(pits, seasons), apply_seasons(laps, seasons), apply_seasons(results, seasons)

ctx = build_lap_context(laps_f, pits_f)
_, pace = build_representative_pace(ctx, results_f)
pit_ctx = prepare_pitstops(pits_f, ctx)
driver_race = pit_driver_race(pit_ctx, results_f, pace)

duration = duration_result(driver_race)
pit_pace = pit_pace_correlations(driver_race)

c1, c2, c3 = st.columns(3)
c1.metric("Pit stops", f"{len(pit_ctx):,}")
c2.metric("Pits > 60 s", int((pit_ctx["duration"] > 60).sum()))
c3.metric("Duração × resultado", f"{duration['spearman']:.3f}")

st.subheader("Quantidade e duração por temporada")
season = pit_by_season(pit_ctx)
st.plotly_chart(
    bar(season, "season", "quantidade", "Quantidade de pit stops por temporada",
        labels={"season": "Temporada", "quantidade": "Pit stops"}),
    use_container_width=True
)
dataframe(season)

st.subheader("Quantidade de pit stops × resultado")
qr = quantity_result(driver_race)
st.plotly_chart(
    bar(qr, "quantidade_pits", "posicao_final_mediana",
        "Posição final mediana por quantidade de pit stops",
        labels={"quantidade_pits": "Pit stops", "posicao_final_mediana": "Posição final mediana"}),
    use_container_width=True
)
dataframe(qr)

st.subheader("Duração convencional × resultado")
d = driver_race.dropna(subset=["duracao_pit_convencional_mediana", "position"])
st.plotly_chart(
    scatter(
        d, "duracao_pit_convencional_mediana", "position",
        "Duração mediana do pit convencional × posição final",
        hover_data=["season", "round", "driver_id"],
        labels={"duracao_pit_convencional_mediana": "Duração mediana (s)", "position": "Posição final"}
    ).update_yaxes(autorange="reversed"),
    use_container_width=True
)

st.subheader("Pits extremos e eventos coletivos")
extreme = extreme_context(pit_ctx)
st.write(
    f"{len(extreme)} pit stops possuem duração superior a 60 segundos."
)
dataframe(extreme.head(50), height=450)

st.subheader("Pit stops × ritmo")
dataframe(pit_pace)

st.warning(
    "O notebook preserva os extremos. Durações muito elevadas podem refletir "
    "esperas, interrupções e eventos coletivos; não devem ser interpretadas automaticamente "
    "como baixa eficiência operacional."
)
