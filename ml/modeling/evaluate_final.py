from pathlib import Path

import duckdb
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)
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

TEST_PATH = (
    "s3://f1-data-lake/ml/prepared/splits/test.parquet"
)

OUTPUT_METRICS = (
    "s3://f1-data-lake/ml/results/final_test_metrics.csv"
)

OUTPUT_PREDICTIONS = (
    "s3://f1-data-lake/ml/results/final_test_predictions.csv"
)

OUTPUT_RACE_SUMMARY = (
    "s3://f1-data-lake/ml/results/final_test_race_summary.csv"
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

FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

TARGET = "vitoria"


# ============================================================
# DUCKDB / MINIO
# ============================================================

def configurar_duckdb():

    con = duckdb.connect()

    con.execute("INSTALL httpfs;")
    con.execute("LOAD httpfs;")

    con.execute(
        f"""
        SET s3_endpoint='{MINIO_ENDPOINT.replace("http://", "")}';
        """
    )

    con.execute(
        f"""
        SET s3_access_key_id='{MINIO_ACCESS_KEY}';
        """
    )

    con.execute(
        f"""
        SET s3_secret_access_key='{MINIO_SECRET_KEY}';
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
# LEITURA DO DATASET
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
                SimpleImputer(strategy="median"),
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
                SimpleImputer(strategy="most_frequent"),
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
# AVALIAÇÃO
# ============================================================

def avaliar_modelo(
    modelo,
    X_test,
    y_test,
):

    y_pred = modelo.predict(X_test)

    y_proba = modelo.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": accuracy_score(
            y_test,
            y_pred,
        ),
        "precision": precision_score(
            y_test,
            y_pred,
            zero_division=0,
        ),
        "recall": recall_score(
            y_test,
            y_pred,
            zero_division=0,
        ),
        "f1": f1_score(
            y_test,
            y_pred,
            zero_division=0,
        ),
        "roc_auc": roc_auc_score(
            y_test,
            y_proba,
        ),
    }

    return metrics, y_pred, y_proba


# ============================================================
# RESUMO POR CORRIDA
# ============================================================

def gerar_resumo_por_corrida(
    test_df,
    y_pred,
    y_proba,
):

    resultado = test_df.copy()

    resultado["y_pred"] = y_pred
    resultado["probabilidade_vitoria"] = y_proba

    registros = []

    for race_key, grupo in resultado.groupby(
        "race_key",
        sort=True,
    ):

        # Ordena os pilotos pela probabilidade prevista
        grupo = grupo.sort_values(
            "probabilidade_vitoria",
            ascending=False,
        ).reset_index(drop=True)

        # Vencedor real
        vencedores_reais = grupo[
            grupo[TARGET] == True
        ]

        if vencedores_reais.empty:
            continue

        vencedor_real = vencedores_reais.iloc[0]

        # Piloto com maior probabilidade prevista
        vencedor_previsto = grupo.iloc[0]

        # Ranking do vencedor real
        ranking_vencedor_real = (
            grupo.index[
                grupo["driver_key"]
                == vencedor_real["driver_key"]
            ][0]
            + 1
        )

        registros.append(
            {
                "race_key": race_key,
                "season": int(
                    vencedor_real["season"]
                ),
                "round": int(
                    vencedor_real["round"]
                ),
                "race_name": (
                    f"Interlagos "
                    f"{int(vencedor_real['season'])}"
                ),
                "vencedor_real": (
                    vencedor_real["full_name"]
                ),
                "probabilidade_vencedor_real": (
                    vencedor_real[
                        "probabilidade_vitoria"
                    ]
                ),
                "vencedor_previsto": (
                    vencedor_previsto["full_name"]
                ),
                "probabilidade_vencedor_previsto": (
                    vencedor_previsto[
                        "probabilidade_vitoria"
                    ]
                ),
                "acertou_vencedor": (
                    vencedor_real["driver_key"]
                    == vencedor_previsto["driver_key"]
                ),
                "posicao_rank_vencedor_real": (
                    ranking_vencedor_real
                ),
            }
        )

    return pd.DataFrame(registros)


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

    con.unregister("df_output")


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "AVALIAÇÃO FINAL — RANDOM FOREST — TESTE 2024–2025"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # Configurar DuckDB
    # --------------------------------------------------------

    con = configurar_duckdb()

    # --------------------------------------------------------
    # Development
    # --------------------------------------------------------

    development = carregar_dataset(
        con,
        DEVELOPMENT_PATH,
    )

    print(
        f"\nDevelopment carregado: "
        f"{len(development)} linhas"
    )

    print(
        f"Corridas development: "
        f"{development['race_key'].nunique()}"
    )

    print(
        f"Temporadas development: "
        f"{sorted(development['season'].unique())}"
    )

    print(
        f"Vitórias development: "
        f"{development[TARGET].sum()}"
    )

    # --------------------------------------------------------
    # Test
    # --------------------------------------------------------

    test = carregar_dataset(
        con,
        TEST_PATH,
    )

    print(
        f"\nTest carregado: "
        f"{len(test)} linhas"
    )

    print(
        f"Corridas test: "
        f"{test['race_key'].nunique()}"
    )

    print(
        f"Temporadas test: "
        f"{sorted(test['season'].unique())}"
    )

    print(
        f"Vitórias test: "
        f"{test[TARGET].sum()}"
    )

    # --------------------------------------------------------
    # Validação básica dos grupos
    # --------------------------------------------------------

    development_races = set(
        development["race_key"].unique()
    )

    test_races = set(
        test["race_key"].unique()
    )

    intersecao = (
        development_races
        & test_races
    )

    if intersecao:

        raise ValueError(
            "ERRO: existem race_keys presentes "
            "simultaneamente em development e test."
        )

    print(
        "\nValidação de grupos: OK"
    )

    print(
        "Nenhuma race_key do test "
        "está presente no development."
    )

    # --------------------------------------------------------
    # Separação das features
    # --------------------------------------------------------

    X_train = development[
        FEATURES
    ]

    y_train = development[
        TARGET
    ].astype(int)

    X_test = test[
        FEATURES
    ]

    y_test = test[
        TARGET
    ].astype(int)

    print(
        f"\nFeatures utilizadas: "
        f"{len(FEATURES)}"
    )

    print(
        f"  Numéricas: "
        f"{len(NUMERIC_FEATURES)}"
    )

    print(
        f"  Categóricas: "
        f"{len(CATEGORICAL_FEATURES)}"
    )

    # --------------------------------------------------------
    # Criar modelo
    # --------------------------------------------------------

    print(
        "\n" + "-" * 70
    )

    print(
        "CONFIGURAÇÃO DO RANDOM FOREST"
    )

    print(
        "-" * 70
    )

    print(
        "n_estimators     : 300"
    )

    print(
        "max_depth        : 3"
    )

    print(
        "min_samples_leaf : 1"
    )

    print(
        "class_weight     : balanced"
    )

    print(
        "random_state     : 42"
    )

    # --------------------------------------------------------
    # Treinamento
    # --------------------------------------------------------

    print(
        "\nTreinando Random Forest final..."
    )

    modelo = criar_modelo()

    modelo.fit(
        X_train,
        y_train,
    )

    print(
        "Treinamento concluído."
    )

    # --------------------------------------------------------
    # Avaliação final
    # --------------------------------------------------------

    metrics, y_pred, y_proba = avaliar_modelo(
        modelo,
        X_test,
        y_test,
    )

    print(
        "\n" + "-" * 70
    )

    print(
        "MÉTRICAS FINAIS — TESTE 2024–2025"
    )

    print(
        "-" * 70
    )

    print(
        f"ACCURACY    : "
        f"{metrics['accuracy']:.4f}"
    )

    print(
        f"PRECISION   : "
        f"{metrics['precision']:.4f}"
    )

    print(
        f"RECALL      : "
        f"{metrics['recall']:.4f}"
    )

    print(
        f"F1          : "
        f"{metrics['f1']:.4f}"
    )

    print(
        f"ROC_AUC     : "
        f"{metrics['roc_auc']:.4f}"
    )

    # --------------------------------------------------------
    # Matriz de confusão
    # --------------------------------------------------------

    cm = confusion_matrix(
        y_test,
        y_pred,
    )

    print(
        "\nMATRIZ DE CONFUSÃO"
    )

    print(cm)

    tn, fp, fn, tp = cm.ravel()

    print(
        f"\nTrue Negative : {tn}"
    )

    print(
        f"False Positive: {fp}"
    )

    print(
        f"False Negative: {fn}"
    )

    print(
        f"True Positive : {tp}"
    )

    # --------------------------------------------------------
    # DataFrame de métricas
    # --------------------------------------------------------

    metrics_df = pd.DataFrame(
        [
            {
                "modelo": "Random Forest",
                "conjunto": "test",
                "temporadas": "2024-2025",
                "n_registros": len(test),
                "n_corridas": test[
                    "race_key"
                ].nunique(),
                "n_vitorias": int(
                    y_test.sum()
                ),
                "accuracy": metrics[
                    "accuracy"
                ],
                "precision": metrics[
                    "precision"
                ],
                "recall": metrics[
                    "recall"
                ],
                "f1": metrics[
                    "f1"
                ],
                "roc_auc": metrics[
                    "roc_auc"
                ],
                "true_negative": int(tn),
                "false_positive": int(fp),
                "false_negative": int(fn),
                "true_positive": int(tp),
            }
        ]
    )

    # --------------------------------------------------------
    # Predições por piloto
    # --------------------------------------------------------

    predictions_df = test[
        [
            "pilot_race_key",
            "race_key",
            "driver_key",
            "team_key",
            "season",
            "round",
            "full_name",
            "constructor_name",
            TARGET,
        ]
    ].copy()

    predictions_df["y_pred"] = y_pred

    predictions_df[
        "probabilidade_vitoria"
    ] = y_proba

    predictions_df[
        "modelo"
    ] = "Random Forest"

    # --------------------------------------------------------
    # Resumo por corrida
    # --------------------------------------------------------

    race_summary_df = gerar_resumo_por_corrida(
        test,
        y_pred,
        y_proba,
    )

    print(
        "\n" + "-" * 70
    )

    print(
        "RESULTADO POR CORRIDA"
    )

    print(
        "-" * 70
    )

    if not race_summary_df.empty:

        print(
            race_summary_df[
                [
                    "season",
                    "race_name",
                    "vencedor_real",
                    "vencedor_previsto",
                    "acertou_vencedor",
                    "posicao_rank_vencedor_real",
                    "probabilidade_vencedor_real",
                    "probabilidade_vencedor_previsto",
                ]
            ].to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # Taxa de acerto do vencedor
    # --------------------------------------------------------

    if not race_summary_df.empty:

        acertos_vencedor = int(
            race_summary_df[
                "acertou_vencedor"
            ].sum()
        )

        total_corridas = len(
            race_summary_df
        )

        taxa_acerto = (
            acertos_vencedor
            / total_corridas
        )

        print(
            "\n" + "-" * 70
        )

        print(
            "ACERTO DO VENCEDOR POR CORRIDA"
        )

        print(
            "-" * 70
        )

        print(
            f"Acertos: "
            f"{acertos_vencedor}/"
            f"{total_corridas}"
        )

        print(
            f"Taxa: "
            f"{taxa_acerto:.2%}"
        )

    # --------------------------------------------------------
    # Salvar no MinIO
    # --------------------------------------------------------

    print(
        "\nSalvando resultados no MinIO..."
    )

    salvar_minio(
        con,
        metrics_df,
        OUTPUT_METRICS,
    )

    salvar_minio(
        con,
        predictions_df,
        OUTPUT_PREDICTIONS,
    )

    salvar_minio(
        con,
        race_summary_df,
        OUTPUT_RACE_SUMMARY,
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
        OUTPUT_METRICS
    )

    print(
        OUTPUT_PREDICTIONS
    )

    print(
        OUTPUT_RACE_SUMMARY
    )

    print(
        "\nAvaliação final concluída."
    )


if __name__ == "__main__":
    main()