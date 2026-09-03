import pandas as pd

def build_base(resultados, pace, pit_driver, strategies_df, climate_context):
    base = resultados[
        ["season", "round", "driver_id", "grid", "position", "status"]
    ].copy()
    base["position"] = pd.to_numeric(base["position"], errors="coerce")
    base["grid"] = pd.to_numeric(base["grid"], errors="coerce")

    base = base.merge(
        pace[
            ["season", "round", "driver_id", "ritmo_representativo_pct",
             "voltas_analisadas", "amostra_reduzida"]
        ],
        on=["season", "round", "driver_id"], how="left", validate="one_to_one"
    )

    pits = pit_driver[
        ["season", "round", "driver_id", "quantidade_pits",
         "quantidade_pits_extremos", "duracao_pit_convencional_mediana"]
    ].drop_duplicates(["season", "round", "driver_id"])

    base = base.merge(
        pits, on=["season", "round", "driver_id"], how="left", validate="one_to_one"
    )

    for col in ["quantidade_pits", "quantidade_pits_extremos"]:
        base[col] = base[col].fillna(0).astype(int)

    strategy = strategies_df[
        ["season", "jolpica_driver_id", "quantidade_stints", "compostos_distintos"]
    ].rename(columns={"jolpica_driver_id": "driver_id"}).drop_duplicates(
        ["season", "driver_id"]
    )

    base = base.merge(
        strategy, on=["season", "driver_id"], how="left", validate="many_to_one"
    )

    climate = climate_context[
        ["season", "percentual_com_chuva", "pct_composto_molhado"]
    ].drop_duplicates("season")

    base = base.merge(
        climate, on="season", how="left", validate="many_to_one"
    )

    base["posicoes_ganhas"] = base["grid"] - base["position"]
    base["top3"] = base["position"].le(3)
    base["top10"] = base["position"].le(10)
    return base

def comparable_performance(base):
    return base[
        base["position"].notna()
        & base["grid"].notna()
        & base["ritmo_representativo_pct"].notna()
        & base["amostra_reduzida"].eq(False)
    ].copy()

def pit_summary(base):
    return (
        base.groupby("quantidade_pits")
        .agg(
            pilotos_corrida=("driver_id", "size"),
            posicao_final_mediana=("position", "median"),
            ritmo_mediano_pct=("ritmo_representativo_pct", "median"),
            posicoes_ganhas_mediana=("posicoes_ganhas", "median"),
        ).round(3).reset_index()
    )

def season_context(base):
    context = base[
        ["season", "percentual_com_chuva", "pct_composto_molhado"]
    ].drop_duplicates().sort_values("season")
    performance = (
        base[base["position"].notna()]
        .groupby("season")
        .agg(
            pilotos_corrida=("driver_id", "size"),
            grid_mediano=("grid", "median"),
            posicoes_ganhas_mediana=("posicoes_ganhas", "median"),
            ritmo_mediano_pct=("ritmo_representativo_pct", "median"),
            pits_mediana=("quantidade_pits", "median"),
        ).round(3).reset_index()
    )
    return performance.merge(context, on="season", how="left", validate="one_to_one")
