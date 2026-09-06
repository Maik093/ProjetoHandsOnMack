"""
Treinamento inicial dos modelos — Dataset ML Interlagos.

Objetivo:
    Avaliar modelos de classificação para identificar padrões
    associados à vitória em corridas de Interlagos.

Estratégia:
    - utiliza somente o conjunto de desenvolvimento;
    - mantém race_key como grupo;
    - utiliza GroupKFold;
    - realiza imputação e encoding dentro do Pipeline;
    - não utiliza o conjunto de teste nesta etapa;
    - não realiza tuning de hiperparâmetros.

Modelos:
    - Logistic Regression
    - Decision Tree
    - Random Forest

Métricas:
    - Precision
    - Recall
    - F1
    - ROC-AUC
    - Accuracy

IMPORTANTE:
    O conjunto de teste 2024–2025 permanece intocado.
"""

import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
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
from sklearn.ensemble import RandomForestClassifier


# ============================================================
# CONFIGURAÇÕES
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = ROOT / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# MINIO
# ============================================================

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


# ============================================================
# FEATURES
# ============================================================

# Variáveis aprovadas para a primeira modelagem.
#
# IDs, nomes e informações de rastreabilidade NÃO entram
# automaticamente como features.
#
# position não pode entrar porque é a origem do target.
#
# posicoes_ganhas, points, race_time, laps e status também
# não entram porque representam resultado/performance final.

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

TARGET = "vitoria"
GROUP = "race_key"


# ============================================================
# FUNÇÕES MINIO / DUCKDB
# ============================================================

def s3_uri(path: str) -> str:
    """Monta URI S3 para o MinIO."""
    return f"s3://{MINIO_BUCKET}/{path}"


def configure_duckdb(
    con: duckdb.DuckDBPyConnection,
) -> None:
    """Configura DuckDB para acessar o MinIO."""

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
        f"SET s3_use_ssl={'true' if use_ssl else 'false'}"
    )

    con.execute(
        "SET s3_url_style='path'"
    )

    con.execute(
        "SET disabled_optimizers="
        "'statistics_propagation'"
    )


# ============================================================
# LEITURA
# ============================================================

def load_development_dataset(
    con: duckdb.DuckDBPyConnection,
) -> pd.DataFrame:
    """Lê o conjunto de desenvolvimento do MinIO."""

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
# VALIDAÇÃO
# ============================================================

def validate_dataset(
    df: pd.DataFrame,
) -> None:
    """Valida o dataset antes do treinamento."""

    required_columns = set(
        NUMERIC_FEATURES
        + CATEGORICAL_FEATURES
        + [
            TARGET,
            GROUP,
        ]
    )

    missing = (
        required_columns
        - set(df.columns)
    )

    if missing:
        raise ValueError(
            "Colunas necessárias ausentes: "
            + ", ".join(
                sorted(missing)
            )
        )

    # --------------------------------------------------------
    # Target
    # --------------------------------------------------------

    if df[TARGET].isna().any():
        raise ValueError(
            "Existem valores nulos no target."
        )

    target_values = set(
        df[TARGET]
        .astype(bool)
        .unique()
    )

    if not target_values.issubset(
        {True, False}
    ):
        raise ValueError(
            "O target possui valores diferentes "
            "de True/False."
        )

    # --------------------------------------------------------
    # Groups
    # --------------------------------------------------------

    if df[GROUP].isna().any():
        raise ValueError(
            "Existem race_key nulos."
        )

    # --------------------------------------------------------
    # Duplicidade piloto-corrida
    # --------------------------------------------------------

    if {
        GROUP,
        "driver_key",
    }.issubset(df.columns):

        duplicates = df.duplicated(
            subset=[
                GROUP,
                "driver_key",
            ]
        ).sum()

        if duplicates > 0:
            raise ValueError(
                "Existem duplicidades "
                "piloto-corrida: "
                f"{duplicates}"
            )

    # --------------------------------------------------------
    # position não pode estar entre features
    # --------------------------------------------------------

    if "position" in (
        NUMERIC_FEATURES
        + CATEGORICAL_FEATURES
    ):
        raise ValueError(
            "A variável position não pode "
            "ser utilizada como feature."
        )

    print(
        "=== VALIDAÇÃO DO DATASET ==="
    )

    print(
        f"Registros: {len(df)}"
    )

    print(
        f"Corridas: {df[GROUP].nunique()}"
    )

    print(
        f"Vitórias: {int(df[TARGET].sum())}"
    )

    print(
        "Não vitórias: "
        f"{int((~df[TARGET].astype(bool)).sum())}"
    )


# ============================================================
# PRÉ-PROCESSAMENTO
# ============================================================

def build_preprocessor():
    """
    Cria o pré-processamento.

    IMPORTANTE:
        O imputador e o encoder são ajustados somente
        dentro do treinamento de cada fold através do Pipeline.
    """

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
                ),
            ),
        ]
    )

    preprocessor = ColumnTransformer(
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

    return preprocessor


# ============================================================
# MODELOS
# ============================================================

def build_models():
    """
    Cria os três modelos da primeira rodada.

    class_weight='balanced' é utilizado devido ao forte
    desbalanceamento do target.
    """

    return {
        "Logistic Regression": LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=42,
        ),

        "Decision Tree": DecisionTreeClassifier(
            class_weight="balanced",
            random_state=42,
        ),

        "Random Forest": RandomForestClassifier(
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
    """Cria Pipeline completo."""

    preprocessor = build_preprocessor()

    return Pipeline(
        steps=[
            (
                "preprocessor",
                preprocessor,
            ),
            (
                "model",
                model,
            ),
        ]
    )


# ============================================================
# MÉTRICAS
# ============================================================

def calculate_metrics(
    y_true,
    y_pred,
    y_score,
) -> dict:
    """
    Calcula métricas de classificação.

    ROC-AUC utiliza as probabilidades quando disponíveis.
    """

    metrics = {
        "accuracy": accuracy_score(
            y_true,
            y_pred,
        ),

        "precision": precision_score(
            y_true,
            y_pred,
            zero_division=0,
        ),

        "recall": recall_score(
            y_true,
            y_pred,
            zero_division=0,
        ),

        "f1": f1_score(
            y_true,
            y_pred,
            zero_division=0,
        ),
    }

    if (
        y_score is not None
        and len(
            np.unique(y_true)
        ) == 2
    ):
        metrics["roc_auc"] = (
            roc_auc_score(
                y_true,
                y_score,
            )
        )
    else:
        metrics["roc_auc"] = np.nan

    return metrics


# ============================================================
# TREINAMENTO / VALIDAÇÃO CRUZADA
# ============================================================

def evaluate_model(
    name: str,
    model,
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
):
    """
    Avalia um modelo utilizando GroupKFold.

    Cada race_key permanece integralmente em um único fold.
    """

    print()
    print(
        f"=== {name.upper()} ==="
    )

    pipeline = build_pipeline(
        model
    )

    # --------------------------------------------------------
    # GroupKFold
    # --------------------------------------------------------

    n_groups = groups.nunique()

    if n_groups < 3:
        raise ValueError(
            "São necessárias pelo menos "
            "3 corridas para GroupKFold."
        )

    cv = GroupKFold(
        n_splits=n_groups
    )

    # --------------------------------------------------------
    # Previsões out-of-fold
    # --------------------------------------------------------

    y_pred = cross_val_predict(
        pipeline,
        X,
        y,
        cv=cv,
        groups=groups,
        method="predict",
    )

    # --------------------------------------------------------
    # Probabilidades
    # --------------------------------------------------------

    try:

        y_score = cross_val_predict(
            pipeline,
            X,
            y,
            cv=cv,
            groups=groups,
            method="predict_proba",
        )[:, 1]

    except AttributeError:

        y_score = None

    # --------------------------------------------------------
    # Métricas
    # --------------------------------------------------------

    metrics = calculate_metrics(
        y,
        y_pred,
        y_score,
    )

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

    if pd.notna(
        metrics["roc_auc"]
    ):

        print(
            f"ROC-AUC  : "
            f"{metrics['roc_auc']:.4f}"
        )

    else:

        print(
            "ROC-AUC  : não disponível"
        )

    return metrics


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=== TREINAMENTO INICIAL "
        "DOS MODELOS ==="
    )

    print(
        "Base: desenvolvimento"
    )

    print(
        "Validação: GroupKFold por race_key"
    )

    print(
        "Teste final 2024–2025: NÃO utilizado"
    )

    print()

    con = duckdb.connect()

    try:

        # ----------------------------------------------------
        # 1. Configuração
        # ----------------------------------------------------

        configure_duckdb(
            con
        )

        # ----------------------------------------------------
        # 2. Leitura
        # ----------------------------------------------------

        print(
            "=== LEITURA ==="
        )

        print(
            f"Origem: "
            f"{s3_uri(DEVELOPMENT_S3)}"
        )

        df = load_development_dataset(
            con
        )

        # ----------------------------------------------------
        # 3. Validação
        # ----------------------------------------------------

        validate_dataset(
            df
        )

        # ----------------------------------------------------
        # 4. Features / target / grupos
        # ----------------------------------------------------

        X = df[
            NUMERIC_FEATURES
            + CATEGORICAL_FEATURES
        ].copy()

        y = (
            df[TARGET]
            .astype(int)
        )

        groups = df[
            GROUP
        ].copy()

        # ----------------------------------------------------
        # 5. Mostrar estrutura
        # ----------------------------------------------------

        print()
        print(
            "=== CONFIGURAÇÃO ==="
        )

        print(
            f"Features numéricas: "
            f"{len(NUMERIC_FEATURES)}"
        )

        print(
            f"Features categóricas: "
            f"{len(CATEGORICAL_FEATURES)}"
        )

        print(
            f"Total de features: "
            f"{len(NUMERIC_FEATURES) + len(CATEGORICAL_FEATURES)}"
        )

        print(
            f"Grupos (race_key): "
            f"{groups.nunique()}"
        )

        # ----------------------------------------------------
        # 6. Modelos
        # ----------------------------------------------------

        models = build_models()

        results = []

        # ----------------------------------------------------
        # 7. Avaliação
        # ----------------------------------------------------

        for name, model in models.items():

            metrics = evaluate_model(
                name,
                model,
                X,
                y,
                groups,
            )

            results.append(
                {
                    "modelo": name,
                    **metrics,
                }
            )

        # ----------------------------------------------------
        # 8. Matriz de comparação
        # ----------------------------------------------------

        results_df = pd.DataFrame(
            results
        )

        results_df = results_df.sort_values(
            "f1",
            ascending=False,
        ).reset_index(
            drop=True
        )

        print()
        print(
            "=== COMPARAÇÃO DOS MODELOS ==="
        )

        print(
            results_df.to_string(
                index=False
            )
        )

        # ----------------------------------------------------
        # 9. Salvar resultado local
        # ----------------------------------------------------

        output_file = (
            OUTPUT_DIR
            / "model_comparison.csv"
        )

        results_df.to_csv(
            output_file,
            index=False,
        )

        print()
        print(
            "=== RESULTADO SALVO ==="
        )

        print(
            output_file
        )

        # ----------------------------------------------------
        # 10. Conclusão
        # ----------------------------------------------------

        print()
        print(
            "=== TREINAMENTO INICIAL "
            "CONCLUÍDO ==="
        )

        print(
            "Nenhum dado do teste 2024–2025 "
            "foi utilizado."
        )

        print(
            "Nenhum tuning de hiperparâmetros "
            "foi realizado."
        )

    finally:

        con.close()


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    main()