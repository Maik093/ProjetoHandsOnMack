import streamlit as st
from src.data_loader import load_all_datasets
from src.pace_analysis import build_lap_context, build_representative_pace
from src.pitstop_analysis import prepare_pitstops, pit_driver_race
from src.tyre_analysis import canonical_tyres, stint_validation, strategies
from src.weather_analysis import tyre_weather_context
from src.combined_analysis import build_base, comparable_performance, pit_summary, season_context
from src.ui import page_header, season_filter, apply_seasons, dataframe
from src.visualizations import scatter, bar

page_header("Análises Combinadas", "Grid, ritmo, resultado e contexto estratégico.")

data = load_all_datasets()
results = data["resultados"]
laps = data["voltas"]
pits = data["pit_stops"]
tyres = data["pneus"]
weather = data["clima"]
mapping = data["driver_mapping"]

seasons = season_filter(results, key="combined_seasons")
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
perf = comparable_performance(base)
pits_summary = pit_summary(perf)
season_summary = season_context(base)

c1, c2, c3 = st.columns(3)
c1.metric("Pilotos-corrida", len(base))
c2.metric("Amostra robusta", len(perf))
c3.metric("Grid × ritmo", f"{perf['grid'].corr(perf['ritmo_representativo_pct'], method='spearman'):.3f}")

st.subheader("Grid × ritmo × resultado")
st.plotly_chart(
    scatter(
        perf, "grid", "ritmo_representativo_pct",
        "Posição de largada × ritmo representativo",
        color="position",
        hover_data=["season", "round", "driver_id"],
        labels={
            "grid": "Posição de largada",
            "ritmo_representativo_pct": "Ritmo relativo (%)",
            "position": "Posição final",
        }
    ),
    use_container_width=True
)

st.subheader("Pit stops no contexto do desempenho")
dataframe(pits_summary)

st.subheader("Contexto por temporada")
dataframe(season_summary)

st.info(
    "Clima e pneus são apresentados como contexto estratégico. O notebook evita "
    "usar o clima como variável independente na matriz piloto-corrida porque seus "
    "valores estão agregados por temporada/corrida e seriam repetidos para os pilotos."
)
