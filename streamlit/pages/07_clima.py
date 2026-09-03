import streamlit as st
from src.data_loader import load_all_datasets
from src.weather_analysis import (
    seasonal_rain, descriptive, seasonal_weather,
    temperature_correlation, tyre_weather_context
)
from src.tyre_analysis import canonical_tyres
from src.ui import page_header, season_filter, apply_seasons, dataframe
from src.visualizations import bar, scatter

page_header("Clima", "Condições meteorológicas e contexto estratégico.")

data = load_all_datasets()
weather, tyres, mapping = data["clima"], data["pneus"], data["driver_mapping"]

seasons = season_filter(weather, key="weather_seasons")
weather_f = apply_seasons(weather, seasons)
tyres_f = apply_seasons(tyres, seasons)
mapping_f = apply_seasons(mapping, seasons)

canon = canonical_tyres(tyres_f, mapping_f)
rain = seasonal_rain(weather_f)
desc = descriptive(weather_f)
seasonal = seasonal_weather(weather_f)
temp = temperature_correlation(weather_f)
context = tyre_weather_context(weather_f, canon)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Observações climáticas", f"{len(weather_f):,}")
c2.metric("Temp. ar mediana", f"{weather_f['air_temp'].median():.1f} °C")
c3.metric("Temp. pista mediana", f"{weather_f['track_temp'].median():.1f} °C")
c4.metric("Spearman ar × pista", f"{temp['spearman']:.3f}")

st.subheader("Chuva por temporada")
st.plotly_chart(
    bar(
        rain, "season", "percentual_com_chuva",
        "Percentual de registros climáticos com chuva",
        labels={"season": "Temporada", "percentual_com_chuva": "Registros com chuva (%)"}
    ),
    use_container_width=True
)
dataframe(rain)

st.subheader("Estatísticas descritivas")
dataframe(desc)

st.subheader("Temperatura do ar × temperatura da pista")
st.plotly_chart(
    scatter(
        weather_f.dropna(subset=["air_temp", "track_temp"]),
        "air_temp", "track_temp",
        "Relação entre temperatura do ar e da pista",
        hover_data=["season"],
        labels={"air_temp": "Temperatura do ar (°C)", "track_temp": "Temperatura da pista (°C)"}
    ),
    use_container_width=True
)
st.caption(
    f"Pearson = {temp['pearson']:.3f}; Spearman = {temp['spearman']:.3f}; n = {temp['n']:,}."
)

st.subheader("Contexto agregado: chuva × pneus")
dataframe(context)

st.warning(
    "Limitação metodológica: weather_time_seconds é relativo à sessão FastF1, enquanto "
    "as voltas Jolpica não possuem timestamp equivalente. Portanto, a aplicação não "
    "afirma causalidade ou alinhamento temporal exato entre clima e volta."
)
