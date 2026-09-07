"""
Avaliação detalhada dos modelos iniciais — Dataset ML Interlagos.

Objetivo:
    Analisar as previsões out-of-fold da primeira rodada de modelos,
    identificando acertos, erros e comportamento por corrida.

Modelos:
    - Logistic Regression
    - Decision Tree
    - Random Forest

Estratégia:
    - somente conjunto de desenvolvimento;
    - GroupKFold por race_key;
    - pré-processamento dentro do Pipeline;
    - teste 2024–2025 permanece intocado.

IMPORTANTE:
    Esta etapa NÃO realiza tuning.
    Esta etapa NÃO utiliza o conjunto de teste final.

SAÍDAS:
    Todos os arquivos são gravados diretamente no MinIO.
"""

import os

from pathlib import Path

import duckdb
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier


# ============================================================
# CONFIGURAÇÕES
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

MINIO_ENDPOINT = os.getenv(
    "MINIO_ENDPOINT",
    "http://localhost:9000",
)

MINIO_ACCESS_KEY = os.getenv(
    "MINIO_ACCESS_KEY",
    "admin",
)

MINIO_SECRET_KEY = os.getenv(
    "MINIO_SECRET_KEY",
    "minioadmin123",
)

MINIO_BUCKET = os.getenv(
    "MINIO_BUCKET",
    "f1-data-lake",
)

DEVELOPMENT_S3 = (
    "ml/prepared/splits/development.parquet"
)

# Pasta de saída EXCLUSIVAMENTE no MinIO
MINIO_RESULTS_PREFIX = "ml/results"

TARGET = "vitoria"
GROUP = "race_key"


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


ALL_FEATURES = (
    NUMERIC_FEATURES
    + CATEGORICAL_FEATURES
)


# ============================================================
# DUCKDB / MINIO
# ============================================================

def s3_uri(path: str) -> str:
    """
    Monta uma URI S3 apontando para o bucket do MinIO.
    """
    return f"s3://{MINIO_BUCKET}/{path}"


def configure_duckdb(
    con: duckdb.DuckDBPyConnection,
) -> None:

    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")

    endpoint = (
        MINIO_ENDPOINT
        .replace("http://", "")
        .replace("https://", "")
    )

    use_ssl = MINIO_ENDPOINT.startswith(
        "https://"
    )

    con.execute(
        f"SET s3_endpoint='{endpoint}'"
    )

    con.execute(
        f"SET s3_access_key_id='{MINIO_ACCESS_KEY}'"
    )

    con.execute(
        f"SET s3_secret_access_key='{MINIO_SECRET_KEY}'"
    )

    con.execute(
        f"SET s3_use_ssl="
        f"{'true' if use_ssl else 'false'}"
    )

    con.execute(
        "SET s3_url_style='path'"
    )

    # Necessário para evitar o problema observado
    # com propagação de estatísticas no DuckDB + MinIO.
    con.execute(
        "SET disabled_optimizers="
        "'statistics_propagation'"
    )


# ============================================================
# LEITURA
# ============================================================

def load_dataset(
    con: duckdb.DuckDBPyConnection,
) -> pd.DataFrame:

    uri = s3_uri(
        DEVELOPMENT_S3
    )

    return con.execute(
        f"""
        SELECT *
        FROM read_parquet('{uri}')
        """
    ).df()


# ============================================================
# GRAVAÇÃO DIRETA NO MINIO
# ============================================================

def save_dataframe_to_minio(
    con: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    minio_path: str,
) -> None:
    """
    Grava um DataFrame diretamente no MinIO como CSV.

    Nenhum arquivo intermediário é criado localmente.
    """

    uri = s3_uri(minio_path)

    # Nome temporário de tabela/view dentro do DuckDB.
    # Não cria arquivo físico local.
    table_name = "df_to_save"

    con.register(
        table_name,
        df,
    )

    try:
        con.execute(
            f"""
            COPY {table_name}
            TO '{uri}'
            (
                FORMAT CSV,
                HEADER TRUE,
                OVERWRITE TRUE
            )
            """
        )

    finally:
        con.unregister(
            table_name
        )

    print(
        f"Arquivo gravado no MinIO: {uri}"
    )


# ============================================================
# PREPROCESSADOR
# ============================================================

def build_preprocessor():

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
                    handle_unknown="ignore"
                ),
            ),
        ]
    )

    return ColumnTransformer(
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
        ],
        remainder="drop",
    )


# ============================================================
# MODELOS
# ============================================================

def build_models():

    return {

        "Logistic Regression":
            LogisticRegression(
                max_iter=2000,
                class_weight="balanced",
                random_state=42,
            ),

        "Decision Tree":
            DecisionTreeClassifier(
                class_weight="balanced",
                random_state=42,
            ),

        "Random Forest":
            RandomForestClassifier(
                n_estimators=300,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            ),
    }


# ============================================================
# PIPELINE
# ============================================================

def build_pipeline(model):

    return Pipeline(
        steps=[
            (
                "preprocessor",
                build_preprocessor(),
            ),
            (
                "model",
                model,
            ),
        ]
    )


# ============================================================
# VALIDAÇÃO
# ============================================================

def validate_dataset(
    df: pd.DataFrame,
) -> None:

    required = set(
        ALL_FEATURES
        + [
            TARGET,
            GROUP,
            "driver_key",
            "full_name",
            "season",
        ]
    )

    missing = (
        required
        - set(df.columns)
    )

    if missing:
        raise ValueError(
            "Colunas ausentes: "
            + ", ".join(
                sorted(missing)
            )
        )

    if df[TARGET].isna().any():
        raise ValueError(
            "Existem valores nulos no target."
        )

    if df[GROUP].isna().any():
        raise ValueError(
            "Existem race_key nulos."
        )

    duplicates = df.duplicated(
        subset=[
            GROUP,
            "driver_key",
        ]
    ).sum()

    if duplicates > 0:
        raise ValueError(
            "Existem duplicidades piloto-corrida: "
            f"{duplicates}"
        )


# ============================================================
# AVALIAÇÃO DE UM MODELO
# ============================================================

def evaluate_model(
    name,
    model,
    X,
    y,
    groups,
    metadata,
):

    print()
    print(
        f"=== {name.upper()} ==="
    )

    pipeline = build_pipeline(
        model
    )

    n_groups = groups.nunique()

    cv = GroupKFold(
        n_splits=n_groups
    )

    # --------------------------------------------------------
    # Previsões out-of-fold
    # --------------------------------------------------------

    predictions = cross_val_predict(
        pipeline,
        X,
        y,
        cv=cv,
        groups=groups,
        method="predict",
    )

    probabilities = cross_val_predict(
        pipeline,
        X,
        y,
        cv=cv,
        groups=groups,
        method="predict_proba",
    )[:, 1]

    # --------------------------------------------------------
    # Métricas
    # --------------------------------------------------------

    metrics = {

        "modelo": name,

        "accuracy": accuracy_score(
            y,
            predictions,
        ),

        "precision": precision_score(
            y,
            predictions,
            zero_division=0,
        ),

        "recall": recall_score(
            y,
            predictions,
            zero_division=0,
        ),

        "f1": f1_score(
            y,
            predictions,
            zero_division=0,
        ),

        "roc_auc": roc_auc_score(
            y,
            probabilities,
        ),
    }

    print(
        f"Accuracy : {metrics['accuracy']:.4f}"
    )

    print(
        f"Precision: {metrics['precision']:.4f}"
    )

    print(
        f"Recall   : {metrics['recall']:.4f}"
    )

    print(
        f"F1       : {metrics['f1']:.4f}"
    )

    print(
        f"ROC-AUC  : {metrics['roc_auc']:.4f}"
    )

    # --------------------------------------------------------
    # Resultado por piloto-corrida
    # --------------------------------------------------------

    predictions_df = metadata.copy()

    predictions_df["modelo"] = name

    predictions_df[
        "y_real"
    ] = y.to_numpy()

    predictions_df[
        "y_pred"
    ] = predictions

    predictions_df[
        "probabilidade_vitoria"
    ] = probabilities

    predictions_df[
        "acertou"
    ] = (
        predictions_df["y_real"]
        == predictions_df["y_pred"]
    )

    predictions_df[
        "erro"
    ] = (
        predictions_df["y_real"]
        != predictions_df["y_pred"]
    )

    # --------------------------------------------------------
    # Fold
    # --------------------------------------------------------

    fold_mapping = {}

    for fold, (
        train_idx,
        validation_idx,
    ) in enumerate(
        cv.split(
            X,
            y,
            groups,
        ),
        start=1,
    ):

        for index in validation_idx:

            fold_mapping[
                index
            ] = fold

    predictions_df[
        "fold"
    ] = [
        fold_mapping[i]
        for i in range(
            len(predictions_df)
        )
    ]

    return (
        metrics,
        predictions_df,
    )


# ============================================================
# ANÁLISE POR CORRIDA
# ============================================================

def analyze_by_race(
    predictions_df,
    model_name,
):

    rows = []

    for race_key, group in (
        predictions_df
        .groupby("race_key")
    ):

        actual_winner = (
            group.loc[
                group["y_real"] == 1,
                "full_name",
            ]
            .iloc[0]
        )

        predicted_winner = (
            group.loc[
                group[
                    "probabilidade_vitoria"
                ].idxmax(),
                "full_name",
            ]
        )

        winner_probability = (
            group.loc[
                group["y_real"] == 1,
                "probabilidade_vitoria",
            ]
            .iloc[0]
        )

        actual_winner_rank = (
            group[
                "probabilidade_vitoria"
            ]
            .rank(
                ascending=False,
                method="min",
            )
            [
                group["y_real"] == 1
            ]
            .iloc[0]
        )

        rows.append(
            {
                "modelo": model_name,
                "race_key": race_key,
                "season": group[
                    "season"
                ].iloc[0],
                "vencedor_real": actual_winner,
                "vencedor_predito_por_probabilidade": (
                    predicted_winner
                ),
                "probabilidade_do_vencedor_real": (
                    winner_probability
                ),
                "ranking_do_vencedor_real": (
                    actual_winner_rank
                ),
                "acertou_vencedor_por_maior_probabilidade": (
                    actual_winner
                    == predicted_winner
                ),
            }
        )

    return pd.DataFrame(
        rows
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=== AVALIAÇÃO DETALHADA "
        "DOS MODELOS INICIAIS ==="
    )

    print(
        "Base: desenvolvimento"
    )

    print(
        "Validação: GroupKFold por race_key"
    )

    print(
        "Teste 2024–2025: NÃO utilizado"
    )

    print(
        "Saída: exclusivamente MinIO"
    )

    print()

    con = duckdb.connect()

    try:

        configure_duckdb(
            con
        )

        # ----------------------------------------------------
        # 1. Ler dataset
        # ----------------------------------------------------

        df = load_dataset(
            con
        )

        print(
            f"Registros carregados: "
            f"{len(df)}"
        )

        validate_dataset(
            df
        )

        # ----------------------------------------------------
        # 2. Features
        # ----------------------------------------------------

        X = df[
            ALL_FEATURES
        ].copy()

        y = (
            df[TARGET]
            .astype(int)
        )

        groups = df[
            GROUP
        ].copy()

        # ----------------------------------------------------
        # 3. Metadados
        # ----------------------------------------------------

        metadata = df[
            [
                "pilot_race_key",
                "race_key",
                "driver_key",
                "season",
                "round",
                "full_name",
                "constructor_name",
                "grid",
            ]
        ].copy()

        # ----------------------------------------------------
        # 4. Modelos
        # ----------------------------------------------------

        models = build_models()

        all_metrics = []
        all_predictions = []
        all_race_analysis = []

        # ----------------------------------------------------
        # 5. Avaliar
        # ----------------------------------------------------

        for name, model in (
            models.items()
        ):

            metrics, predictions = (
                evaluate_model(
                    name,
                    model,
                    X,
                    y,
                    groups,
                    metadata,
                )
            )

            all_metrics.append(
                metrics
            )

            all_predictions.append(
                predictions
            )

            race_analysis = (
                analyze_by_race(
                    predictions,
                    name,
                )
            )

            all_race_analysis.append(
                race_analysis
            )

        # ----------------------------------------------------
        # 6. DataFrames finais
        # ----------------------------------------------------

        metrics_df = pd.DataFrame(
            all_metrics
        )

        predictions_df = pd.concat(
            all_predictions,
            ignore_index=True,
        )

        race_analysis_df = pd.concat(
            all_race_analysis,
            ignore_index=True,
        )

        # ----------------------------------------------------
        # 7. Comparação
        # ----------------------------------------------------

        metrics_df = metrics_df.sort_values(
            "f1",
            ascending=False,
        )

        print()
        print(
            "=== COMPARAÇÃO ==="
        )

        print(
            metrics_df.to_string(
                index=False
            )
        )

        # ----------------------------------------------------
        # 8. Análise por corrida
        # ----------------------------------------------------

        print()
        print(
            "=== RESULTADO POR CORRIDA ==="
        )

        print(
            race_analysis_df.to_string(
                index=False
            )
        )

        # ----------------------------------------------------
        # 9. Caminhos no MinIO
        # ----------------------------------------------------

        metrics_path = (
            f"{MINIO_RESULTS_PREFIX}/"
            "initial_model_metrics.csv"
        )

        predictions_path = (
            f"{MINIO_RESULTS_PREFIX}/"
            "initial_model_predictions.csv"
        )

        race_path = (
            f"{MINIO_RESULTS_PREFIX}/"
            "initial_model_race_analysis.csv"
        )

        # ----------------------------------------------------
        # 10. Gravar DIRETAMENTE no MinIO
        # ----------------------------------------------------

        save_dataframe_to_minio(
            con,
            metrics_df,
            metrics_path,
        )

        save_dataframe_to_minio(
            con,
            predictions_df,
            predictions_path,
        )

        save_dataframe_to_minio(
            con,
            race_analysis_df,
            race_path,
        )

        # ----------------------------------------------------
        # 11. Análise dos erros
        # ----------------------------------------------------

        print()
        print(
            "=== ERROS POR MODELO ==="
        )

        for name in models:

            model_predictions = (
                predictions_df[
                    predictions_df["modelo"]
                    == name
                ]
            )

            errors = (
                model_predictions[
                    model_predictions["erro"]
                ]
            )

            print(
                f"{name}: "
                f"{len(errors)} erros "
                f"de {len(model_predictions)} "
                f"previsões"
            )

        # ----------------------------------------------------
        # 12. Arquivos no MinIO
        # ----------------------------------------------------

        print()
        print(
            "=== ARQUIVOS GERADOS NO MINIO ==="
        )

        print(
            s3_uri(metrics_path)
        )

        print(
            s3_uri(predictions_path)
        )

        print(
            s3_uri(race_path)
        )

        # ----------------------------------------------------
        # 13. Conclusão
        # ----------------------------------------------------

        print()
        print(
            "=== AVALIAÇÃO CONCLUÍDA ==="
        )

        print(
            "Os resultados foram gravados "
            "exclusivamente no MinIO."
        )

        print(
            "Nenhum arquivo de resultado "
            "foi salvo localmente."
        )

        print(
            "O teste final 2024–2025 "
            "permaneceu intocado."
        )

        print(
            "Nenhum tuning foi realizado."
        )

    finally:

        con.close()


if __name__ == "__main__":
    main()