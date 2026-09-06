"""
Preparação base dos dados para modelagem — Dataset ML Interlagos.

IMPORTANTE:
Este script NÃO ajusta imputadores nem encoders sobre o dataset completo.

Ele:
- lê o Dataset ML do MinIO;
- seleciona as features aprovadas;
- normaliza apenas a variável booleana rainfall_ocorreu;
- mantém valores nulos para que o tratamento seja aprendido dentro
  de cada fold/conjunto de treinamento;
- separa conceitualmente features, target e race_key;
- materializa uma base RAW de modelagem no MinIO.

O pré-processamento que aprende parâmetros dos dados (mediana,
categorias etc.) deverá ocorrer dentro do Pipeline do treinamento,
após a separação dos dados e, principalmente, dentro de cada fold
de validação cruzada.

Não treina modelos.
Não altera Gold.
Não altera o Dataset ML original.
"""

import os
from pathlib import Path

import duckdb
import pandas as pd


# ============================================================
# CONFIGURAÇÕES
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = ROOT / "dataset" / "prepared"
OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


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


# ============================================================
# ORIGEM E DESTINO
# ============================================================

DATASET_ML_S3 = (
    "ml/dataset/dataset_ml_interlagos.parquet"
)

OUTPUT_S3 = (
    "ml/prepared/model_data_base.parquet"
)


# ============================================================
# FEATURES
# ============================================================

# Features numéricas aprovadas para a modelagem.
#
# IMPORTANTE:
# Estas variáveis são mantidas em estado RAW.
# Nenhuma imputação ou transformação que aprenda parâmetros
# do dataset é realizada aqui.

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


# Features categóricas.
CATEGORICAL_FEATURES = [

    "primeiro_composto",

    "composto_mais_utilizado",
]


# Features booleanas.
BOOLEAN_FEATURES = [

    "rainfall_ocorreu",
]


# Target.
TARGET = "vitoria"


# Grupo utilizado posteriormente na validação cruzada.
GROUP = "race_key"


# ============================================================
# RASTREABILIDADE
# ============================================================

TRACEABILITY_COLUMNS = [

    "pilot_race_key",

    "race_key",

    "driver_key",

    "team_key",

    "season",

    "round",

    "full_name",

    "constructor_name",
]


# ============================================================
# COLUNAS FINAIS
# ============================================================

SELECTED_COLUMNS = (

    TRACEABILITY_COLUMNS

    + NUMERIC_FEATURES

    + CATEGORICAL_FEATURES

    + BOOLEAN_FEATURES

    + [TARGET]
)


# ============================================================
# MINIO / DUCKDB
# ============================================================

def s3_uri(
    path: str,
) -> str:
    """
    Monta o URI S3 utilizado pelo DuckDB
    para acessar o MinIO.
    """

    return (
        f"s3://{MINIO_BUCKET}/{path}"
    )


def configure_duckdb(
    con: duckdb.DuckDBPyConnection,
) -> None:
    """
    Configura o DuckDB para leitura e escrita no MinIO.
    """

    con.execute(
        "INSTALL httpfs"
    )

    con.execute(
        "LOAD httpfs"
    )

    endpoint = (
        MINIO_ENDPOINT
        .replace("http://", "")
        .replace("https://", "")
    )

    use_ssl = (
        MINIO_ENDPOINT.startswith(
            "https://"
        )
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

    # Workaround utilizado no projeto para problemas
    # de statistics propagation envolvendo MinIO.
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
    """
    Lê o Dataset ML original diretamente do MinIO.
    """

    uri = s3_uri(
        DATASET_ML_S3
    )

    return con.execute(
        f"""
        SELECT *
        FROM read_parquet('{uri}')
        """
    ).df()


# ============================================================
# NORMALIZAÇÃO BOOLEAN
# ============================================================

def normalize_boolean(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Normaliza rainfall_ocorreu para boolean
    sem realizar imputação.

    Nenhum valor numérico ou categórico recebe
    imputação nesta etapa.
    """

    result = df.copy()

    def convert(value):

        if pd.isna(value):
            return pd.NA

        if isinstance(value, bool):
            return value

        if (
            isinstance(
                value,
                (int, float),
            )
            and value in (0, 1)
        ):
            return bool(value)

        text = (
            str(value)
            .strip()
            .lower()
        )

        if text in {
            "true",
            "1",
            "sim",
            "yes",
        }:
            return True

        if text in {
            "false",
            "0",
            "não",
            "nao",
            "no",
        }:
            return False

        raise ValueError(
            "Valor inesperado em "
            "rainfall_ocorreu: "
            f"{value!r}"
        )

    result[
        "rainfall_ocorreu"
    ] = result[
        "rainfall_ocorreu"
    ].map(convert)

    return result


# ============================================================
# VALIDAÇÃO DA ENTRADA
# ============================================================

def validate_input(
    df: pd.DataFrame,
) -> None:
    """
    Valida se o Dataset ML possui todas as
    colunas necessárias.
    """

    required = set(
        SELECTED_COLUMNS
    )

    missing = sorted(
        required
        - set(df.columns)
    )

    if missing:
        raise ValueError(
            "Colunas obrigatórias ausentes "
            "no Dataset ML: "
            + ", ".join(missing)
        )

    # --------------------------------------------------------
    # Target
    # --------------------------------------------------------

    if df[TARGET].isna().any():

        raise ValueError(
            "O target 'vitoria' "
            "possui valores nulos."
        )

    target_values = set(
        df[TARGET]
        .dropna()
        .astype(bool)
        .unique()
    )

    if not target_values.issubset(
        {True, False}
    ):

        raise ValueError(
            "Valores inesperados "
            f"em 'vitoria': "
            f"{target_values}"
        )

    # --------------------------------------------------------
    # Grupo
    # --------------------------------------------------------

    if df[GROUP].isna().any():

        raise ValueError(
            "Existem race_key nulos."
        )

    # --------------------------------------------------------
    # Chave piloto-corrida
    # --------------------------------------------------------

    if df[
        "pilot_race_key"
    ].isna().any():

        raise ValueError(
            "Existem pilot_race_key nulos."
        )

    # --------------------------------------------------------
    # Duplicidade piloto-corrida
    # --------------------------------------------------------

    if df.duplicated(
        subset=[
            "race_key",
            "driver_key",
        ]
    ).any():

        raise ValueError(
            "Existem duplicidades "
            "piloto-corrida."
        )

    # --------------------------------------------------------
    # Duplicidade pilot_race_key
    # --------------------------------------------------------

    if df.duplicated(
        subset=[
            "pilot_race_key"
        ]
    ).any():

        raise ValueError(
            "Existem duplicidades "
            "em pilot_race_key."
        )

    # --------------------------------------------------------
    # Temporadas
    # --------------------------------------------------------

    seasons = set(
        df["season"]
        .astype(int)
        .unique()
    )

    expected = {
        2018,
        2019,
        2021,
        2022,
        2023,
        2024,
        2025,
    }

    if seasons != expected:

        raise ValueError(
            "Temporadas inesperadas "
            "no Dataset ML. "
            f"Encontradas: "
            f"{sorted(seasons)}"
        )


# ============================================================
# SALVAR NO MINIO
# ============================================================

def save_to_minio(
    con: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
) -> None:
    """
    Salva a base RAW no MinIO.
    """

    con.register(
        "model_data_base",
        df,
    )

    try:

        uri = s3_uri(
            OUTPUT_S3
        )

        con.execute(
            f"""
            COPY model_data_base
            TO '{uri}'
            (
                FORMAT PARQUET,
                OVERWRITE_OR_IGNORE
            )
            """
        )

    finally:

        con.unregister(
            "model_data_base"
        )


# ============================================================
# VALIDAÇÃO DO OUTPUT NO MINIO
# ============================================================

def validate_minio_output(
    con: duckdb.DuckDBPyConnection,
) -> None:
    """
    Valida o arquivo depois da gravação no MinIO.
    """

    uri = s3_uri(
        OUTPUT_S3
    )

    result = con.execute(
        f"""
        SELECT
            COUNT(*) AS registros,

            SUM(
                CASE
                    WHEN vitoria
                    THEN 1
                    ELSE 0
                END
            ) AS vitorias,

            COUNT(
                DISTINCT race_key
            ) AS corridas

        FROM read_parquet(
            '{uri}'
        )
        """
    ).fetchone()

    print(
        "\n=== VALIDAÇÃO DO ARQUIVO "
        "NO MINIO ==="
    )

    print(
        f"Registros: {result[0]}"
    )

    print(
        f"Vitórias: {result[1]}"
    )

    print(
        f"Corridas: {result[2]}"
    )

    if result[0] != 140:

        raise ValueError(
            "A quantidade de registros "
            "no MinIO não corresponde "
            "aos 140 esperados."
        )

    if result[1] != 7:

        raise ValueError(
            "A quantidade de vitórias "
            "no MinIO não corresponde "
            "às 7 esperadas."
        )

    if result[2] != 7:

        raise ValueError(
            "A quantidade de corridas "
            "no MinIO não corresponde "
            "às 7 esperadas."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=== PREPARAÇÃO BASE DOS DADOS "
        "PARA MODELAGEM ==="
    )

    print(
        f"Origem: "
        f"{s3_uri(DATASET_ML_S3)}"
    )

    print()

    print(
        "IMPORTANTE:"
    )

    print(
        "Nenhuma imputação é realizada "
        "nesta etapa."
    )

    print(
        "Nenhum encoder é ajustado "
        "nesta etapa."
    )

    print(
        "O pré-processamento será aprendido "
        "dentro do treinamento/folds."
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

        df = load_dataset(
            con
        )

        # ----------------------------------------------------
        # 3. Validação
        # ----------------------------------------------------

        validate_input(
            df
        )

        # ----------------------------------------------------
        # 4. Normalização booleana
        # ----------------------------------------------------

        base = (
            normalize_boolean(df)
            [
                SELECTED_COLUMNS
            ]
            .copy()
        )

        # ----------------------------------------------------
        # 5. Informações da base
        # ----------------------------------------------------

        total_features = (
            len(NUMERIC_FEATURES)
            + len(CATEGORICAL_FEATURES)
            + len(BOOLEAN_FEATURES)
        )

        print(
            "\n=== DATASET BASE ==="
        )

        print(
            f"Linhas: {len(base)}"
        )

        print(
            f"Colunas: {len(base.columns)}"
        )

        print(
            f"Features: {total_features}"
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
            f"Features booleanas: "
            f"{len(BOOLEAN_FEATURES)}"
        )

        print(
            f"Vitórias: "
            f"{int(base[TARGET].sum())}"
        )

        print(
            "Não vitórias: "
            f"{int((~base[TARGET].astype(bool)).sum())}"
        )

        print(
            f"Corridas: "
            f"{base[GROUP].nunique()}"
        )

        # ----------------------------------------------------
        # 6. Nulos
        # ----------------------------------------------------

        print(
            "\n=== NULOS PRESERVADOS ==="
        )

        features = (
            NUMERIC_FEATURES
            + CATEGORICAL_FEATURES
            + BOOLEAN_FEATURES
        )

        nulls = (
            base[features]
            .isna()
            .sum()
        )

        nulls = nulls[
            nulls > 0
        ]

        if nulls.empty:

            print(
                "Nenhum nulo."
            )

        else:

            for feature, count in (
                nulls.items()
            ):

                print(
                    f"- {feature}: "
                    f"{int(count)}"
                )

        # ----------------------------------------------------
        # 7. Cópia local
        # ----------------------------------------------------

        local_path = (
            OUTPUT_DIR
            / "model_data_base.parquet"
        )

        base.to_parquet(
            local_path,
            index=False,
        )

        # ----------------------------------------------------
        # 8. Salvar MinIO
        # ----------------------------------------------------

        print(
            "\n=== SALVANDO DATASET BASE "
            "NO MINIO ==="
        )

        print(
            f"Destino: "
            f"{s3_uri(OUTPUT_S3)}"
        )

        save_to_minio(
            con,
            base,
        )

        # ----------------------------------------------------
        # 9. Validar MinIO
        # ----------------------------------------------------

        validate_minio_output(
            con
        )

        # ----------------------------------------------------
        # 10. Destinos
        # ----------------------------------------------------

        print(
            "\n=== DESTINOS ==="
        )

        print(
            f"MinIO: "
            f"{s3_uri(OUTPUT_S3)}"
        )

        print(
            f"Local: "
            f"{local_path}"
        )

        # ----------------------------------------------------
        # 11. Próxima etapa
        # ----------------------------------------------------

        print(
            "\n=== PRÓXIMA ETAPA ==="
        )

        print(
            "O split_data.py deverá separar "
            "esta base em desenvolvimento "
            "e teste."
        )

        print(
            "O train_models.py deverá aplicar "
            "imputação, encoding e modelo "
            "dentro de um Pipeline, utilizando "
            "somente os dados de treino "
            "de cada fold."
        )

        print(
            "\nPreparação base concluída."
        )

        print(
            "Nenhum modelo foi treinado."
        )

        print(
            "Nenhuma tabela Gold foi alterada."
        )

        print(
            "O Dataset ML original "
            "não foi alterado."
        )

    finally:

        con.close()


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    main()