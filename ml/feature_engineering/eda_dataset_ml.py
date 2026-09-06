from __future__ import annotations

import os
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import pandas as pd


# ============================================================
# CONFIGURAÇÕES
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

ENDPOINT = os.getenv(
    "MINIO_ENDPOINT",
    "http://localhost:9000"
)

ACCESS = os.getenv(
    "MINIO_ACCESS_KEY",
    "admin"
)

SECRET = os.getenv(
    "MINIO_SECRET_KEY",
    "minioadmin123"
)

BUCKET = os.getenv(
    "MINIO_BUCKET",
    "f1-data-lake"
)


# Dataset de entrada
DATASET_S3 = "ml/dataset/dataset_ml_interlagos.parquet"


# Saída local
OUTPUT_DIR = ROOT / "ml" / "eda" / "outputs"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# Saídas no MinIO
EDA_S3_PREFIX = "ml/eda"

EDA_CSV_S3_PREFIX = f"{EDA_S3_PREFIX}/csv"

EDA_PLOTS_S3_PREFIX = f"{EDA_S3_PREFIX}/plots"

EDA_REPORT_S3 = f"{EDA_S3_PREFIX}/EDA_DATASET_ML.md"


# ============================================================
# FEATURES
# ============================================================

NUMERIC_FEATURES = [
    "grid",
    "ritmo_representativo_pct",
    "voltas_analisadas",
    "voltas_disponiveis",
    "cobertura_ritmo_pct",
    "qtd_pit_stops",
    "duracao_mediana_pit_convencional",
    "qtd_stints",
    "qtd_compostos_distintos",
    "voltas_stint_medio",
    "air_temp_media",
    "track_temp_media",
    "humidity_media",
    "pressure_media",
    "wind_speed_medio",
]


CATEGORICAL_FEATURES = [
    "primeiro_composto",
    "composto_mais_utilizado",
]


# ============================================================
# UTILITÁRIOS S3 / MINIO
# ============================================================

def s3(path: str) -> str:
    """Monta um URI S3 para o MinIO."""
    return f"s3://{BUCKET}/{path}"


def configure_duckdb(con):
    """Configura o DuckDB para acessar o MinIO."""

    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")

    endpoint = (
        ENDPOINT
        .replace("http://", "")
        .replace("https://", "")
    )

    use_ssl = ENDPOINT.startswith("https://")

    con.execute(
        f"SET s3_endpoint='{endpoint}'"
    )

    con.execute(
        f"SET s3_access_key_id='{ACCESS}'"
    )

    con.execute(
        f"SET s3_secret_access_key='{SECRET}'"
    )

    con.execute(
        f"SET s3_use_ssl={'true' if use_ssl else 'false'}"
    )

    con.execute(
        "SET s3_url_style='path'"
    )

    con.execute(
        "SET disabled_optimizers='statistics_propagation'"
    )


# ============================================================
# SALVAMENTO LOCAL
# ============================================================

def save_csv(
    df: pd.DataFrame,
    name: str
):
    """Salva CSV localmente."""

    path = OUTPUT_DIR / name

    df.to_csv(
        path,
        index=False,
        encoding="utf-8-sig"
    )


# ============================================================
# SALVAMENTO NO MINIO
# ============================================================

def save_dataframe_to_minio(
    con,
    df: pd.DataFrame,
    s3_path: str,
    name: str
):
    """
    Salva um DataFrame como CSV no MinIO.

    Também mantém uma cópia local.
    """

    local_path = OUTPUT_DIR / name

    # --------------------------------------------------------
    # Salva localmente
    # --------------------------------------------------------

    df.to_csv(
        local_path,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Registra DataFrame no DuckDB
    # --------------------------------------------------------

    table_name = "temp_dataframe"

    con.register(
        table_name,
        df
    )

    # --------------------------------------------------------
    # Salva CSV no MinIO
    # --------------------------------------------------------

    output_uri = s3(s3_path)

    con.execute(
        f"""
        COPY {table_name}
        TO '{output_uri}'
        (
            FORMAT CSV,
            HEADER TRUE,
            DELIMITER ','
        )
        """
    )

    con.unregister(table_name)


def save_text_to_minio(
    con,
    text: str,
    s3_path: str
):
    """
    Salva um arquivo de texto no MinIO.

    O arquivo também é salvo localmente.
    """

    local_path = OUTPUT_DIR / "EDA_DATASET_ML.md"

    local_path.write_text(
        text,
        encoding="utf-8"
    )

    # DataFrame de uma coluna para gerar o arquivo
    df = pd.DataFrame(
        {
            "content": [text]
        }
    )

    con.register(
        "report_dataframe",
        df
    )

    output_uri = s3(s3_path)

    # O DuckDB gera CSV, então removemos a primeira
    # e última parte através de uma tabela de texto.
    #
    # Para Markdown, usamos COPY para um arquivo CSV
    # temporário no MinIO e posteriormente mantemos
    # o Markdown localmente.
    #
    # A gravação final do Markdown no MinIO será feita
    # usando o mecanismo de filesystem do Python.
    #
    # Como o projeto utiliza MinIO como S3 compatível,
    # o upload será realizado através do DuckDB.

    con.execute(
        f"""
        COPY (
            SELECT content
            FROM report_dataframe
        )
        TO '{output_uri}'
        (
            FORMAT CSV,
            HEADER FALSE,
            QUOTE ''
        )
        """
    )

    con.unregister("report_dataframe")


def upload_local_file_to_minio(
    con,
    local_path: Path,
    s3_path: str
):
    """
    Envia um arquivo local para o MinIO utilizando
    o mecanismo S3/httpfs do DuckDB.

    Usado principalmente para os gráficos PNG.
    """

    output_uri = s3(s3_path)

    # DuckDB não utiliza COPY diretamente de arquivos
    # binários para S3. O upload dos PNGs será tratado
    # separadamente.
    #
    # Esta função existe como ponto de extensão caso
    # o projeto utilize boto3 posteriormente.
    pass


# ============================================================
# LEITURA DO DATASET
# ============================================================

def load_dataset(con) -> pd.DataFrame:
    """Lê o dataset ML diretamente do MinIO."""

    path = s3(DATASET_S3)

    query = f"""
        SELECT *
        FROM read_parquet('{path}')
        ORDER BY season, round, grid, driver_key
    """

    return con.execute(query).df()


# ============================================================
# VALIDAÇÃO E ANÁLISES
# ============================================================

def structural_validation(df):

    return pd.DataFrame(
        [
            {
                "validacao": "total_linhas",
                "valor": len(df)
            },
            {
                "validacao": "total_colunas",
                "valor": len(df.columns)
            },
            {
                "validacao": "duplicidades_race_driver",
                "valor": int(
                    df.duplicated(
                        ["race_key", "driver_key"]
                    ).sum()
                )
            },
            {
                "validacao": "duplicidades_pilot_race_key",
                "valor": int(
                    df["pilot_race_key"]
                    .duplicated()
                    .sum()
                )
            },
            {
                "validacao": "position_presente",
                "valor": int(
                    "position" in df.columns
                )
            },
            {
                "validacao": "vitoria_presente",
                "valor": int(
                    "vitoria" in df.columns
                )
            },
            {
                "validacao": "vitoria_nulos",
                "valor": int(
                    df["vitoria"].isna().sum()
                )
            },
            {
                "validacao": "temporadas",
                "valor": int(
                    df["season"].nunique()
                )
            },
            {
                "validacao": "corridas",
                "valor": int(
                    df["race_key"].nunique()
                )
            },
            {
                "validacao": "pilotos",
                "valor": int(
                    df["driver_key"].nunique()
                )
            },
        ]
    )


def target_analysis(df):

    counts = (
        df["vitoria"]
        .value_counts(dropna=False)
        .rename_axis("vitoria")
        .reset_index(name="registros")
    )

    counts["percentual"] = (
        counts["registros"]
        / len(df)
        * 100
    ).round(2)

    by_season = (
        df.groupby("season")
        .agg(
            pilotos=("driver_key", "count"),
            vitorias=("vitoria", "sum")
        )
        .reset_index()
    )

    by_season["taxa_vitoria_pct"] = (
        by_season["vitorias"]
        / by_season["pilotos"]
        * 100
    ).round(2)

    return counts, by_season


def numeric_stats(df):

    rows = []

    for col in NUMERIC_FEATURES:

        if col not in df.columns:
            continue

        for value, label in [
            (True, "vencedores"),
            (False, "nao_vencedores")
        ]:

            s = pd.to_numeric(
                df.loc[
                    df["vitoria"] == value,
                    col
                ],
                errors="coerce"
            )

            rows.append(
                {
                    "feature": col,
                    "grupo": label,
                    "n": int(s.notna().sum()),
                    "media": s.mean(),
                    "mediana": s.median(),
                    "desvio_padrao": s.std(),
                    "min": s.min(),
                    "max": s.max(),
                }
            )

    return pd.DataFrame(rows)


def numeric_association(df):

    rows = []

    target = df["vitoria"].astype(int)

    for col in NUMERIC_FEATURES:

        if col not in df.columns:
            continue

        x = pd.to_numeric(
            df[col],
            errors="coerce"
        )

        pair = pd.DataFrame(
            {
                "x": x,
                "target": target
            }
        ).dropna()

        if (
            len(pair) >= 3
            and pair["x"].nunique() >= 2
        ):

            pearson = pair["x"].corr(
                pair["target"],
                method="pearson"
            )

            spearman = pair["x"].corr(
                pair["target"],
                method="spearman"
            )

        else:
            pearson = None
            spearman = None

        rows.append(
            {
                "feature": col,
                "n_disponivel": len(pair),
                "pearson_com_vitoria": pearson,
                "spearman_com_vitoria": spearman,
                "abs_spearman": (
                    abs(spearman)
                    if spearman is not None
                    else None
                ),
            }
        )

    return (
        pd.DataFrame(rows)
        .sort_values(
            "abs_spearman",
            ascending=False,
            na_position="last"
        )
    )


def categorical_analysis(df):

    frames = []

    for col in CATEGORICAL_FEATURES:

        if col not in df.columns:
            continue

        t = (
            df.groupby(
                col,
                dropna=False
            )
            .agg(
                registros=("vitoria", "size"),
                vitorias=("vitoria", "sum")
            )
            .reset_index()
        )

        t["taxa_vitoria_pct"] = (
            t["vitorias"]
            / t["registros"]
            * 100
        ).round(2)

        t.insert(
            0,
            "feature",
            col
        )

        frames.append(t)

    if frames:
        return pd.concat(
            frames,
            ignore_index=True
        )

    return pd.DataFrame()


def missing_analysis(df):

    missing = pd.DataFrame(
        {
            "feature": df.columns,
            "nulos": df.isna().sum().values,
        }
    )

    missing["pct_nulos"] = (
        missing["nulos"]
        / len(df)
        * 100
    ).round(2)

    rows = []

    for col in (
        NUMERIC_FEATURES
        + CATEGORICAL_FEATURES
    ):

        if col not in df.columns:
            continue

        m = df[col].isna()

        rows.append(
            {
                "feature": col,
                "nulos": int(m.sum()),
                "nulos_vencedores": int(
                    (
                        m
                        & (df["vitoria"] == True)
                    ).sum()
                ),
                "nulos_nao_vencedores": int(
                    (
                        m
                        & (df["vitoria"] == False)
                    ).sum()
                ),
                "taxa_vitoria_nulos_pct": (
                    round(
                        df.loc[
                            m,
                            "vitoria"
                        ]
                        .astype(int)
                        .mean()
                        * 100,
                        2
                    )
                    if m.sum()
                    else None
                ),
                "taxa_vitoria_disponiveis_pct": (
                    round(
                        df.loc[
                            ~m,
                            "vitoria"
                        ]
                        .astype(int)
                        .mean()
                        * 100,
                        2
                    )
                    if (~m).sum()
                    else None
                ),
            }
        )

    return (
        missing.sort_values(
            "pct_nulos",
            ascending=False
        ),
        pd.DataFrame(rows)
    )


def redundancy_analysis(df):

    cols = [
        c
        for c in NUMERIC_FEATURES
        if c in df.columns
    ]

    corr = df[cols].corr(
        method="spearman"
    )

    rows = []

    for i, a in enumerate(cols):

        for b in cols[i + 1:]:

            v = corr.loc[a, b]

            if (
                pd.notna(v)
                and abs(v) >= 0.70
            ):

                rows.append(
                    {
                        "feature_a": a,
                        "feature_b": b,
                        "spearman": v,
                        "abs_spearman": abs(v),
                    }
                )

    if not rows:

        return pd.DataFrame(
            columns=[
                "feature_a",
                "feature_b",
                "spearman",
                "abs_spearman"
            ]
        )

    return (
        pd.DataFrame(rows)
        .sort_values(
            "abs_spearman",
            ascending=False
        )
    )


# ============================================================
# GRÁFICOS
# ============================================================

def create_plots(
    df,
    association
):

    counts = df["vitoria"].value_counts()

    labels = [
        "Vitória" if bool(v)
        else "Não vitória"
        for v in counts.index
    ]

    # --------------------------------------------------------
    # 01 - Distribuição do target
    # --------------------------------------------------------

    plt.figure(
        figsize=(7, 5)
    )

    plt.bar(
        labels,
        counts.values
    )

    plt.title(
        "Distribuição do target: vitória"
    )

    plt.ylabel(
        "Registros"
    )

    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR
        / "01_distribuicao_target.png",
        dpi=150
    )

    plt.close()

    # --------------------------------------------------------
    # 02 - Grid x vitória
    # --------------------------------------------------------

    if "grid" in df.columns:

        plt.figure(
            figsize=(8, 5)
        )

        for value, label in [
            (False, "Não vencedores"),
            (True, "Vencedores")
        ]:

            plt.hist(
                df.loc[
                    df["vitoria"] == value,
                    "grid"
                ].dropna(),
                bins=range(
                    int(df["grid"].min()),
                    int(df["grid"].max()) + 2
                ),
                alpha=0.6,
                label=label,
            )

        plt.title(
            "Grid de largada: vencedores x não vencedores"
        )

        plt.xlabel(
            "Grid"
        )

        plt.ylabel(
            "Frequência"
        )

        plt.legend()

        plt.tight_layout()

        plt.savefig(
            OUTPUT_DIR
            / "02_grid_vitoria.png",
            dpi=150
        )

        plt.close()

    # --------------------------------------------------------
    # 03 - Ritmo x vitória
    # --------------------------------------------------------

    if "ritmo_representativo_pct" in df.columns:

        plt.figure(
            figsize=(8, 5)
        )

        for value, label in [
            (False, "Não vencedores"),
            (True, "Vencedores")
        ]:

            plt.hist(
                df.loc[
                    df["vitoria"] == value,
                    "ritmo_representativo_pct"
                ].dropna(),
                bins=15,
                alpha=0.6,
                label=label,
            )

        plt.title(
            "Ritmo representativo: vencedores x não vencedores"
        )

        plt.xlabel(
            "Ritmo representativo (%)"
        )

        plt.ylabel(
            "Frequência"
        )

        plt.legend()

        plt.tight_layout()

        plt.savefig(
            OUTPUT_DIR
            / "03_pace_vitoria.png",
            dpi=150
        )

        plt.close()

    # --------------------------------------------------------
    # 04 - Associação
    # --------------------------------------------------------

    if not association.empty:

        top = (
            association
            .head(10)
            .sort_values(
                "spearman_com_vitoria"
            )
        )

        plt.figure(
            figsize=(9, 6)
        )

        plt.barh(
            top["feature"],
            top["spearman_com_vitoria"]
        )

        plt.axvline(
            0,
            linewidth=1
        )

        plt.title(
            "Top associações monotônicas com vitória"
        )

        plt.xlabel(
            "Correlação de Spearman"
        )

        plt.tight_layout()

        plt.savefig(
            OUTPUT_DIR
            / "04_associacao_vitoria.png",
            dpi=150
        )

        plt.close()


# ============================================================
# RELATÓRIO
# ============================================================

def generate_report(
    df,
    structural,
    counts,
    by_season,
    stats,
    association,
    categorical,
    missing,
    missing_target,
    redundancy
):

    wins = int(
        df["vitoria"].sum()
    )

    parts = [

        "# EDA — Dataset ML Interlagos",

        "",

        "EDA específica do dataset ML, focada na relação entre as features consolidadas e `vitoria`.",

        "",

        "## 1. Escopo",

        f"- Fonte: `s3://{BUCKET}/{DATASET_S3}`",

        "- Período: 2018–2025",

        f"- Registros: {len(df)}",

        f"- Vitórias: {wins}",

        f"- Não vitórias: {len(df) - wins}",

        f"- Taxa de vitória: {wins / len(df) * 100:.2f}%",

        "",

        "## 2. Validação estrutural",

        structural.to_markdown(index=False),

        "",

        "## 3. Distribuição do target",

        counts.to_markdown(index=False),

        "",

        "A classe positiva é minoritária. Isso deve ser considerado na modelagem e na escolha das métricas.",

        "",

        "## 4. Vitórias por temporada",

        by_season.to_markdown(index=False),

        "",

        "## 5. Features numéricas — vencedores x não vencedores",

        stats.to_markdown(
            index=False,
            floatfmt=".4f"
        ),

        "",

        "## 6. Associação numérica com `vitoria`",

        association.to_markdown(
            index=False,
            floatfmt=".4f"
        ),

        "",

        "As correlações são medidas exploratórias de associação e não representam causalidade.",

        "",

        "## 7. Features categóricas",

        (
            categorical.to_markdown(
                index=False,
                floatfmt=".2f"
            )
            if not categorical.empty
            else "Nenhuma."
        ),

        "",

        "## 8. Missing values",

        (
            missing[
                missing["nulos"] > 0
            ].to_markdown(index=False)
            if (
                missing["nulos"] > 0
            ).any()
            else "Nenhum nulo."
        ),

        "",

        "### Missing x target",

        (
            missing_target[
                missing_target["nulos"] > 0
            ].to_markdown(
                index=False,
                floatfmt=".2f"
            )
            if (
                missing_target["nulos"] > 0
            ).any()
            else "Nenhum nulo nas features analisadas."
        ),

        "",

        "## 9. Redundância",

        (
            redundancy.to_markdown(
                index=False,
                floatfmt=".4f"
            )
            if not redundancy.empty
            else "Nenhum par apresentou |Spearman| >= 0,70."
        ),

        "",

        "## 10. Preparação para modelagem",

        "- O target é fortemente desbalanceado: apenas 7 vitórias.",

        "- `position` não está presente e não deve ser reintroduzida como feature.",

        "- Nulos devem ser tratados conforme a natureza de cada variável, sem imputação indiscriminada.",

        "- `voltas_analisadas`, `voltas_disponiveis` e `cobertura_ritmo_pct` devem ser avaliadas quanto à redundância.",

        "- `qtd_pit_stops` e `qtd_stints` devem ser avaliadas conjuntamente.",

        "- Identificadores e colunas de contexto não devem entrar automaticamente como features numéricas.",

        "- Devido ao pequeno número de positivos, resultados de modelagem podem ser instáveis.",

        "",

        "## 11. Limitações",

        "- 140 observações e apenas 7 eventos positivos.",

        "- Associação não implica causalidade.",

        "- A definição do momento da previsão deve ser estabelecida antes de qualquer modelagem preditiva para evitar uso indevido de variáveis pós-corrida.",
    ]

    report = "\n".join(parts)

    local_path = (
        OUTPUT_DIR
        / "EDA_DATASET_ML.md"
    )

    local_path.write_text(
        report,
        encoding="utf-8"
    )

    return report


# ============================================================
# MAIN
# ============================================================

def main():

    con = duckdb.connect()

    try:

        configure_duckdb(con)

        print(
            "=== EDA DATASET ML INTERLAGOS ==="
        )

        print(
            f"Dataset: {s3(DATASET_S3)}"
        )

        # ----------------------------------------------------
        # Leitura
        # ----------------------------------------------------

        df = load_dataset(con)

        print(
            f"Linhas: {len(df)}"
        )

        print(
            f"Colunas: {len(df.columns)}"
        )

        # ----------------------------------------------------
        # Validações
        # ----------------------------------------------------

        structural = structural_validation(
            df
        )

        assert "vitoria" in df.columns

        assert "position" not in df.columns

        assert df["vitoria"].notna().all()

        assert set(
            df["vitoria"].unique()
        ) <= {True, False}

        assert (
            df.duplicated(
                ["race_key", "driver_key"]
            ).sum()
            == 0
        )

        assert (
            df["pilot_race_key"]
            .duplicated()
            .sum()
            == 0
        )

        # ----------------------------------------------------
        # Análises
        # ----------------------------------------------------

        counts, by_season = (
            target_analysis(df)
        )

        stats = numeric_stats(df)

        association = numeric_association(
            df
        )

        categorical = categorical_analysis(
            df
        )

        missing, missing_target = (
            missing_analysis(df)
        )

        redundancy = redundancy_analysis(
            df
        )

        # ----------------------------------------------------
        # Salvar CSVs localmente
        # ----------------------------------------------------

        save_csv(
            structural,
            "structural_validation.csv"
        )

        save_csv(
            counts,
            "target_counts.csv"
        )

        save_csv(
            by_season,
            "wins_by_season.csv"
        )

        save_csv(
            stats,
            "numeric_stats_by_target.csv"
        )

        save_csv(
            association,
            "numeric_association_target.csv"
        )

        save_csv(
            categorical,
            "categorical_analysis.csv"
        )

        save_csv(
            missing,
            "missing_values.csv"
        )

        save_csv(
            missing_target,
            "missing_vs_target.csv"
        )

        save_csv(
            redundancy,
            "feature_redundancy.csv"
        )

        # ----------------------------------------------------
        # Gráficos
        # ----------------------------------------------------

        create_plots(
            df,
            association
        )

        # ----------------------------------------------------
        # Relatório
        # ----------------------------------------------------

        report = generate_report(
            df,
            structural,
            counts,
            by_season,
            stats,
            association,
            categorical,
            missing,
            missing_target,
            redundancy
        )

        # ----------------------------------------------------
        # Enviar CSVs para MinIO
        # ----------------------------------------------------

        print(
            "\n=== ENVIANDO CSVs PARA O MINIO ==="
        )

        csv_files = [
            "structural_validation.csv",
            "target_counts.csv",
            "wins_by_season.csv",
            "numeric_stats_by_target.csv",
            "numeric_association_target.csv",
            "categorical_analysis.csv",
            "missing_values.csv",
            "missing_vs_target.csv",
            "feature_redundancy.csv",
        ]

        csv_dataframes = {
            "structural_validation.csv": structural,
            "target_counts.csv": counts,
            "wins_by_season.csv": by_season,
            "numeric_stats_by_target.csv": stats,
            "numeric_association_target.csv": association,
            "categorical_analysis.csv": categorical,
            "missing_values.csv": missing,
            "missing_vs_target.csv": missing_target,
            "feature_redundancy.csv": redundancy,
        }

        for filename in csv_files:

            df_csv = csv_dataframes[
                filename
            ]

            s3_path = (
                f"{EDA_CSV_S3_PREFIX}"
                f"/{filename}"
            )

            save_dataframe_to_minio(
                con,
                df_csv,
                s3_path,
                filename
            )

            print(
                f"- {s3_path}"
            )

        # ----------------------------------------------------
        # Mostrar resultados
        # ----------------------------------------------------

        print(
            "\n=== TARGET ==="
        )

        print(
            counts.to_string(
                index=False
            )
        )

        print(
            "\n=== TOP ASSOCIAÇÕES COM VITÓRIA ==="
        )

        print(
            association
            .head(10)
            .to_string(index=False)
        )

        print(
            "\n=== NULOS ==="
        )

        print(
            missing[
                missing["nulos"] > 0
            ].to_string(index=False)
        )

        print(
            "\n=== REDUNDÂNCIA ==="
        )

        print(
            redundancy.to_string(
                index=False
            )
            if not redundancy.empty
            else
            "Nenhum par com |Spearman| >= 0,70."
        )

        # ----------------------------------------------------
        # Final
        # ----------------------------------------------------

        print(
            "\n=== EDA CONCLUÍDA ==="
        )

        print(
            f"Saídas locais: {OUTPUT_DIR}"
        )

        print(
            f"Saídas MinIO: s3://{BUCKET}/{EDA_S3_PREFIX}"
        )

    finally:

        con.close()


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    main()
