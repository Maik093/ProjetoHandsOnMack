import streamlit as st
from src.data_loader import load_all_datasets
from src.quality import (
    dataset_summary, missing_summary, duplicate_summary,
    referential_integrity, temporal_coverage, race_time_analysis,
    fastest_lap_analysis, PROBLEMAS_QUALIDADE
)
from src.ui import page_header, dataframe

page_header("Qualidade dos Dados", "Validações e limitações documentadas na EDA.")

data = load_all_datasets()

summary = dataset_summary(data)
missing = missing_summary(data)
duplicates = duplicate_summary(data)
integrity = referential_integrity(data)
temporal = temporal_coverage(data)
race_time = race_time_analysis(data["resultados"])
fastest = fastest_lap_analysis(data["resultados"])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Datasets", len(data))
c2.metric("Nulos identificados", int(missing["nulos"].sum()) if not missing.empty else 0)
c3.metric("Grupos duplicados", int(duplicates["grupos_duplicados"].sum()))
c4.metric("Relacionamentos", len(integrity))

st.subheader("Visão geral dos datasets")
dataframe(summary)

st.subheader("Integridade referencial")
dataframe(integrity)
st.caption("Na EDA, os principais relacionamentos apresentaram 100% de cobertura.")

st.subheader("Cobertura temporal")
dataframe(temporal)

with st.expander("Valores ausentes"):
    dataframe(missing if not missing.empty else summary.iloc[0:0], height=420)

with st.expander("race_time — ausência por status"):
    dataframe(race_time)

with st.expander("fastest_lap — campos ausentes"):
    dataframe(fastest)

with st.expander("Duplicidades"):
    dataframe(duplicates)

st.subheader("Problemas identificados e tratamentos")
dataframe(PROBLEMAS_QUALIDADE, height=430)

st.warning(
    "A temporada 2020 foi removida das análises FastF1 porque os registros recuperados "
    "correspondiam ao GP da Turquia, e não a Interlagos."
)
