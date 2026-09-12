"""
Benchmark de custo computacional dos modelos tunados.

Objetivo:
- medir tempo de treinamento;
- medir tempo de inferência;
- comparar os três modelos finais após tuning;
- usar o mesmo dataset de desenvolvimento e o mesmo conjunto de features.

Importante:
- este script NÃO executa GridSearchCV;
- utiliza diretamente os melhores hiperparâmetros encontrados anteriormente;
- o conjunto de teste 2024–2025 NÃO é utilizado;
- os tempos são dependentes do hardware e do ambiente de execução.
"""

import os
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
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

OUTPUT_FILE = (
    OUTPUT_DIR
    / "model_computational_cost.csv"
)

REPETICOES = 10


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

ALL_FEATURES = (
    NUMERIC_FEATURES
    + CATEGORICAL_FEATURES
)

TARGET = "vitoria"


# ============================================================
# MINIO / DUCKDB
# ============================================================

def s3_uri(path: str) -> str:
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
        f"SET s3_use_ssl={'true' if use_ssl else 'false'}"
    )

    con.execute(
        "SET s3_url_style='path'"
    )

    con.execute(
        "SET disabled_optimizers="
        "'statistics_propagation'"
    )


def load_dataset(
    con: duckdb.DuckDBPyConnection,
) -> pd.DataFrame:

    uri = s3_uri(
        DEVELOPMENT_S3
    )

    df = con.execute(
        f"""
        SELECT *
        FROM read_parquet('{uri}')
        """
    ).df()

    df["rainfall_ocorreu"] = (
        df["rainfall_ocorreu"]
        .astype("Int64")
    )

    return df


# ============================================================
# PRÉ-PROCESSAMENTO
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
                    handle_unknown="ignore",
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
# MODELOS TUNADOS
# ============================================================

def build_models():

    return {
        "Logistic Regression": LogisticRegression(
            C=0.1,
            max_iter=2000,
            class_weight="balanced",
            random_state=42,
        ),

        "Decision Tree": DecisionTreeClassifier(
            max_depth=3,
            min_samples_leaf=4,
            class_weight="balanced",
            random_state=42,
        ),

        "Random Forest": RandomForestClassifier(
            n_estimators=300,
            max_depth=3,
            min_samples_leaf=1,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),
    }


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
# BENCHMARK
# ============================================================

def benchmark_model(
    name: str,
    model,
    X: pd.DataFrame,
    y: pd.Series,
) -> dict:

    tempos_treino = []
    tempos_inferencia = []

    for _ in range(REPETICOES):

        pipeline = build_pipeline(
            model
        )

        inicio_treino = (
            time.perf_counter()
        )

        pipeline.fit(
            X,
            y,
        )

        fim_treino = (
            time.perf_counter()
        )

        inicio_inferencia = (
            time.perf_counter()
        )

        pipeline.predict_proba(
            X
        )

        fim_inferencia = (
            time.perf_counter()
        )

        tempo_treino_ms = (
            fim_treino
            - inicio_treino
        ) * 1000

        tempo_inferencia_ms = (
            fim_inferencia
            - inicio_inferencia
        ) * 1000

        tempos_treino.append(
            tempo_treino_ms
        )

        tempos_inferencia.append(
            tempo_inferencia_ms
        )

    interpretabilidade = {
        "Logistic Regression": "Alta",
        "Decision Tree": "Alta",
        "Random Forest": "Média",
    }

    return {
        "modelo": name,
        "repeticoes": REPETICOES,
        "tempo_treino_ms_mediana": float(
            np.median(
                tempos_treino
            )
        ),
        "tempo_treino_ms_media": float(
            np.mean(
                tempos_treino
            )
        ),
        "tempo_inferencia_ms_mediana": float(
            np.median(
                tempos_inferencia
            )
        ),
        "tempo_inferencia_ms_media": float(
            np.mean(
                tempos_inferencia
            )
        ),
        "interpretabilidade": (
            interpretabilidade[name]
        ),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=== BENCHMARK DOS MODELOS TUNADOS ==="
    )

    print(
        f"Repetições por modelo: "
        f"{REPETICOES}"
    )

    con = duckdb.connect()

    try:

        configure_duckdb(
            con
        )

        df = load_dataset(
            con
        )

    finally:

        con.close()

    missing = (
        set(
            ALL_FEATURES
            + [TARGET]
        )
        - set(df.columns)
    )

    if missing:
        raise ValueError(
            "Colunas ausentes: "
            + ", ".join(
                sorted(missing)
            )
        )

    X = df[
        ALL_FEATURES
    ].copy()

    y = (
        df[TARGET]
        .astype(int)
    )

    print(
        f"Registros utilizados: "
        f"{len(df)}"
    )

    print(
        f"Features utilizadas: "
        f"{len(ALL_FEATURES)}"
    )

    models = build_models()

    results = []

    for name, model in models.items():

        print()
        print(
            f"Executando benchmark: "
            f"{name}"
        )

        result = benchmark_model(
            name,
            model,
            X,
            y,
        )

        results.append(
            result
        )

    results_df = pd.DataFrame(
        results
    )

    results_df = (
        results_df
        .sort_values(
            "tempo_treino_ms_mediana"
        )
        .reset_index(
            drop=True
        )
    )

    results_df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print()
    print(
        "=== RESULTADO ==="
    )

    print(
        results_df.to_string(
            index=False
        )
    )

    print()
    print(
        "Arquivo salvo em:"
    )

    print(
        OUTPUT_FILE
    )

    print()
    print(
        "IMPORTANTE:"
    )

    print(
        "Os tempos representam benchmark local "
        "e dependem do hardware e do ambiente."
    )

    print(
        "O conjunto de teste 2024–2025 "
        "não foi utilizado."
    )


if __name__ == "__main__":
    main()