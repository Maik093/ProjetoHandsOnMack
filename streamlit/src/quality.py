import pandas as pd

GRANULARIDADES = {
    "calendario": "1 registro por corrida",
    "resultados": "1 piloto por corrida",
    "voltas": "1 piloto por volta",
    "pit_stops": "1 registro por pit stop realizado por piloto",
    "pneus": "1 piloto por volta/sessão",
    "clima": "1 medição meteorológica por instante",
    "driver_mapping": "1 piloto FastF1 por temporada",
}

LOGICAL_KEYS = {
    "calendario": ["season", "round"],
    "resultados": ["season", "round", "driver_id"],
    "voltas": ["season", "round", "driver_id", "lap"],
    "pit_stops": ["season", "round", "driver_id", "stop"],
    "driver_mapping": ["season", "fastf1_driver_id"],
}

def dataset_summary(datasets):
    rows = []
    for name, df in datasets.items():
        rows.append({
            "dataset": name,
            "registros": len(df),
            "colunas": len(df.columns),
            "granularidade": GRANULARIDADES.get(name, ""),
        })
    return pd.DataFrame(rows).sort_values("registros", ascending=False)

def missing_summary(datasets):
    rows = []
    for name, df in datasets.items():
        for col in df.columns:
            n = int(df[col].isna().sum())
            if n:
                rows.append({
                    "dataset": name,
                    "coluna": col,
                    "nulos": n,
                    "percentual": round(n / len(df) * 100, 2),
                })
    return pd.DataFrame(rows).sort_values(
        ["dataset", "percentual"], ascending=[True, False]
    )

def duplicate_summary(datasets):
    rows = []
    for name, key in LOGICAL_KEYS.items():
        df = datasets[name]
        groups = (
            df.groupby(key, dropna=False).size()
            .reset_index(name="quantidade")
            .query("quantidade > 1")
        )
        rows.append({
            "dataset": name,
            "chave_logica": " + ".join(key),
            "grupos_duplicados": len(groups),
            "registros_envolvidos": int(groups["quantidade"].sum()) if not groups.empty else 0,
        })

    pneus = datasets["pneus"]
    key = ["season", "session", "driver_id", "lap_number"]
    groups = (
        pneus.groupby(key, dropna=False).size()
        .reset_index(name="quantidade")
        .query("quantidade > 1")
    )
    rows.append({
        "dataset": "pneus",
        "chave_logica": "season + session + driver_id + lap_number",
        "grupos_duplicados": len(groups),
        "registros_envolvidos": int(groups["quantidade"].sum()) if not groups.empty else 0,
    })
    return pd.DataFrame(rows)

def referential_integrity(datasets):
    calendario = datasets["calendario"]
    resultados = datasets["resultados"]
    voltas = datasets["voltas"]
    pits = datasets["pit_stops"]
    pneus = datasets["pneus"]
    mapping = datasets["driver_mapping"]

    checks = [
        ("resultados → calendario", resultados, ["season", "round"], calendario, ["season", "round"]),
        ("voltas → resultados", voltas, ["season", "round", "driver_id"],
         resultados, ["season", "round", "driver_id"]),
        ("pit_stops → resultados", pits, ["season", "round", "driver_id"],
         resultados, ["season", "round", "driver_id"]),
        ("pneus → driver_mapping", pneus, ["season", "driver_id"],
         mapping, ["season", "fastf1_driver_id"]),
    ]

    rows = []
    for name, src, skey, dst, dkey in checks:
        left = src[skey].drop_duplicates()
        right = dst[dkey].drop_duplicates()
        merged = left.merge(
            right, left_on=skey, right_on=dkey, how="left", indicator=True
        )
        orphans = int((merged["_merge"] == "left_only").sum())
        rows.append({
            "relacionamento": name,
            "registros_origem": len(src),
            "orfãos": orphans,
            "cobertura_pct": round((1 - orphans / len(src)) * 100, 2),
        })
    return pd.DataFrame(rows)

def temporal_coverage(datasets):
    rows = []
    for name, df in datasets.items():
        seasons = sorted(df["season"].dropna().unique())
        rows.append({
            "dataset": name,
            "temporada_inicial": int(min(seasons)),
            "temporada_final": int(max(seasons)),
            "qtd_temporadas": len(seasons),
            "temporadas_disponiveis": ", ".join(map(str, seasons)),
        })
    return pd.DataFrame(rows)

def race_time_analysis(resultados):
    nulos = (
        resultados[resultados["race_time"].isna()]
        .groupby("status").size()
        .reset_index(name="quantidade")
        .sort_values("quantidade", ascending=False)
    )
    return nulos

def fastest_lap_analysis(resultados):
    cols = [
        "fastest_lap_rank", "fastest_lap", "fastest_lap_time",
        "fastest_lap_time_millis", "fastest_lap_average_speed",
        "fastest_lap_average_speed_unit"
    ]
    return resultados[cols].isna().sum().rename("nulos").to_frame()

def practice_missing_by_season(calendario):
    return (
        calendario.groupby("season")
        .agg(
            corridas=("round", "count"),
            second_practice_nulos=("second_practice_date", lambda x: x.isna().sum()),
            third_practice_nulos=("third_practice_date", lambda x: x.isna().sum()),
        )
        .reset_index()
    )

PROBLEMAS_QUALIDADE = pd.DataFrame([
    {
        "problema": "Paginação dos pit stops",
        "impacto": "Quantidade de registros inferior ao esperado",
        "tratamento": "Implementação de paginação na API Jolpica",
        "resultado": "512 registros e validação OK",
    },
    {
        "problema": "Identificadores de pilotos incompatíveis",
        "impacto": "FastF1 e Jolpica não permitem relacionamento direto",
        "tratamento": "Criação da dimensão driver_mapping",
        "resultado": "137/137 pares mapeados",
    },
    {
        "problema": "Registro FastF1 inválido para 2020",
        "impacto": "GP da Turquia identificado incorretamente como Interlagos",
        "tratamento": "Validação do evento e remoção dos registros inválidos",
        "resultado": "2020 removido de pneus e clima",
    },
    {
        "problema": "Cobertura pneus × voltas",
        "impacto": "12 registros de pneus sem volta correspondente",
        "tratamento": "Investigação dos registros sem correspondência",
        "resultado": "8.803/8.815 registros relacionados (99,86%)",
    },
    {
        "problema": "Alinhamento temporal clima × voltas",
        "impacto": "Fontes não possuem chave temporal diretamente compatível",
        "tratamento": "Relacionamento temporal estimado apenas na camada analítica",
        "resultado": "Não persistido na Silver",
    },
    {
        "problema": "Valores ausentes",
        "impacto": "Campos específicos apresentam valores nulos",
        "tratamento": "Análise contextual sem imputação automática",
        "resultado": "Ausências documentadas e preservadas",
    },
    {
        "problema": "Registros duplicados",
        "impacto": "Possível alteração de métricas e relacionamentos",
        "tratamento": "Validação pelas chaves lógicas",
        "resultado": "Nenhuma duplicidade identificada",
    },
    {
        "problema": "Integridade referencial",
        "impacto": "Possibilidade de registros órfãos",
        "tratamento": "Validação dos principais relacionamentos",
        "resultado": "100% de cobertura",
    },
])
