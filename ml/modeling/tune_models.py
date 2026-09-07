"""
Tuning dos modelos de classificação para vitória em Interlagos.

Estratégia:
- Dataset: development.parquet
- Validação: GroupKFold por race_key
- Métrica principal: F1
- Teste 2024-2025: NÃO utilizado nesta etapa
- Pré-processamento dentro do Pipeline para evitar data leakage
- Modelos:
    * Logistic Regression
    * Decision Tree
    * Random Forest

Features:
- 16 numéricas
- 2 categóricas
- Total: 18

Saídas:
- Exclusivamente no MinIO:
    s3://f1-data-lake/ml/results/tuning_results.csv
    s3://f1-data-lake/ml/results/tuned_model_comparison.csv
"""

import duckdb
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
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier


# ============================================================
# CONFIGURAÇÃO
# ============================================================

MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "minioadmin123"

MINIO_BUCKET = "f1-data-lake"

DEVELOPMENT_S3 = (
    "ml/prepared/splits/development.parquet"
)

RESULTS_PREFIX = "ml/results"

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


# ============================================================
# DUCKDB / MINIO
# ============================================================

def s3_uri(path: str) -> str:
    """
    Monta uma URI S3 apontando para o bucket do MinIO.
    """
    return f"s3://{MINIO_BUCKET}/{path}"


def configurar_duckdb():

    conn = duckdb.connect()

    conn.execute("INSTALL httpfs")
    conn.execute("LOAD httpfs")

    conn.execute(
        f"SET s3_endpoint='{MINIO_ENDPOINT}'"
    )

    conn.execute(
        f"SET s3_access_key_id='{MINIO_ACCESS_KEY}'"
    )

    conn.execute(
        f"SET s3_secret_access_key='{MINIO_SECRET_KEY}'"
    )

    conn.execute(
        "SET s3_use_ssl=false"
    )

    conn.execute(
        "SET s3_url_style='path'"
    )

    conn.execute(
        "SET disabled_optimizers="
        "'statistics_propagation'"
    )

    return conn


# ============================================================
# LEITURA DO DATASET
# ============================================================

def carregar_dataset():

    print("=" * 70)
    print("CARREGANDO DATASET DE DESENVOLVIMENTO")
    print("=" * 70)

    conn = configurar_duckdb()

    uri = s3_uri(
        DEVELOPMENT_S3
    )

    query = f"""
        SELECT *
        FROM read_parquet('{uri}')
    """

    df = conn.execute(query).df()

    conn.close()

    # --------------------------------------------------------
    # Converter rainfall_ocorreu para variável numérica
    # --------------------------------------------------------

    df["rainfall_ocorreu"] = (
        df["rainfall_ocorreu"]
        .astype("Int64")
    )

    print(
        f"Linhas: {len(df)}"
    )

    print(
        f"Colunas: {len(df.columns)}"
    )

    if TARGET not in df.columns:
        raise ValueError(
            "A coluna 'vitoria' não foi encontrada."
        )

    if GROUP not in df.columns:
        raise ValueError(
            "A coluna 'race_key' não foi encontrada."
        )

    print("\nDistribuição do target:")
    print(
        df[TARGET].value_counts()
    )

    print("\nCorridas:")
    print(
        df[GROUP].nunique()
    )

    return df


# ============================================================
# VALIDAÇÃO DAS FEATURES
# ============================================================

def validar_features(df):

    ausentes = [
        coluna
        for coluna in ALL_FEATURES
        if coluna not in df.columns
    ]

    if ausentes:
        raise ValueError(
            "Features ausentes no dataset:\n"
            + "\n".join(ausentes)
        )

    print("\nFeatures utilizadas:")
    print(
        f"  Numéricas: "
        f"{len(NUMERIC_FEATURES)}"
    )

    print(
        f"  Categóricas: "
        f"{len(CATEGORICAL_FEATURES)}"
    )

    print(
        f"  Total: "
        f"{len(ALL_FEATURES)}"
    )


# ============================================================
# PREPROCESSADOR
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
                "onehot",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=False,
                ),
            ),
        ]
    )

    # IMPORTANTE:
    # rainfall_ocorreu está dentro de NUMERIC_FEATURES.
    #
    # Portanto NÃO existe mais um terceiro transformer
    # "boolean" no ColumnTransformer.

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
        ],
        remainder="drop",
    )

    return preprocessador


# ============================================================
# MODELOS E GRID
# ============================================================

def criar_modelos():

    modelos = {}

    # --------------------------------------------------------
    # Logistic Regression
    # --------------------------------------------------------

    pipeline_logistic = Pipeline(
        steps=[
            (
                "preprocessor",
                criar_preprocessador(),
            ),
            (
                "model",
                LogisticRegression(
                    max_iter=2000,
                    random_state=42,
                ),
            ),
        ]
    )

    grid_logistic = {
        "model__C": [
            0.01,
            0.1,
            1,
            10,
        ],
        "model__class_weight": [
            None,
            "balanced",
        ],
    }

    modelos["Logistic Regression"] = (
        pipeline_logistic,
        grid_logistic,
    )

    # --------------------------------------------------------
    # Decision Tree
    # --------------------------------------------------------

    pipeline_tree = Pipeline(
        steps=[
            (
                "preprocessor",
                criar_preprocessador(),
            ),
            (
                "model",
                DecisionTreeClassifier(
                    random_state=42,
                ),
            ),
        ]
    )

    grid_tree = {
        "model__max_depth": [
            2,
            3,
            4,
            5,
        ],
        "model__min_samples_leaf": [
            1,
            2,
            4,
            8,
        ],
        "model__class_weight": [
            None,
            "balanced",
        ],
    }

    modelos["Decision Tree"] = (
        pipeline_tree,
        grid_tree,
    )

    # --------------------------------------------------------
    # Random Forest
    # --------------------------------------------------------

    pipeline_rf = Pipeline(
        steps=[
            (
                "preprocessor",
                criar_preprocessador(),
            ),
            (
                "model",
                RandomForestClassifier(
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    grid_rf = {
        "model__n_estimators": [
            100,
            300,
        ],
        "model__max_depth": [
            None,
            3,
            5,
        ],
        "model__min_samples_leaf": [
            1,
            2,
            4,
        ],
        "model__class_weight": [
            None,
            "balanced",
        ],
    }

    modelos["Random Forest"] = (
        pipeline_rf,
        grid_rf,
    )

    return modelos


# ============================================================
# TUNING
# ============================================================

def executar_tuning(df):

    X = df[
        ALL_FEATURES
    ].copy()

    y = (
        df[TARGET]
        .astype(int)
    )

    groups = df[
        GROUP
    ]

    # --------------------------------------------------------
    # GroupKFold
    # --------------------------------------------------------

    n_groups = groups.nunique()

    if n_groups < 5:
        raise ValueError(
            "São necessárias pelo menos 5 corridas "
            "para GroupKFold(n_splits=5). "
            f"Encontradas: {n_groups}"
        )

    cv = GroupKFold(
        n_splits=5
    )

    modelos = criar_modelos()

    resultados_grid = []

    melhores_modelos = {}

    # --------------------------------------------------------
    # Grid Search
    # --------------------------------------------------------

    for nome, (
        pipeline,
        param_grid,
    ) in modelos.items():

        print("\n")
        print("=" * 70)
        print(
            f"TUNING: {nome}"
        )
        print("=" * 70)

        grid = GridSearchCV(
            estimator=pipeline,
            param_grid=param_grid,
            scoring="f1",
            cv=cv,
            refit=True,
            n_jobs=-1,
            return_train_score=True,
            error_score="raise",
        )

        grid.fit(
            X,
            y,
            groups=groups,
        )

        melhores_modelos[nome] = (
            grid.best_estimator_
        )

        print("\nMelhores parâmetros:")
        print(
            grid.best_params_
        )

        print(
            f"\nMelhor F1 médio CV: "
            f"{grid.best_score_:.4f}"
        )

        cv_results = pd.DataFrame(
            grid.cv_results_
        )

        cv_results["modelo"] = nome

        resultados_grid.append(
            cv_results
        )

    resultados_grid_df = pd.concat(
        resultados_grid,
        ignore_index=True,
    )

    return (
        resultados_grid_df,
        melhores_modelos,
        X,
        y,
        groups,
    )


# ============================================================
# AVALIAÇÃO DOS MELHORES MODELOS
# ============================================================

def avaliar_melhores_modelos(
    melhores_modelos,
    X,
    y,
    groups,
):

    resultados = []

    cv = GroupKFold(
        n_splits=5
    )

    from sklearn.model_selection import (
        cross_val_predict
    )

    for nome, modelo in (
        melhores_modelos.items()
    ):

        print("\n")
        print("=" * 70)
        print(
            f"AVALIAÇÃO CV: {nome}"
        )
        print("=" * 70)

        y_pred = cross_val_predict(
            modelo,
            X,
            y,
            cv=cv,
            groups=groups,
            method="predict",
            n_jobs=-1,
        )

        y_proba = cross_val_predict(
            modelo,
            X,
            y,
            cv=cv,
            groups=groups,
            method="predict_proba",
            n_jobs=-1,
        )[:, 1]

        accuracy = accuracy_score(
            y,
            y_pred,
        )

        precision = precision_score(
            y,
            y_pred,
            zero_division=0,
        )

        recall = recall_score(
            y,
            y_pred,
            zero_division=0,
        )

        f1 = f1_score(
            y,
            y_pred,
            zero_division=0,
        )

        roc_auc = roc_auc_score(
            y,
            y_proba,
        )

        print(
            f"Accuracy : "
            f"{accuracy:.4f}"
        )

        print(
            f"Precision: "
            f"{precision:.4f}"
        )

        print(
            f"Recall   : "
            f"{recall:.4f}"
        )

        print(
            f"F1       : "
            f"{f1:.4f}"
        )

        print(
            f"ROC-AUC  : "
            f"{roc_auc:.4f}"
        )

        resultados.append(
            {
                "modelo": nome,
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "roc_auc": roc_auc,
            }
        )

    return pd.DataFrame(
        resultados
    )


# ============================================================
# SALVAR DIRETAMENTE NO MINIO
# ============================================================

def salvar_dataframe_minio(
    con,
    df,
    path,
):

    uri = s3_uri(path)

    table_name = "resultado_tuning"

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
        f"Gravado no MinIO: {uri}"
    )


def salvar_resultados(
    resultados_grid,
    comparacao,
):

    con = configurar_duckdb()

    try:

        tuning_path = (
            f"{RESULTS_PREFIX}/"
            "tuning_results.csv"
        )

        comparison_path = (
            f"{RESULTS_PREFIX}/"
            "tuned_model_comparison.csv"
        )

        salvar_dataframe_minio(
            con,
            resultados_grid,
            tuning_path,
        )

        salvar_dataframe_minio(
            con,
            comparacao,
            comparison_path,
        )

    finally:

        con.close()


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n")
    print("=" * 70)
    print(
        "TUNING DOS MODELOS — "
        "VITÓRIA EM INTERLAGOS"
    )
    print("=" * 70)

    print("\nEstratégia:")
    print(
        "  Validação : GroupKFold"
    )
    print(
        "  Grupo     : race_key"
    )
    print(
        "  Folds     : 5"
    )
    print(
        "  Métrica   : F1"
    )
    print(
        "  Teste     : NÃO utilizado"
    )
    print(
        "  Target    : vitoria"
    )
    print(
        "  Features  : 18"
    )
    print(
        "  Saída     : somente MinIO"
    )

    # --------------------------------------------------------
    # 1. Dataset
    # --------------------------------------------------------

    df = carregar_dataset()

    validar_features(df)

    # --------------------------------------------------------
    # 2. Tuning
    # --------------------------------------------------------

    (
        resultados_grid,
        melhores_modelos,
        X,
        y,
        groups,
    ) = executar_tuning(df)

    # --------------------------------------------------------
    # 3. Avaliação dos melhores
    # --------------------------------------------------------

    comparacao = (
        avaliar_melhores_modelos(
            melhores_modelos,
            X,
            y,
            groups,
        )
    )

    # --------------------------------------------------------
    # 4. Ordenar por F1
    # --------------------------------------------------------

    comparacao = (
        comparacao
        .sort_values(
            by="f1",
            ascending=False,
        )
        .reset_index(
            drop=True
        )
    )

    # --------------------------------------------------------
    # 5. Salvar somente no MinIO
    # --------------------------------------------------------

    salvar_resultados(
        resultados_grid,
        comparacao,
    )

    # --------------------------------------------------------
    # 6. Resultado final
    # --------------------------------------------------------

    print("\n")
    print("=" * 70)
    print(
        "COMPARAÇÃO FINAL DOS "
        "MODELOS TUNADOS"
    )
    print("=" * 70)

    print(
        comparacao.to_string(
            index=False
        )
    )

    print("\n")
    print("=" * 70)
    print("TUNING CONCLUÍDO")
    print("=" * 70)

    print(
        "\nResultados disponíveis "
        "exclusivamente no MinIO:"
    )

    print(
        s3_uri(
            f"{RESULTS_PREFIX}/"
            "tuning_results.csv"
        )
    )

    print(
        s3_uri(
            f"{RESULTS_PREFIX}/"
            "tuned_model_comparison.csv"
        )
    )

    print(
        "\nO conjunto de teste "
        "2024–2025 permaneceu intocado."
    )


if __name__ == "__main__":
    main()