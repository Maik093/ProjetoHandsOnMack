import pandas as pd

def race_overview(resultados):
    return (
        resultados.groupby(["season", "round"])
        .agg(
            pilotos=("driver_id", "nunique"),
            total_voltas_pilotos=("laps", "sum"),
            maior_numero_voltas=("laps", "max"),
        )
        .reset_index()
    )

def driver_podiums(resultados):
    return (
        resultados.assign(
            vitoria=resultados["position"].eq(1),
            podio=resultados["position"].isin([1, 2, 3]),
        )
        .groupby("driver_id")
        .agg(vitorias=("vitoria", "sum"), podios=("podio", "sum"))
        .sort_values(["podios", "vitorias"], ascending=False)
        .reset_index()
    )

def winners(resultados):
    return (
        resultados.loc[
            resultados["position"] == 1,
            ["season", "driver_id", "constructor_id", "grid", "laps", "status"],
        ]
        .sort_values("season")
        .reset_index(drop=True)
    )

def winner_grid_summary(winners_df):
    df = winners_df.copy()
    return pd.DataFrame({
        "criterio": ["Pole position", "Primeira fila", "Top 3", "Top 5", "Fora do Top 5"],
        "vitorias": [
            (df["grid"] == 1).sum(),
            (df["grid"] <= 2).sum(),
            (df["grid"] <= 3).sum(),
            (df["grid"] <= 5).sum(),
            (df["grid"] > 5).sum(),
        ],
    }).assign(
        percentual=lambda x: (x["vitorias"] / len(df) * 100).round(1)
    )

def grid_analysis(resultados):
    df = resultados.loc[
        (resultados["grid"] > 0) & resultados["position"].notna(),
        ["season", "driver_id", "grid", "position", "status"],
    ].copy()
    df["posicoes_ganhas"] = df["grid"] - df["position"]
    return df

def grid_correlations(df):
    pairs = df[["grid", "position"]].dropna()
    return {
        "pearson": pairs["grid"].corr(pairs["position"], method="pearson"),
        "spearman": pairs["grid"].corr(pairs["position"], method="spearman"),
        "n": len(pairs),
    }

def movement_summary(df):
    return pd.DataFrame({
        "metrica": [
            "Ganhou posições", "Manteve posição", "Perdeu posições",
            "Ganhou 5+ posições", "Ganhou 10+ posições"
        ],
        "pilotos": [
            (df["posicoes_ganhas"] > 0).sum(),
            (df["posicoes_ganhas"] == 0).sum(),
            (df["posicoes_ganhas"] < 0).sum(),
            (df["posicoes_ganhas"] >= 5).sum(),
            (df["posicoes_ganhas"] >= 10).sum(),
        ],
    }).assign(
        percentual=lambda x: (x["pilotos"] / len(df) * 100).round(1)
    )
