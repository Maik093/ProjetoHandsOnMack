from pathlib import Path

import duckdb
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier


# ============================================================
# CONFIGURAÇÕES
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "minioadmin123"

DEVELOPMENT_PATH = (
    "s3://f1-data-lake/ml/prepared/splits/development.parquet"
)

OUTPUT_FEATURE_IMPORTANCE = (
    "s3://f1-data-lake/ml/results/feature_importance.csv"
)

OUTPUT_FEATURE_GROUPS = (
    "s3://f1-data-lake/ml/results/feature_importance_groups.csv"
)

OUTPUT_WINNERS_COMPARISON = (
    "s3://f1-data-lake/ml/results/winners_vs_non_winners.csv"
)


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
    "rainfall_ocorreu",
]

CATEGORICAL_FEATURES = [
    "primeiro_composto",
    "composto_mais_utilizado",
]

FEATURES = (
    NUMERIC_FEATURES
    + CATEGORICAL_FEATURES
)

TARGET = "vitoria"


# ============================================================
# GRUPOS ANALÍTICOS
# ============================================================

FEATURE_GROUPS = {
    "Desempenho": [
        "ritmo_representativo_pct",
    ],

    "Qualificação": [
        "grid",
    ],

    "Pit Stops": [
        "qtd_pit_stops",
        "duracao_mediana_pit_convencional",
    ],

    "Stints e Pneus": [
        "qtd_stints",
        "qtd_compostos_distintos",
        "primeiro_composto",
        "composto_mais_utilizado",
        "voltas_stint_medio",
    ],

    "Cobertura do Ritmo": [
        "voltas_analisadas",
        "voltas_disponiveis",
        "cobertura_ritmo_pct",
    ],

    "Clima": [
        "air_temp_media",
        "track_temp_media",
        "humidity_media",
        "pressure_media",
        "wind_speed_medio",
        "rainfall_ocorreu",
    ],
}


# ============================================================
# DUCKDB / MINIO
# ============================================================

def configurar_duckdb():

    con = duckdb.connect()

    con.execute("INSTALL httpfs;")
    con.execute("LOAD httpfs;")

    con.execute(
        f"""
        SET s3_endpoint=
        '{MINIO_ENDPOINT.replace("http://", "")}';
        """
    )

    con.execute(
        f"""
        SET s3_access_key_id=
        '{MINIO_ACCESS_KEY}';
        """
    )

    con.execute(
        f"""
        SET s3_secret_access_key=
        '{MINIO_SECRET_KEY}';
        """
    )

    con.execute("SET s3_use_ssl=false;")
    con.execute("SET s3_url_style='path';")

    # Compatibilidade DuckDB + MinIO
    con.execute(
        "SET disabled_optimizers='statistics_propagation';"
    )

    return con


# ============================================================
# LEITURA
# ============================================================

def carregar_dataset(con, path):

    query = f"""
        SELECT *
        FROM read_parquet('{path}')
    """

    return con.execute(query).df()


# ============================================================
# PREPROCESSAMENTO
# ============================================================

def criar_preprocessador():

    numeric_pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(
                    strategy="median"
                ),
            ),
            (
                "scaler",
                StandardScaler(),
            ),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(
                    strategy="most_frequent"
                ),
            ),
            (
                "encoder",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=False,
                ),
            ),
        ]
    )

    preprocessador = ColumnTransformer(
        transformers=[
            (
                "numeric",
                numeric_pipeline,
                NUMERIC_FEATURES,
            ),
            (
                "categorical",
                categorical_pipeline,
                CATEGORICAL_FEATURES,
            ),
        ]
    )

    return preprocessador


# ============================================================
# MODELO FINAL
# ============================================================

def criar_modelo():

    preprocessador = criar_preprocessador()

    modelo = RandomForestClassifier(
        n_estimators=300,
        max_depth=3,
        min_samples_leaf=1,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )

    pipeline = Pipeline(
        steps=[
            (
                "preprocessor",
                preprocessador,
            ),
            (
                "model",
                modelo,
            ),
        ]
    )

    return pipeline


# ============================================================
# MAPEAR FEATURES TRANSFORMADAS
# ============================================================

def obter_importancias(
    modelo,
    X,
):

    preprocessador = (
        modelo.named_steps["preprocessor"]
    )

    rf = modelo.named_steps["model"]

    importancias = (
        rf.feature_importances_
    )

    nomes_transformados = (
        preprocessador.get_feature_names_out()
    )

    if len(importancias) != len(
        nomes_transformados
    ):
        raise ValueError(
            "Quantidade de importâncias "
            "diferente da quantidade de "
            "features transformadas."
        )

    resultado = pd.DataFrame(
        {
            "feature_transformada": (
                nomes_transformados
            ),
            "importancia": importancias,
        }
    )

    # Remove os prefixos criados pelo ColumnTransformer
    resultado[
        "feature_transformada"
    ] = (
        resultado[
            "feature_transformada"
        ]
        .str.replace(
            "numeric__",
            "",
            regex=False,
        )
        .str.replace(
            "categorical__",
            "",
            regex=False,
        )
    )

    # --------------------------------------------------------
    # Identificar a feature original
    # --------------------------------------------------------

    def identificar_feature(nome):

        for feature in FEATURES:

            if nome == feature:
                return feature

            if nome.startswith(
                feature + "_"
            ):
                return feature

        return nome

    resultado[
        "feature"
    ] = resultado[
        "feature_transformada"
    ].apply(
        identificar_feature
    )

    # --------------------------------------------------------
    # Ordenar
    # --------------------------------------------------------

    resultado = resultado.sort_values(
        "importancia",
        ascending=False,
    ).reset_index(
        drop=True
    )

    resultado[
        "ranking_transformado"
    ] = (
        resultado.index + 1
    )

    return resultado


# ============================================================
# AGRUPAR IMPORTÂNCIAS POR FEATURE ORIGINAL
# ============================================================

def agrupar_importancias(
    importance_df,
):

    agrupado = (
        importance_df
        .groupby(
            "feature",
            as_index=False,
        )["importancia"]
        .sum()
        .sort_values(
            "importancia",
            ascending=False,
        )
        .reset_index(
            drop=True
        )
    )

    agrupado[
        "ranking"
    ] = (
        agrupado.index + 1
    )

    total = agrupado[
        "importancia"
    ].sum()

    if total > 0:

        agrupado[
            "percentual_importancia"
        ] = (
            agrupado[
                "importancia"
            ]
            / total
            * 100
        )

    else:

        agrupado[
            "percentual_importancia"
        ] = 0.0

    return agrupado


# ============================================================
# AGRUPAR POR TEMA ANALÍTICO
# ============================================================

def criar_importancia_grupos(
    feature_importance_df,
):

    registros = []

    for grupo, features in (
        FEATURE_GROUPS.items()
    ):

        subset = (
            feature_importance_df[
                feature_importance_df[
                    "feature"
                ].isin(features)
            ]
        )

        importancia = subset[
            "importancia"
        ].sum()

        registros.append(
            {
                "grupo": grupo,
                "importancia": importancia,
                "quantidade_features": len(
                    features
                ),
            }
        )

    resultado = pd.DataFrame(
        registros
    )

    total = resultado[
        "importancia"
    ].sum()

    if total > 0:

        resultado[
            "percentual_importancia"
        ] = (
            resultado[
                "importancia"
            ]
            / total
            * 100
        )

    else:

        resultado[
            "percentual_importancia"
        ] = 0.0

    resultado = resultado.sort_values(
        "importancia",
        ascending=False,
    ).reset_index(
        drop=True
    )

    resultado[
        "ranking"
    ] = (
        resultado.index + 1
    )

    return resultado


# ============================================================
# COMPARAÇÃO VENCEDORES × NÃO VENCEDORES
# ============================================================

def comparar_vencedores(
    df,
):

    registros = []

    numeric_comparison = [
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
        "rainfall_ocorreu",
    ]

    for feature in numeric_comparison:

        vencedores = df.loc[
            df[TARGET] == True,
            feature,
        ]

        nao_vencedores = df.loc[
            df[TARGET] == False,
            feature,
        ]

        registros.append(
            {
                "feature": feature,
                "grupo": "vencedores",
                "n": len(vencedores),
                "media": vencedores.mean(),
                "mediana": vencedores.median(),
                "min": vencedores.min(),
                "max": vencedores.max(),
            }
        )

        registros.append(
            {
                "feature": feature,
                "grupo": "nao_vencedores",
                "n": len(nao_vencedores),
                "media": nao_vencedores.mean(),
                "mediana": nao_vencedores.median(),
                "min": nao_vencedores.min(),
                "max": nao_vencedores.max(),
            }
        )

    # --------------------------------------------------------
    # Categóricas
    # --------------------------------------------------------

    categorical_comparison = [
        "primeiro_composto",
        "composto_mais_utilizado",
    ]

    for feature in categorical_comparison:

        tabela = (
            df.groupby(
                [
                    feature,
                    TARGET,
                ],
                dropna=False,
            )
            .size()
            .reset_index(
                name="quantidade"
            )
        )

        tabela[
            "feature"
        ] = feature

        tabela[
            "grupo"
        ] = tabela[
            TARGET
        ].map(
            {
                True: "vencedores",
                False: "nao_vencedores",
            }
        )

        tabela = tabela.rename(
            columns={
                feature: "categoria"
            }
        )

        for _, row in tabela.iterrows():

            registros.append(
                {
                    "feature": feature,
                    "grupo": row["grupo"],
                    "n": row["quantidade"],
                    "media": None,
                    "mediana": None,
                    "min": None,
                    "max": None,
                    "categoria": row[
                        "categoria"
                    ],
                    "quantidade": row[
                        "quantidade"
                    ],
                }
            )

    return pd.DataFrame(
        registros
    )


# ============================================================
# SALVAR NO MINIO
# ============================================================

def salvar_minio(
    con,
    df,
    path,
):

    con.register(
        "df_output",
        df,
    )

    con.execute(
        f"""
        COPY df_output
        TO '{path}'
        (
            FORMAT CSV,
            HEADER,
            DELIMITER ','
        );
        """
    )

    con.unregister(
        "df_output"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "INTERPRETAÇÃO DO RANDOM FOREST"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # Configuração
    # --------------------------------------------------------

    con = configurar_duckdb()

    # --------------------------------------------------------
    # Dataset
    # --------------------------------------------------------

    df = carregar_dataset(
        con,
        DEVELOPMENT_PATH,
    )

    print(
        f"\nDataset development: "
        f"{len(df)} linhas"
    )

    print(
        f"Corridas: "
        f"{df['race_key'].nunique()}"
    )

    print(
        f"Vitórias: "
        f"{df[TARGET].sum()}"
    )

    print(
        f"Não-vitórias: "
        f"{(~df[TARGET]).sum()}"
    )

    # --------------------------------------------------------
    # Features
    # --------------------------------------------------------

    X = df[FEATURES]

    y = df[TARGET].astype(int)

    # --------------------------------------------------------
    # Treinamento
    # --------------------------------------------------------

    print(
        "\nTreinando Random Forest final "
        "no development..."
    )

    modelo = criar_modelo()

    modelo.fit(
        X,
        y,
    )

    print(
        "Treinamento concluído."
    )

    # --------------------------------------------------------
    # Importâncias
    # --------------------------------------------------------

    importance_transformed = (
        obter_importancias(
            modelo,
            X,
        )
    )

    feature_importance = (
        agrupar_importancias(
            importance_transformed
        )
    )

    # --------------------------------------------------------
    # Grupos
    # --------------------------------------------------------

    group_importance = (
        criar_importancia_grupos(
            feature_importance
        )
    )

    # --------------------------------------------------------
    # Comparação
    # --------------------------------------------------------

    winners_comparison = (
        comparar_vencedores(df)
    )

    # --------------------------------------------------------
    # Exibir ranking
    # --------------------------------------------------------

    print(
        "\n" + "-" * 70
    )

    print(
        "RANKING DE IMPORTÂNCIA DAS FEATURES"
    )

    print(
        "-" * 70
    )

    print(
        feature_importance[
            [
                "ranking",
                "feature",
                "importancia",
                "percentual_importancia",
            ]
        ].to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Exibir grupos
    # --------------------------------------------------------

    print(
        "\n" + "-" * 70
    )

    print(
        "IMPORTÂNCIA POR GRUPO"
    )

    print(
        "-" * 70
    )

    print(
        group_importance[
            [
                "ranking",
                "grupo",
                "importancia",
                "percentual_importancia",
            ]
        ].to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Comparação vencedores
    # --------------------------------------------------------

    print(
        "\n" + "-" * 70
    )

    print(
        "VENCEDORES × NÃO VENCEDORES"
    )

    print(
        "-" * 70
    )

    print(
        winners_comparison[
            [
                "feature",
                "grupo",
                "n",
                "media",
                "mediana",
            ]
        ]
        .drop_duplicates(
            subset=[
                "feature",
                "grupo",
            ]
        )
        .to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Salvar MinIO
    # --------------------------------------------------------

    print(
        "\nSalvando resultados no MinIO..."
    )

    salvar_minio(
        con,
        feature_importance,
        OUTPUT_FEATURE_IMPORTANCE,
    )

    salvar_minio(
        con,
        group_importance,
        OUTPUT_FEATURE_GROUPS,
    )

    salvar_minio(
        con,
        winners_comparison,
        OUTPUT_WINNERS_COMPARISON,
    )

    # --------------------------------------------------------
    # Final
    # --------------------------------------------------------

    print(
        "\n" + "=" * 70
    )

    print(
        "RESULTADOS SALVOS NO MINIO"
    )

    print(
        "=" * 70
    )

    print(
        OUTPUT_FEATURE_IMPORTANCE
    )

    print(
        OUTPUT_FEATURE_GROUPS
    )

    print(
        OUTPUT_WINNERS_COMPARISON
    )

    print(
        "\nInterpretação concluída."
    )


if __name__ == "__main__":
    main()