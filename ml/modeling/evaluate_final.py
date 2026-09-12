from pathlib import Path
import json
import platform
from datetime import datetime, timezone

import duckdb
import joblib
import pandas as pd
import sklearn

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
# CONFIGURAÃ‡Ã•ES
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

MODEL_DIR = ROOT / "ml" / "models"

MODEL_PATH = (
    MODEL_DIR
    / "random_forest_interlagos.joblib"
)

MODEL_METADATA_PATH = (
    MODEL_DIR
    / "random_forest_interlagos_metadata.json"
)

MODEL_VERSION = "1.0.0"

LOCAL_RESULTS_DIR = ROOT / "ml" / "results"

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

OUTPUT_RANKING_METRICS = (
    "s3://f1-data-lake/ml/results/final_test_ranking_metrics.csv"
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

FORBIDDEN_FEATURES = {
    "position",
    "posicoes_ganhas",
    "points",
    "race_time",
    "laps",
    "status",
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
# AVALIAÃ‡ÃƒO
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
    """
    Gera a avaliaÃ§Ã£o do modelo dentro de cada corrida.

    A classificaÃ§Ã£o tradicional verifica se o score ultrapassa
    o threshold definido pelo classificador.

    Aqui avaliamos uma segunda perspectiva:
    a capacidade do modelo de ranquear os pilotos dentro da
    mesma corrida.

    Como cada GP possui apenas um vencedor, verificamos:
    - posiÃ§Ã£o do vencedor real no ranking;
    - acerto Top-1;
    - presenÃ§a do vencedor no Top-3;
    - reciprocal rank.
    """

    resultado = test_df.copy()

    resultado["y_pred"] = y_pred
    resultado["score_modelo_vitoria"] = y_proba

    registros = []

    for race_key, grupo in resultado.groupby(
        "race_key",
        sort=True,
    ):
        # ----------------------------------------------------
        # Ordenar pilotos pelo score atribuÃ­do pelo modelo
        # ----------------------------------------------------

        grupo = (
            grupo
            .sort_values(
                "score_modelo_vitoria",
                ascending=False,
            )
            .reset_index(drop=True)
        )

        # Ranking comeÃ§a em 1
        grupo["rank_modelo"] = (
            grupo.index + 1
        )

        # ----------------------------------------------------
        # Localizar vencedor real
        # ----------------------------------------------------

        vencedores_reais = grupo[
            grupo[TARGET].astype(int) == 1
        ]

        if vencedores_reais.empty:

            raise ValueError(
                f"Race {race_key} nÃ£o possui "
                "vencedor real no dataset."
            )

        if len(vencedores_reais) > 1:
            raise ValueError(
                f"Race {race_key} possui mais de "
                "um vencedor no dataset."
            )

        vencedor_real = vencedores_reais.iloc[0]

        # ----------------------------------------------------
        # Piloto Top-1 do modelo
        # ----------------------------------------------------

        top1_modelo = grupo.iloc[0]

        # ----------------------------------------------------
        # PosiÃ§Ã£o do vencedor verdadeiro no ranking
        # ----------------------------------------------------

        posicao_vencedor = int(
            vencedor_real["rank_modelo"]
        )

        acertou_top1 = (
            posicao_vencedor == 1
        )

        acertou_top3 = (
            posicao_vencedor <= 3
        )

        reciprocal_rank = (
            1.0 / posicao_vencedor
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
                "score_vencedor_real": float(
                    vencedor_real[
                        "score_modelo_vitoria"
                    ]
                ),
                "top1_modelo": (
                    top1_modelo["full_name"]
                ),
                "score_top1_modelo": float(
                    top1_modelo[
                        "score_modelo_vitoria"
                    ]
                ),
                "posicao_rank_vencedor_real": (
                    posicao_vencedor
                ),
                "acertou_top1": (
                    acertou_top1
                ),
                "acertou_top3": (
                    acertou_top3
                ),
                "reciprocal_rank": (
                    reciprocal_rank
                ),
            }
        )

    return pd.DataFrame(registros)

def calcular_metricas_ranking(
    race_summary_df,
):
    """
    Calcula mÃ©tricas de ranking considerando cada corrida
    como uma unidade de avaliaÃ§Ã£o.

    MÃ©tricas:
    - Top-1 Accuracy
    - Top-3 Accuracy
    - Mean Winner Rank
    - Mean Reciprocal Rank (MRR)
    """

    if race_summary_df.empty:
        return pd.DataFrame()

    total_corridas = len(
        race_summary_df
    )

    top1_acertos = int(
        race_summary_df[
            "acertou_top1"
        ].sum()
    )

    top3_acertos = int(
        race_summary_df[
            "acertou_top3"
        ].sum()
    )

    top1_accuracy = (
        top1_acertos
        / total_corridas
    )

    top3_accuracy = (
        top3_acertos
        / total_corridas
    )

    mean_winner_rank = (
        race_summary_df[
            "posicao_rank_vencedor_real"
        ].mean()
    )

    mrr = (
        race_summary_df[
            "reciprocal_rank"
        ].mean()
    )

    ranking_metrics_df = pd.DataFrame(
        [
            {
                "modelo": "Random Forest",
                "conjunto": "test",
                "temporadas": "2024-2025",
                "n_corridas": total_corridas,
                "top1_acertos": top1_acertos,
                "top1_accuracy": top1_accuracy,
                "top3_acertos": top3_acertos,
                "top3_accuracy": top3_accuracy,
                "mean_winner_rank": (
                    mean_winner_rank
                ),
                "mrr": mrr,
            }
        ]
    )

    return ranking_metrics_df

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
# PERSISTÃŠNCIA DO MODELO
# ============================================================


def salvar_modelo_local(
    modelo,
    path,
):
    """
    Salva a Pipeline completa treinada.

    O artefato contÃ©m:
    - imputaÃ§Ã£o;
    - normalizaÃ§Ã£o das variÃ¡veis numÃ©ricas;
    - encoding das variÃ¡veis categÃ³ricas;
    - Random Forest treinado.

    Isso permite reutilizar exatamente o mesmo fluxo
    de transformaÃ§Ã£o durante a inferÃªncia.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(
        modelo,
        path,
    )

    return path

def gerar_metadata_modelo(
    metrics_df,
    ranking_metrics_df,
    development,
    test,
):
    """
    Gera metadata tÃ©cnica do modelo final.

    A metadata registra:
    - identidade do modelo;
    - versÃ£o;
    - features utilizadas;
    - target;
    - hiperparÃ¢metros;
    - perÃ­odos de treino e teste;
    - principais mÃ©tricas;
    - limitaÃ§Ãµes de interpretaÃ§Ã£o.
    """

    metadata = {
        "model": {
            "name": "random_forest_interlagos",
            "version": MODEL_VERSION,
            "algorithm": "RandomForestClassifier",
            "artifact": MODEL_PATH.name,
        },

        "objective": {
            "target": TARGET,
            "problem_type": "binary_classification",
            "analytical_use": (
                "historical_explanatory_and_ranking"
            ),
            "description": (
                "Identificar caracterÃ­sticas historicamente "
                "associadas Ã  vitÃ³ria de um piloto em Interlagos "
                "e ranquear pilotos dentro de cada corrida."
            ),
        },

        "features": {
            "numeric": NUMERIC_FEATURES,
            "categorical": CATEGORICAL_FEATURES,
            "total": len(FEATURES),
        },

        "training": {
            "development_seasons": sorted(
                int(x)
                for x in development[
                    "season"
                ].unique()
            ),
            "development_rows": int(
                len(development)
            ),
            "development_races": int(
                development[
                    "race_key"
                ].nunique()
            ),
            "development_wins": int(
                development[
                    TARGET
                ].sum()
            ),
        },

        "test": {
            "test_seasons": sorted(
                int(x)
                for x in test[
                    "season"
                ].unique()
            ),
            "test_rows": int(
                len(test)
            ),
            "test_races": int(
                test[
                    "race_key"
                ].nunique()
            ),
            "test_wins": int(
                test[
                    TARGET
                ].sum()
            ),
        },

        "hyperparameters": {
            "n_estimators": 300,
            "max_depth": 3,
            "min_samples_leaf": 1,
            "class_weight": "balanced",
            "random_state": 42,
            "n_jobs": -1,
        },

        "classification_metrics": {},

        "ranking_metrics": {},

        "interpretation": {
            "classification_threshold": 0.5,
            "score_name": "score_modelo_vitoria",
            "score_is_calibrated_probability": False,
            "warning": (
                "O score do modelo nÃ£o deve ser interpretado "
                "como probabilidade real calibrada de vitÃ³ria."
            ),
        },

        "limitations": [
            (
                "O conjunto possui poucas corridas e poucos "
                "eventos positivos."
            ),
            (
                "O teste final contÃ©m apenas as temporadas "
                "2024 e 2025."
            ),
            (
                "Parte das features Ã© observada durante ou "
                "apÃ³s a corrida."
            ),
            (
                "O modelo atual nÃ£o deve ser apresentado como "
                "previsÃ£o prÃ©-corrida de vitÃ³ria."
            ),
            (
                "Feature importance representa associaÃ§Ã£o "
                "dentro do modelo e nÃ£o causalidade."
            ),
        ],

        "environment": {
            "python_version": (
                platform.python_version()
            ),
            "sklearn_version": (
                sklearn.__version__
            ),
            "created_at_utc": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
        },
    }

    if not metrics_df.empty:

        metricas = metrics_df.iloc[0]

        metadata[
            "classification_metrics"
        ] = {
            "accuracy": float(
                metricas["accuracy"]
            ),
            "precision": float(
                metricas["precision"]
            ),
            "recall": float(
                metricas["recall"]
            ),
            "f1": float(
                metricas["f1"]
            ),
            "roc_auc": float(
                metricas["roc_auc"]
            ),
        }

    if not ranking_metrics_df.empty:

        ranking = (
            ranking_metrics_df.iloc[0]
        )

        metadata[
            "ranking_metrics"
        ] = {
            "top1_hits": int(
                ranking[
                    "top1_acertos"
                ]
            ),
            "top1_accuracy": float(
                ranking[
                    "top1_accuracy"
                ]
            ),
            "top3_hits": int(
                ranking[
                    "top3_acertos"
                ]
            ),
            "top3_accuracy": float(
                ranking[
                    "top3_accuracy"
                ]
            ),
            "mean_winner_rank": float(
                ranking[
                    "mean_winner_rank"
                ]
            ),
            "mrr": float(
                ranking["mrr"]
            ),
        }

    return metadata

def salvar_metadata_local(
    metadata,
    path,
):
    """
    Persiste a metadata do modelo em JSON.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            metadata,
            file,
            ensure_ascii=False,
            indent=4,
        )

    return path

def salvar_resultado_local(
    df,
    filename,
):
    """
    Salva um DataFrame como CSV no diretÃ³rio local de resultados.

    O objetivo Ã© manter no repositÃ³rio os principais artefatos
    de avaliaÃ§Ã£o do modelo, facilitando auditoria, versionamento
    e consulta sem dependÃªncia do MinIO.
    """

    LOCAL_RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        LOCAL_RESULTS_DIR
        / filename
    )

    df.to_csv(
        path,
        index=False,
        encoding="utf-8",
    )

    return path

def validar_datasets_entrada(
    development,
    test,
):
    """
    Valida a consistÃªncia dos datasets de development e test
    antes do treinamento do modelo.

    As validaÃ§Ãµes protegem contra:
    - ausÃªncia de colunas obrigatÃ³rias;
    - target invÃ¡lido;
    - corridas sem exatamente um vencedor;
    - duplicidade na chave piloto x corrida;
    - sobreposiÃ§Ã£o entre development e test;
    - uso acidental de features com leakage;
    - conjuntos contendo apenas uma classe.
    """

    print(
        "\nExecutando validaÃ§Ãµes dos datasets..."
    )

    required_columns = set(
        FEATURES
        + [
            TARGET,
            "pilot_race_key",
            "race_key",
            "season",
            "round",
            "full_name",
        ]
    )

    # --------------------------------------------------------
    # Colunas obrigatÃ³rias
    # --------------------------------------------------------

    for dataset_name, df in [
        ("development", development),
        ("test", test),
    ]:

        missing_columns = (
            required_columns
            - set(df.columns)
        )

        if missing_columns:

            raise ValueError(
                f"{dataset_name}: colunas obrigatÃ³rias "
                f"ausentes: "
                f"{sorted(missing_columns)}"
            )

    # --------------------------------------------------------
    # Features proibidas
    # --------------------------------------------------------

    leakage_features = (
        set(FEATURES)
        & FORBIDDEN_FEATURES
    )

    if leakage_features:

        raise ValueError(
            "Features potencialmente causadoras "
            "de leakage encontradas: "
            f"{sorted(leakage_features)}"
        )

    # --------------------------------------------------------
    # Target binÃ¡rio
    # --------------------------------------------------------

    for dataset_name, df in [
        ("development", development),
        ("test", test),
    ]:

        target_values = set(
            df[TARGET]
            .dropna()
            .astype(int)
            .unique()
        )

        if not target_values.issubset(
            {0, 1}
        ):

            raise ValueError(
                f"{dataset_name}: target contÃ©m "
                f"valores invÃ¡lidos: "
                f"{sorted(target_values)}"
            )

        if df[TARGET].isna().any():

            raise ValueError(
                f"{dataset_name}: target possui "
                "valores nulos."
            )

    # --------------------------------------------------------
    # As duas classes devem existir
    # --------------------------------------------------------

    for dataset_name, df in [
        ("development", development),
        ("test", test),
    ]:

        classes = set(
            df[TARGET]
            .astype(int)
            .unique()
        )

        if classes != {0, 1}:

            raise ValueError(
                f"{dataset_name}: esperado target "
                "com classes 0 e 1, encontrado "
                f"{sorted(classes)}."
            )

    # --------------------------------------------------------
    # Duplicidade piloto x corrida
    # --------------------------------------------------------

    for dataset_name, df in [
        ("development", development),
        ("test", test),
    ]:

        duplicated = df[
            "pilot_race_key"
        ].duplicated()

        if duplicated.any():

            duplicated_keys = (
                df.loc[
                    duplicated,
                    "pilot_race_key",
                ]
                .astype(str)
                .tolist()
            )

            raise ValueError(
                f"{dataset_name}: "
                "pilot_race_key duplicada. "
                f"Exemplos: "
                f"{duplicated_keys[:5]}"
            )

    # --------------------------------------------------------
    # Exatamente um vencedor por corrida
    # --------------------------------------------------------

    for dataset_name, df in [
        ("development", development),
        ("test", test),
    ]:

        winners_per_race = (
            df
            .groupby("race_key")[
                TARGET
            ]
            .sum()
        )

        invalid_races = (
            winners_per_race[
                winners_per_race != 1
            ]
        )

        if not invalid_races.empty:

            raise ValueError(
                f"{dataset_name}: cada corrida "
                "deve possuir exatamente um vencedor. "
                f"Corridas invÃ¡lidas: "
                f"{invalid_races.to_dict()}"
            )

    # --------------------------------------------------------
    # SeparaÃ§Ã£o entre development e test
    # --------------------------------------------------------

    development_races = set(
        development[
            "race_key"
        ].unique()
    )

    test_races = set(
        test[
            "race_key"
        ].unique()
    )

    race_overlap = (
        development_races
        & test_races
    )

    if race_overlap:

        raise ValueError(
            "Existem race_keys simultaneamente "
            "em development e test: "
            f"{sorted(race_overlap)}"
        )

    # --------------------------------------------------------
    # Temporadas esperadas
    # --------------------------------------------------------

    expected_test_seasons = {
        2024,
        2025,
    }

    actual_test_seasons = set(
        test[
            "season"
        ].astype(int)
        .unique()
    )

    if actual_test_seasons != (
        expected_test_seasons
    ):

        raise ValueError(
            "Temporadas inesperadas no test. "
            f"Esperado: "
            f"{sorted(expected_test_seasons)}. "
            f"Encontrado: "
            f"{sorted(actual_test_seasons)}."
        )

    development_seasons = set(
        development[
            "season"
        ].astype(int)
        .unique()
    )

    season_overlap = (
        development_seasons
        & expected_test_seasons
    )

    if season_overlap:

        raise ValueError(
            "Temporadas de teste encontradas "
            "em development: "
            f"{sorted(season_overlap)}"
        )

    print(
        "ValidaÃ§Ã£o dos datasets: OK"
    )

def validar_predicoes(
    test,
    predictions_df,
    race_summary_df,
    ranking_metrics_df,
):
    """
    Valida a consistÃªncia das prediÃ§Ãµes e do ranking
    gerados no conjunto de teste.
    """

    print(
        "\nExecutando validaÃ§Ãµes das prediÃ§Ãµes..."
    )

    # --------------------------------------------------------
    # Quantidade de registros
    # --------------------------------------------------------

    if len(predictions_df) != len(test):

        raise ValueError(
            "Quantidade de prediÃ§Ãµes diferente "
            "da quantidade de registros do test."
        )

    # --------------------------------------------------------
    # Scores nulos
    # --------------------------------------------------------

    if predictions_df[
        "score_modelo_vitoria"
    ].isna().any():

        raise ValueError(
            "Existem scores nulos nas prediÃ§Ãµes."
        )

    # --------------------------------------------------------
    # Faixa do score
    # --------------------------------------------------------

    score_valid = predictions_df[
        "score_modelo_vitoria"
    ].between(
        0,
        1,
        inclusive="both",
    )

    if not score_valid.all():

        raise ValueError(
            "Existem scores fora do intervalo "
            "[0, 1]."
        )

    # --------------------------------------------------------
    # Rank positivo
    # --------------------------------------------------------

    if (
        predictions_df[
            "rank_modelo"
        ] < 1
    ).any():

        raise ValueError(
            "Existem ranks menores que 1."
        )

    # --------------------------------------------------------
    # Rank Ãºnico dentro da corrida
    # --------------------------------------------------------

    duplicated_rank = (
        predictions_df
        .duplicated(
            subset=[
                "race_key",
                "rank_modelo",
            ]
        )
    )

    if duplicated_rank.any():

        raise ValueError(
            "Existem ranks duplicados "
            "dentro da mesma corrida."
        )

    # --------------------------------------------------------
    # Exatamente um Top-1 por corrida
    # --------------------------------------------------------

    top1_per_race = (
        predictions_df
        .groupby("race_key")[
            "eh_top1"
        ]
        .sum()
    )

    if not (
        top1_per_race == 1
    ).all():

        raise ValueError(
            "Cada corrida deve possuir "
            "exatamente um piloto Top-1."
        )

    # --------------------------------------------------------
    # Resumo deve conter todas as corridas
    # --------------------------------------------------------

    expected_races = test[
        "race_key"
    ].nunique()

    summary_races = len(
        race_summary_df
    )

    if summary_races != expected_races:

        raise ValueError(
            "Resumo por corrida nÃ£o contÃ©m "
            "todas as corridas do test. "
            f"Esperado: {expected_races}. "
            f"Encontrado: {summary_races}."
        )

    # --------------------------------------------------------
    # MÃ©trica consolidada
    # --------------------------------------------------------

    if ranking_metrics_df.empty:

        raise ValueError(
            "ranking_metrics_df estÃ¡ vazio."
        )

    ranking_races = int(
        ranking_metrics_df.iloc[0][
            "n_corridas"
        ]
    )

    if ranking_races != expected_races:

        raise ValueError(
            "Quantidade de corridas nas mÃ©tricas "
            "de ranking nÃ£o corresponde ao test."
        )

    print(
        "ValidaÃ§Ã£o das prediÃ§Ãµes: OK"
    )

# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "AVALIAÃ‡ÃƒO FINAL â€” RANDOM FOREST â€” TESTE 2024â€“2025"
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
        f"VitÃ³rias development: "
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
        f"VitÃ³rias test: "
        f"{test[TARGET].sum()}"
    )

    validar_datasets_entrada(
        development,
        test,
    )

    # --------------------------------------------------------
    # ValidaÃ§Ã£o bÃ¡sica dos grupos
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
        "\nValidaÃ§Ã£o de grupos: OK"
    )

    print(
        "Nenhuma race_key do test "
        "estÃ¡ presente no development."
    )

    # --------------------------------------------------------
    # SeparaÃ§Ã£o das features
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
        f"  NumÃ©ricas: "
        f"{len(NUMERIC_FEATURES)}"
    )

    print(
        f"  CategÃ³ricas: "
        f"{len(CATEGORICAL_FEATURES)}"
    )

    # --------------------------------------------------------
    # Criar modelo
    # --------------------------------------------------------

    print(
        "\n" + "-" * 70
    )

    print(
        "CONFIGURAÃ‡ÃƒO DO RANDOM FOREST"
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
        "Treinamento concluÃ­do."
    )

    # --------------------------------------------------------
    # AvaliaÃ§Ã£o final
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
        "MÃ‰TRICAS FINAIS â€” TESTE 2024â€“2025"
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
    # Matriz de confusÃ£o
    # --------------------------------------------------------

    cm = confusion_matrix(
        y_test,
        y_pred,
    )

    print(
        "\nMATRIZ DE CONFUSÃƒO"
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
    # DataFrame de mÃ©tricas
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
    # PrediÃ§Ãµes por piloto
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
        "score_modelo_vitoria"
    ] = y_proba

    predictions_df[
        "modelo"
    ] = "Random Forest"

    predictions_df[
        "rank_modelo"
    ] = (
        predictions_df
        .groupby("race_key")[
            "score_modelo_vitoria"
        ]
        .rank(
            method="first",
            ascending=False,
        )
        .astype(int)
    )

    predictions_df[
        "eh_top1"
    ] = (
        predictions_df[
            "rank_modelo"
        ] == 1
    )

    predictions_df[
        "eh_top3"
    ] = (
        predictions_df[
            "rank_modelo"
        ] <= 3
    )
    # --------------------------------------------------------
    # Resumo por corrida
    # --------------------------------------------------------

    race_summary_df = gerar_resumo_por_corrida(
        test,
        y_pred,
        y_proba,
    )

    ranking_metrics_df = (
        calcular_metricas_ranking(
            race_summary_df
        )
    )

    validar_predicoes(
        test,
        predictions_df,
        race_summary_df,
        ranking_metrics_df,
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
                "top1_modelo",
                "acertou_top1",
                "acertou_top3",
                "posicao_rank_vencedor_real",
                "score_vencedor_real",
                "score_top1_modelo",
                ]
            ].to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # MÃ©tricas de ranking
    # --------------------------------------------------------

    if not ranking_metrics_df.empty:

        ranking = ranking_metrics_df.iloc[0]

        print(
            "\n" + "-" * 70
        )

        print(
            "MÃ‰TRICAS DE RANKING POR CORRIDA"
        )

        print(
            "-" * 70
        )

        print(
            f"TOP-1         : "
            f"{int(ranking['top1_acertos'])}/"
            f"{int(ranking['n_corridas'])} "
            f"({ranking['top1_accuracy']:.2%})"
        )

        print(
            f"TOP-3         : "
            f"{int(ranking['top3_acertos'])}/"
            f"{int(ranking['n_corridas'])} "
            f"({ranking['top3_accuracy']:.2%})"
        )

        print(
            f"MEAN WIN RANK : "
            f"{ranking['mean_winner_rank']:.2f}"
        )

        print(
            f"MRR           : "
            f"{ranking['mrr']:.4f}"
        )

        print(
            "\nATENÃ‡ÃƒO:"
        )

        print(
            "As mÃ©tricas acima foram calculadas sobre "
            f"{int(ranking['n_corridas'])} corridas de teste."
        )

        print(
            "Portanto, devem ser interpretadas como evidÃªncia "
            "experimental e nÃ£o como precisÃ£o geral do modelo."
        )


    # --------------------------------------------------------
    # PersistÃªncia do modelo
    # --------------------------------------------------------

    print(
        "\nPersistindo modelo final..."
    )

    model_saved_path = (
        salvar_modelo_local(
            modelo,
            MODEL_PATH,
        )
    )

    metadata = gerar_metadata_modelo(
        metrics_df,
        ranking_metrics_df,
        development,
        test,
    )

    metadata_saved_path = (
        salvar_metadata_local(
            metadata,
            MODEL_METADATA_PATH,
        )
    )

    print(
        f"Modelo salvo em: "
        f"{model_saved_path}"
    )

    print(
        f"Metadata salva em: "
        f"{metadata_saved_path}"
    )

    # --------------------------------------------------------
    # Salvar resultados localmente
    # --------------------------------------------------------

    print(
        "\nSalvando resultados localmente..."
    )

    local_metrics_path = (
        salvar_resultado_local(
            metrics_df,
            "final_test_metrics.csv",
        )
    )

    local_predictions_path = (
        salvar_resultado_local(
            predictions_df,
            "final_test_predictions.csv",
        )
    )

    local_race_summary_path = (
        salvar_resultado_local(
            race_summary_df,
            "final_test_race_summary.csv",
        )
    )

    local_ranking_metrics_path = None

    if not ranking_metrics_df.empty:

        local_ranking_metrics_path = (
            salvar_resultado_local(
                ranking_metrics_df,
                "final_test_ranking_metrics.csv",
            )
        )

    print(
        f"MÃ©tricas locais: "
        f"{local_metrics_path}"
    )

    print(
        f"PrediÃ§Ãµes locais: "
        f"{local_predictions_path}"
    )

    print(
        f"Resumo por corrida local: "
        f"{local_race_summary_path}"
    )

    if local_ranking_metrics_path is not None:

        print(
            f"MÃ©tricas de ranking locais: "
            f"{local_ranking_metrics_path}"
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

    if not ranking_metrics_df.empty:

        salvar_minio(
            con,
            ranking_metrics_df,
            OUTPUT_RANKING_METRICS,
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
        OUTPUT_RANKING_METRICS
    )

    print(
        "\nAvaliaÃ§Ã£o final concluÃ­da."
    )


if __name__ == "__main__":
    main()
