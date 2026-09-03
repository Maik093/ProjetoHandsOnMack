import streamlit as st
from src.data_loader import load_all_datasets
from src.pace_analysis import build_lap_context
from src.tyre_analysis import (
    canonical_tyres, stint_validation, compound_distribution,
    compound_by_season, stint_summary, strategies, tyre_rhythm,
    tyre_life_rhythm, within_stint
)
from src.ui import page_header, season_filter, apply_seasons, dataframe
from src.visualizations import bar, line, scatter

page_header("Pneus e Stints", "Compostos, estratégias, duração dos stints e tyre life.")

data = load_all_datasets()
tyres, mapping = data["pneus"], data["driver_mapping"]
laps, pits = data["voltas"], data["pit_stops"]

seasons = season_filter(tyres, key="tyre_seasons")
tyres_f = apply_seasons(tyres, seasons)
mapping_f = apply_seasons(mapping, seasons)
laps_f = apply_seasons(laps, seasons)
pits_f = apply_seasons(pits, seasons)

canon = canonical_tyres(tyres_f, mapping_f)
ctx = build_lap_context(laps_f, pits_f)
comp, continuity, tyre_life = stint_validation(canon)
dist = compound_distribution(canon)
season_comp = compound_by_season(canon)
by_driver, freq = strategies(tyre_life)
merged, comparable = tyre_rhythm(canon, ctx)
rhythm_comp = tyre_rhythm(canon, ctx)[1]
rhythm_comp_summary = (
    comparable.groupby("compound")
    .agg(
        voltas=("lap_number", "size"),
        pilotos=("jolpica_driver_id", "nunique"),
        delta_mediano_pct=("delta_contexto_volta_pct", "median"),
        delta_medio_pct=("delta_contexto_volta_pct", "mean"),
    ).round(3).reset_index().sort_values("delta_mediano_pct")
)
life_rhythm = tyre_life_rhythm(comparable)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Registros de pneus", f"{len(canon):,}")
c2.metric("Stints", f"{len(tyre_life):,}")
c3.metric("Stints com >1 composto", int((comp["quantidade_compostos"] > 1).sum()))
c4.metric("Lacunas de stint", int((continuity["voltas_ausentes"] > 0).sum()))

st.subheader("Participação dos compostos")
st.plotly_chart(
    bar(dist, "compound", "percentual", "Participação dos compostos nos registros de volta",
        labels={"compound": "Composto", "percentual": "Participação (%)"}),
    use_container_width=True
)
dataframe(dist)

st.subheader("Compostos por temporada")
pivot = season_comp.pivot(index="season", columns="compound", values="percentual_temporada").fillna(0).reset_index()
long = pivot.melt(id_vars="season", var_name="compound", value_name="percentual")
st.plotly_chart(
    bar(long, "season", "percentual", "Participação dos compostos por temporada",
        color="compound", labels={"season": "Temporada", "percentual": "%", "compound": "Composto"}),
    use_container_width=True
)

st.subheader("Duração dos stints")
summary = stint_summary(tyre_life)
dataframe(summary)

st.subheader("Estratégias por piloto")
dataframe(by_driver.head(50), height=450)

st.subheader("Ritmo relativo por composto")
st.plotly_chart(
    bar(
        rhythm_comp_summary, "compound", "delta_mediano_pct",
        "Ritmo relativo mediano por composto",
        labels={"compound": "Composto", "delta_mediano_pct": "Delta mediano (%)"}
    ),
    use_container_width=True
)
dataframe(rhythm_comp_summary)

st.subheader("Idade do pneu × ritmo")
st.plotly_chart(
    line(
        life_rhythm.sort_values("faixa_tyre_life"),
        "faixa_tyre_life", "delta_mediano_pct",
        "Ritmo relativo por faixa de tyre life",
        color="compound",
        labels={"faixa_tyre_life": "Tyre life", "delta_mediano_pct": "Delta mediano (%)"}
    ),
    use_container_width=True
)
dataframe(life_rhythm, height=430)

st.warning(
    "Tyre life representa a idade acumulada do pneu. Não deve ser interpretada automaticamente "
    "como quantidade observada de voltas do stint."
)
