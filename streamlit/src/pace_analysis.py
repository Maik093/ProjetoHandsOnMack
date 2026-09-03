import numpy as np
import pandas as pd

def build_lap_context(voltas, pit_stops):
    mediana_corrida = (
        voltas.groupby(["season", "round"])["lap_time_seconds"]
        .median().reset_index(name="mediana_corrida")
    )
    df = voltas.merge(mediana_corrida, on=["season", "round"], how="left")
    df["delta_mediana_pct"] = (
        df["lap_time_seconds"] / df["mediana_corrida"] - 1
    ) * 100

    pit_laps = (
        pit_stops[["season", "round", "driver_id", "lap"]]
        .drop_duplicates().assign(pit_stop=True)
    )
    df = df.merge(
        pit_laps,
        on=["season", "round", "driver_id", "lap"],
        how="left",
    )
    df["pit_stop"] = df["pit_stop"].fillna(False).astype(bool)

    mediana_por_volta = (
        voltas.groupby(["season", "round", "lap"])["lap_time_seconds"]
        .median().reset_index(name="mediana_volta_corrida")
    )
    df = df.merge(
        mediana_por_volta,
        on=["season", "round", "lap"],
        how="left",
    )
    df["delta_volta_pct"] = (
        df["lap_time_seconds"] / df["mediana_volta_corrida"] - 1
    ) * 100

    pilotos_por_volta = (
        voltas.groupby(["season", "round", "lap"])
        .agg(pilotos_na_volta=("driver_id", "nunique"))
        .reset_index()
    )
    df = df.merge(pilotos_por_volta, on=["season", "round", "lap"], how="left")

    df["delta_contexto_volta_pct"] = (
        df["mediana_volta_corrida"] / df["mediana_corrida"] - 1
    ) * 100

    df["evento_coletivo_extremo"] = df["delta_contexto_volta_pct"] > 100
    df["volta_comparavel"] = (
        (~df["pit_stop"]) & (~df["evento_coletivo_extremo"])
    )
    return df

def build_representative_pace(voltas_contexto, resultados):
    comparable = voltas_contexto[voltas_contexto["volta_comparavel"]].copy()
    reference = (
        comparable.groupby(["season", "round", "lap"])["lap_time_seconds"]
        .median().rename("mediana_volta_comparavel").reset_index()
    )
    comparable = comparable.merge(
        reference, on=["season", "round", "lap"], how="left"
    )
    comparable["delta_ritmo_pct"] = (
        comparable["lap_time_seconds"] / comparable["mediana_volta_comparavel"] - 1
    ) * 100

    pace = (
        comparable.groupby(["season", "round", "driver_id"])
        .agg(
            ritmo_representativo_pct=("delta_ritmo_pct", "median"),
            media_delta_pct=("delta_ritmo_pct", "mean"),
            voltas_analisadas=("lap", "count"),
            melhor_delta_pct=("delta_ritmo_pct", "min"),
            pior_delta_pct=("delta_ritmo_pct", "max"),
        ).reset_index()
    )

    pace = pace.merge(
        resultados[
            ["season", "round", "driver_id", "position", "grid", "laps", "status"]
        ],
        on=["season", "round", "driver_id"], how="left"
    )

    available = (
        voltas_contexto.groupby(["season", "round", "driver_id"])
        .agg(voltas_disponiveis=("lap", "nunique"))
        .reset_index()
    )
    pace = pace.merge(
        available, on=["season", "round", "driver_id"], how="left"
    )
    pace["cobertura_ritmo_pct"] = (
        pace["voltas_analisadas"] / pace["voltas_disponiveis"] * 100
    )
    pace["amostra_reduzida"] = pace["voltas_analisadas"] < 20
    return comparable, pace

def lap_distribution(voltas):
    return voltas["lap_time_seconds"].describe(
        percentiles=[.01, .05, .25, .50, .75, .90, .95, .99]
    )

def lap_bands(voltas):
    bins = [0, 90, 120, 150, 180, 300, 600, float("inf")]
    labels = ["até 90s", "90–120s", "120–150s", "150–180s", "3–5 min", "5–10 min", "10+ min"]
    cats = pd.cut(voltas["lap_time_seconds"], bins=bins, labels=labels, right=False)
    out = cats.value_counts(sort=False).rename("voltas").to_frame()
    out["percentual"] = (out["voltas"] / len(voltas) * 100).round(2)
    return out.reset_index(names="faixa")

def extreme_laps(voltas):
    return (
        voltas[["season", "round", "driver_id", "lap", "lap_time_seconds"]]
        .sort_values("lap_time_seconds", ascending=False).head(20)
    )

def extreme_by_season(voltas):
    return (
        voltas[voltas["lap_time_seconds"] > 180]
        .groupby("season")
        .agg(
            quantidade=("lap_time_seconds", "size"),
            maior_tempo=("lap_time_seconds", "max"),
            pilotos=("driver_id", "nunique"),
        ).reset_index()
        .assign(maior_tempo_min=lambda x: (x["maior_tempo"] / 60).round(2))
    )

def pit_lap_comparison(voltas_contexto):
    return (
        voltas_contexto.groupby("pit_stop")["lap_time_seconds"]
        .agg(quantidade="count", media="mean", mediana="median", minimo="min", maximo="max")
        .round(2).reset_index()
    )

def pace_correlations(pace):
    df = pace[["ritmo_representativo_pct", "position"]].dropna()
    robust = pace[
        pace["ritmo_representativo_pct"].notna()
        & pace["position"].notna()
        & ~pace["amostra_reduzida"]
    ].copy()
    return {
        "all": {
            "n": len(df),
            "pearson": df["ritmo_representativo_pct"].corr(df["position"], method="pearson"),
            "spearman": df["ritmo_representativo_pct"].corr(df["position"], method="spearman"),
        },
        "robust": {
            "n": len(robust),
            "pearson": robust["ritmo_representativo_pct"].corr(robust["position"], method="pearson"),
            "spearman": robust["ritmo_representativo_pct"].corr(robust["position"], method="spearman"),
        },
    }
