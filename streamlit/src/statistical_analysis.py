import pandas as pd

VARIABLES = [
    "grid",
    "ritmo_representativo_pct",
    "quantidade_pits",
    "duracao_pit_convencional_mediana",
    "quantidade_stints",
    "compostos_distintos",
    "position",
]

LABELS = {
    "grid": "Posição de largada",
    "ritmo_representativo_pct": "Ritmo representativo",
    "quantidade_pits": "Quantidade de pit stops",
    "duracao_pit_convencional_mediana": "Duração mediana do pit convencional",
    "quantidade_stints": "Quantidade de stints",
    "compostos_distintos": "Compostos distintos",
    "position": "Posição final",
}

def spearman_matrix(base):
    return base[VARIABLES].corr(method="spearman").round(3)

def association_ranking(base):
    rows = []
    for var in VARIABLES[:-1]:
        pairs = base[[var, "position"]].dropna()
        rows.append({
            "variavel": LABELS[var],
            "variavel_codigo": var,
            "observacoes": len(pairs),
            "spearman": pairs[var].corr(pairs["position"], method="spearman"),
        })
    out = pd.DataFrame(rows)
    out["magnitude"] = out["spearman"].abs()
    return out.sort_values("magnitude", ascending=False).reset_index(drop=True)

def sensitivity(base):
    available = base[
        base["ritmo_representativo_pct"].notna()
        & base["position"].notna()
    ].copy()
    robust = available[available["amostra_reduzida"] == 1].copy()

    rows = []
    for label, df in [
        ("Ritmo disponível", available),
        ("Ritmo robusto (>= 20 voltas comparáveis)", robust),
    ]:
        rows.append({
            "amostra": label,
            "observacoes": len(df),
            "spearman_grid_resultado": df["grid"].corr(df["position"], method="spearman"),
            "spearman_ritmo_resultado": df["ritmo_representativo_pct"].corr(
                df["position"], method="spearman"
            ),
        })
    return pd.DataFrame(rows).round(3)
