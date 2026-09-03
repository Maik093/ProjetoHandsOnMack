import pandas as pd

def prepare_pitstops(pit_stops, voltas_contexto):
    events = (
        voltas_contexto.loc[
            voltas_contexto["evento_coletivo_extremo"],
            ["season", "round", "lap"]
        ].drop_duplicates()
    )
    df = pit_stops.copy()
    df["pit_duracao_extrema"] = df["duration"] > 60
    df["pit_convencional"] = ~df["pit_duracao_extrema"]
    df = df.merge(
        events.assign(evento_coletivo_extremo=True),
        on=["season", "round", "lap"], how="left"
    )
    df["evento_coletivo_extremo"] = df["evento_coletivo_extremo"].fillna(False).astype(bool)
    return df

def pit_by_season(df):
    return (
        df.groupby("season")
        .agg(
            quantidade=("stop", "count"),
            media=("duration", "mean"),
            mediana=("duration", "median"),
            minimo=("duration", "min"),
            maximo=("duration", "max"),
        ).round(2).reset_index()
    )

def pit_driver_race(df, resultados, pace):
    base = (
        df.groupby(["season", "round", "driver_id"])
        .agg(
            quantidade_pits=("stop", "count"),
            quantidade_pits_convencionais=("pit_convencional", "sum"),
            quantidade_pits_extremos=("pit_duracao_extrema", "sum"),
        ).reset_index()
    )
    conventional = (
        df[df["pit_convencional"]]
        .groupby(["season", "round", "driver_id"])
        .agg(
            duracao_pit_convencional_total=("duration", "sum"),
            duracao_pit_convencional_media=("duration", "mean"),
            duracao_pit_convencional_mediana=("duration", "median"),
            duracao_pit_convencional_maxima=("duration", "max"),
        ).reset_index()
    )
    base = base.merge(conventional, on=["season", "round", "driver_id"], how="left")
    base = base.merge(
        resultados[["season", "round", "driver_id", "grid", "position", "status"]],
        on=["season", "round", "driver_id"], how="left"
    )
    base = base.merge(
        pace[[
            "season", "round", "driver_id", "ritmo_representativo_pct",
            "voltas_analisadas", "amostra_reduzida"
        ]],
        on=["season", "round", "driver_id"], how="left"
    )
    base["posicoes_ganhas"] = base["grid"] - base["position"]
    return base

def quantity_result(df):
    return (
        df[df["position"].notna()]
        .groupby("quantidade_pits")
        .agg(
            observacoes=("driver_id", "size"),
            posicao_final_media=("position", "mean"),
            posicao_final_mediana=("position", "median"),
            posicoes_ganhas_media=("posicoes_ganhas", "mean"),
            posicoes_ganhas_mediana=("posicoes_ganhas", "median"),
        ).round(2).reset_index()
    )

def duration_result(df):
    x = df[
        df["duracao_pit_convencional_mediana"].notna()
        & df["position"].notna()
    ][["duracao_pit_convencional_mediana", "position"]].dropna()
    return {
        "n": len(x),
        "pearson": x["duracao_pit_convencional_mediana"].corr(x["position"], method="pearson"),
        "spearman": x["duracao_pit_convencional_mediana"].corr(x["position"], method="spearman"),
    }

def pit_pace_correlations(df):
    x = df[
        df["ritmo_representativo_pct"].notna()
        & ~df["amostra_reduzida"]
    ]
    rows = []
    for variable in ["quantidade_pits", "duracao_pit_convencional_mediana"]:
        y = x[[variable, "ritmo_representativo_pct"]].dropna()
        rows.append({
            "variavel": variable,
            "n": len(y),
            "pearson": y[variable].corr(y["ritmo_representativo_pct"], method="pearson"),
            "spearman": y[variable].corr(y["ritmo_representativo_pct"], method="spearman"),
        })
    return pd.DataFrame(rows)

def extreme_context(df):
    extreme = df[df["duration"] > 60].copy()
    events = set(
        df.loc[df["evento_coletivo_extremo"], ["season", "round", "lap"]]
        .itertuples(index=False, name=None)
    )
    extreme["evento_mesma_volta"] = extreme.apply(
        lambda r: (r["season"], r["round"], r["lap"]) in events, axis=1
    )
    extreme["evento_volta_seguinte"] = extreme.apply(
        lambda r: (r["season"], r["round"], r["lap"] + 1) in events, axis=1
    )
    extreme["evento_volta_anterior"] = extreme.apply(
        lambda r: (r["season"], r["round"], r["lap"] - 1) in events, axis=1
    )
    return extreme.sort_values("duration", ascending=False)
