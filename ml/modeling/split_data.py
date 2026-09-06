"""
Separação dos dados para modelagem — Dataset ML Interlagos.

Estratégia:
- manter corridas inteiras no mesmo conjunto;
- desenvolvimento: 2018, 2019, 2021, 2022 e 2023;
- teste final: 2024 e 2025;
- dentro do desenvolvimento, preservar race_key para validação
  cruzada agrupada durante treinamento/tuning.

A origem é o model_data_base.parquet, que contém:
- identificadores;
- season;
- features;
- target vitoria.

Os conjuntos de desenvolvimento e teste são materializados
diretamente no MinIO.

Este script NÃO treina modelos.
"""

import os
from pathlib import Path

import duckdb
import pandas as pd


# ============================================================
# CONFIGURAÇÕES
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

# Diretório local apenas para arquivos auxiliares/inspeção.
OUTPUT_DIR = ROOT / "dataset" / "prepared" / "splits"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# MinIO
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# Origem oficial
# ------------------------------------------------------------

# IMPORTANTE:
# Esta é a nova base criada pelo prepare_model_data.py.
# Ela já contém a coluna season.
BASE_S3 = "ml/prepared/model_data_base.parquet"


# ------------------------------------------------------------
# Destino dos splits no MinIO
# ------------------------------------------------------------

MINIO_OUTPUT_PREFIX = "ml/prepared/splits"


# ------------------------------------------------------------
# Estratégia temporal
# ------------------------------------------------------------

# Corridas de 2024 e 2025 ficam reservadas para o teste final.
TEST_SEASONS = {
    2024,
    2025,
}


# Temporadas esperadas no Dataset ML enriquecido.
EXPECTED_SEASONS = {
    2018,
    2019,
    2021,
    2022,
    2023,
    2024,
    2025,
}


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def s3_uri(path: str) -> str:
    """
    Monta o URI S3 utilizado pelo DuckDB para acessar o MinIO.
    """
    return f"s3://{MINIO_BUCKET}/{path}"


def configure_duckdb(
    con: duckdb.DuckDBPyConnection,
) -> None:
    """
    Configura o DuckDB para leitura e escrita no MinIO.
    """

    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")

    endpoint = (
        MINIO_ENDPOINT
        .replace("http://", "")
        .replace("https://", "")
    )

    use_ssl = MINIO_ENDPOINT.startswith("https://")

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

    # Workaround utilizado no projeto para problemas de
    # statistics propagation em operações envolvendo MinIO.
    con.execute(
        "SET disabled_optimizers='statistics_propagation'"
    )


# ============================================================
# LEITURA DA BASE
# ============================================================

def load_base_dataset(
    con: duckdb.DuckDBPyConnection,
) -> pd.DataFrame:
    """
    Lê o model_data_base.parquet diretamente do MinIO.

    IMPORTANTE:
    Não há mais necessidade de recuperar season do
    dataset_ml_interlagos.parquet, pois season já faz parte
    da base model_data_base.parquet.
    """

    base_uri = s3_uri(BASE_S3)

    df = con.execute(
        f"""
        SELECT *
        FROM read_parquet('{base_uri}')
        """
    ).df()

    return df


# ============================================================
# VALIDAÇÃO DA BASE DE ENTRADA
# ============================================================

def validate_dataset(
    df: pd.DataFrame,
) -> None:
    """
    Valida o dataset antes da separação.
    """

    required = {
        "race_key",
        "season",
        "vitoria",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            "Colunas necessárias ausentes: "
            + ", ".join(sorted(missing))
        )

    # --------------------------------------------------------
    # Nulos
    # --------------------------------------------------------

    if df["season"].isna().any():
        raise ValueError(
            "Existem temporadas nulas."
        )

    if df["race_key"].isna().any():
        raise ValueError(
            "Existem race_key nulos."
        )

    if df["vitoria"].isna().any():
        raise ValueError(
            "Existem valores nulos no target."
        )

    # --------------------------------------------------------
    # Temporadas
    # --------------------------------------------------------

    seasons = set(
        df["season"]
        .astype(int)
        .unique()
    )

    if seasons != EXPECTED_SEASONS:
        raise ValueError(
            "As temporadas encontradas não correspondem "
            "ao Dataset ML esperado. "
            f"Encontradas: {sorted(seasons)}"
        )

    # --------------------------------------------------------
    # Target
    # --------------------------------------------------------

    if df["vitoria"].sum() == 0:
        raise ValueError(
            "Nenhuma vitória encontrada no dataset."
        )

    # --------------------------------------------------------
    # Duplicidade piloto-corrida
    # --------------------------------------------------------

    if {
        "race_key",
        "driver_key",
    }.issubset(df.columns):

        duplicated_pilot_race = df.duplicated(
            subset=[
                "race_key",
                "driver_key",
            ]
        ).sum()

        if duplicated_pilot_race > 0:
            raise ValueError(
                "Existem duplicidades na granularidade "
                "piloto-corrida: "
                f"{duplicated_pilot_race}"
            )

    # --------------------------------------------------------
    # Resumo
    # --------------------------------------------------------

    print("=== VALIDAÇÃO DO DATASET ===")
    print(f"Linhas: {len(df)}")
    print(f"Colunas: {len(df.columns)}")
    print(
        f"Corridas: {df['race_key'].nunique()}"
    )
    print(
        f"Vitórias: {int(df['vitoria'].sum())}"
    )
    print(
        "Não vitórias: "
        f"{int((~df['vitoria'].astype(bool)).sum())}"
    )
    print(
        f"Temporadas: {sorted(seasons)}"
    )


# ============================================================
# SEPARAÇÃO
# ============================================================

def split_by_race(
    df: pd.DataFrame,
):
    """
    Separa o dataset por temporada, preservando
    corridas inteiras.

    Desenvolvimento:
        2018
        2019
        2021
        2022
        2023

    Teste final:
        2024
        2025
    """

    test_mask = df["season"].isin(
        TEST_SEASONS
    )

    development = df.loc[
        ~test_mask
    ].copy()

    test = df.loc[
        test_mask
    ].copy()

    # --------------------------------------------------------
    # Validação por race_key
    # --------------------------------------------------------

    development_races = set(
        development["race_key"].unique()
    )

    test_races = set(
        test["race_key"].unique()
    )

    intersection = (
        development_races
        & test_races
    )

    if intersection:
        raise ValueError(
            "Existem race_key compartilhados entre "
            "desenvolvimento e teste: "
            + ", ".join(
                map(
                    str,
                    sorted(intersection),
                )
            )
        )

    # --------------------------------------------------------
    # Garantir existência de vitórias
    # --------------------------------------------------------

    if development["vitoria"].sum() == 0:
        raise ValueError(
            "O conjunto de desenvolvimento "
            "não possui nenhuma vitória."
        )

    if test["vitoria"].sum() == 0:
        raise ValueError(
            "O conjunto de teste "
            "não possui nenhuma vitória."
        )

    return development, test


# ============================================================
# PERSISTÊNCIA NO MINIO
# ============================================================

def save_dataframe_to_minio(
    con: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    minio_path: str,
    format_name: str = "PARQUET",
) -> None:
    """
    Materializa um DataFrame diretamente no MinIO.
    """

    relation_name = "data_to_save"

    con.register(
        relation_name,
        df,
    )

    try:

        uri = s3_uri(
            minio_path
        )

        con.execute(
            f"""
            COPY {relation_name}
            TO '{uri}'
            (
                FORMAT {format_name},
                OVERWRITE_OR_IGNORE
            )
            """
        )

    finally:

        con.unregister(
            relation_name
        )


# ============================================================
# CÓPIA LOCAL
# ============================================================

def save_local_copy(
    df: pd.DataFrame,
    filename: str,
) -> None:
    """
    Salva uma cópia local apenas para inspeção.

    A persistência oficial dos splits é o MinIO.
    """

    output_path = (
        OUTPUT_DIR / filename
    )

    df.to_parquet(
        output_path,
        index=False,
    )


# ============================================================
# RESUMO
# ============================================================

def print_summary(
    name: str,
    df: pd.DataFrame,
) -> None:
    """
    Exibe resumo detalhado do conjunto.
    """

    races = (
        df[
            [
                "season",
                "race_key",
            ]
        ]
        .drop_duplicates()
        .sort_values(
            [
                "season",
                "race_key",
            ]
        )
    )

    print()
    print(
        f"=== {name} ==="
    )

    print(
        f"Registros: {len(df)}"
    )

    print(
        f"Corridas: {df['race_key'].nunique()}"
    )

    print(
        f"Vitórias: {int(df['vitoria'].sum())}"
    )

    print(
        "Não vitórias: "
        f"{int((~df['vitoria'].astype(bool)).sum())}"
    )

    print()
    print("Temporadas:")

    print(
        df.groupby("season")
        .agg(
            registros=(
                "vitoria",
                "size",
            ),
            vitorias=(
                "vitoria",
                "sum",
            ),
        )
        .to_string()
    )

    print()
    print("Race keys:")

    print(
        races.to_string(
            index=False
        )
    )


# ============================================================
# VALIDAÇÃO DA SEPARAÇÃO
# ============================================================

def validate_split_integrity(
    development: pd.DataFrame,
    test: pd.DataFrame,
) -> None:
    """
    Executa as validações finais da separação.
    """

    development_races = set(
        development["race_key"].unique()
    )

    test_races = set(
        test["race_key"].unique()
    )

    shared_races = (
        development_races
        & test_races
    )

    # --------------------------------------------------------
    # Nenhuma corrida compartilhada
    # --------------------------------------------------------

    if shared_races:
        raise ValueError(
            "Falha: existem corridas compartilhadas "
            "entre desenvolvimento e teste: "
            f"{sorted(shared_races)}"
        )

    # --------------------------------------------------------
    # Temporadas
    # --------------------------------------------------------

    if development[
        "season"
    ].isin(TEST_SEASONS).any():

        raise ValueError(
            "Falha: temporada de teste "
            "encontrada no desenvolvimento."
        )

    if (
        ~test["season"].isin(TEST_SEASONS)
    ).any():

        raise ValueError(
            "Falha: temporada fora de "
            "2024–2025 encontrada no teste."
        )

    print()
    print(
        "=== INTEGRIDADE DA SEPARAÇÃO ==="
    )

    print(
        "Race keys compartilhados: "
        f"{len(shared_races)}"
    )

    print(
        "Temporadas de teste no "
        "desenvolvimento: 0"
    )

    print(
        "Temporadas fora de 2024–2025 "
        "no teste: 0"
    )


# ============================================================
# VALIDAÇÃO PÓS-ESCRITA NO MINIO
# ============================================================

def validate_minio_outputs(
    con: duckdb.DuckDBPyConnection,
    development_s3: str,
    test_s3: str,
    development: pd.DataFrame,
    test: pd.DataFrame,
) -> None:
    """
    Lê novamente os arquivos materializados no MinIO
    e compara as quantidades com os DataFrames originais.
    """

    print()
    print(
        "=== VALIDAÇÃO DOS ARQUIVOS NO MINIO ==="
    )

    development_uri = s3_uri(
        development_s3
    )

    test_uri = s3_uri(
        test_s3
    )

    # --------------------------------------------------------
    # Quantidade de registros
    # --------------------------------------------------------

    dev_minio = con.execute(
        f"""
        SELECT COUNT(*)
        FROM read_parquet(
            '{development_uri}'
        )
        """
    ).fetchone()[0]

    test_minio = con.execute(
        f"""
        SELECT COUNT(*)
        FROM read_parquet(
            '{test_uri}'
        )
        """
    ).fetchone()[0]

    # --------------------------------------------------------
    # Quantidade de vitórias
    # --------------------------------------------------------

    dev_wins_minio = con.execute(
        f"""
        SELECT
            SUM(
                CASE
                    WHEN vitoria THEN 1
                    ELSE 0
                END
            )
        FROM read_parquet(
            '{development_uri}'
        )
        """
    ).fetchone()[0]

    test_wins_minio = con.execute(
        f"""
        SELECT
            SUM(
                CASE
                    WHEN vitoria THEN 1
                    ELSE 0
                END
            )
        FROM read_parquet(
            '{test_uri}'
        )
        """
    ).fetchone()[0]

    print(
        "Registros desenvolvimento no MinIO: "
        f"{dev_minio}"
    )

    print(
        "Vitórias desenvolvimento no MinIO: "
        f"{dev_wins_minio}"
    )

    print(
        "Registros teste no MinIO: "
        f"{test_minio}"
    )

    print(
        "Vitórias teste no MinIO: "
        f"{test_wins_minio}"
    )

    # --------------------------------------------------------
    # Comparações
    # --------------------------------------------------------

    if dev_minio != len(development):
        raise ValueError(
            "Quantidade de registros do "
            "desenvolvimento no MinIO "
            "não confere com o DataFrame."
        )

    if test_minio != len(test):
        raise ValueError(
            "Quantidade de registros do "
            "teste no MinIO "
            "não confere com o DataFrame."
        )

    if dev_wins_minio != int(
        development["vitoria"].sum()
    ):
        raise ValueError(
            "Quantidade de vitórias do "
            "desenvolvimento no MinIO "
            "não confere com o DataFrame."
        )

    if test_wins_minio != int(
        test["vitoria"].sum()
    ):
        raise ValueError(
            "Quantidade de vitórias do "
            "teste no MinIO "
            "não confere com o DataFrame."
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print(
        "=== SEPARAÇÃO DOS DADOS "
        "PARA MODELAGEM ==="
    )

    print(
        "Estratégia: separação temporal "
        "por race_key"
    )

    print(
        "Desenvolvimento: "
        "2018, 2019, 2021, 2022 e 2023"
    )

    print(
        "Teste final: 2024 e 2025"
    )

    print()

    con = duckdb.connect()

    try:

        # ----------------------------------------------------
        # 1. Configurar DuckDB / MinIO
        # ----------------------------------------------------

        configure_duckdb(
            con
        )

        # ----------------------------------------------------
        # 2. Ler base oficial
        # ----------------------------------------------------

        print(
            "=== LEITURA DA BASE ==="
        )

        print(
            "Origem:"
        )

        print(
            s3_uri(BASE_S3)
        )

        df = load_base_dataset(
            con
        )

        print(
            f"Registros carregados: {len(df)}"
        )

        print(
            f"Colunas carregadas: {len(df.columns)}"
        )

        # ----------------------------------------------------
        # 3. Validar entrada
        # ----------------------------------------------------

        validate_dataset(
            df
        )

        # ----------------------------------------------------
        # 4. Separar desenvolvimento/teste
        # ----------------------------------------------------

        development, test = split_by_race(
            df
        )

        # ----------------------------------------------------
        # 5. Validar integridade
        # ----------------------------------------------------

        validate_split_integrity(
            development,
            test,
        )

        # ----------------------------------------------------
        # 6. Criar grupos explícitos
        # ----------------------------------------------------

        development_groups = (
            development[
                [
                    "race_key",
                    "season",
                ]
            ]
            .drop_duplicates()
            .sort_values(
                [
                    "season",
                    "race_key",
                ]
            )
        )

        test_groups = (
            test[
                [
                    "race_key",
                    "season",
                ]
            ]
            .drop_duplicates()
            .sort_values(
                [
                    "season",
                    "race_key",
                ]
            )
        )

        # ----------------------------------------------------
        # 7. Definir destinos
        # ----------------------------------------------------

        development_s3 = (
            f"{MINIO_OUTPUT_PREFIX}/"
            "development.parquet"
        )

        test_s3 = (
            f"{MINIO_OUTPUT_PREFIX}/"
            "test.parquet"
        )

        development_groups_s3 = (
            f"{MINIO_OUTPUT_PREFIX}/"
            "development_groups.csv"
        )

        test_groups_s3 = (
            f"{MINIO_OUTPUT_PREFIX}/"
            "test_groups.csv"
        )

        # ----------------------------------------------------
        # 8. Persistência oficial no MinIO
        # ----------------------------------------------------

        print()
        print(
            "=== SALVANDO NO MINIO ==="
        )

        save_dataframe_to_minio(
            con,
            development,
            development_s3,
            "PARQUET",
        )

        save_dataframe_to_minio(
            con,
            test,
            test_s3,
            "PARQUET",
        )

        save_dataframe_to_minio(
            con,
            development_groups,
            development_groups_s3,
            "CSV",
        )

        save_dataframe_to_minio(
            con,
            test_groups,
            test_groups_s3,
            "CSV",
        )

        # ----------------------------------------------------
        # 9. Cópias locais
        # ----------------------------------------------------

        save_local_copy(
            development,
            "development.parquet",
        )

        save_local_copy(
            test,
            "test.parquet",
        )

        # ----------------------------------------------------
        # 10. Mostrar resultados
        # ----------------------------------------------------

        print_summary(
            "DESENVOLVIMENTO",
            development,
        )

        print_summary(
            "TESTE FINAL",
            test,
        )

        # ----------------------------------------------------
        # 11. Mostrar destinos
        # ----------------------------------------------------

        print()
        print(
            "=== DESTINOS NO MINIO ==="
        )

        print(
            f"- {s3_uri(development_s3)}"
        )

        print(
            f"- {s3_uri(test_s3)}"
        )

        print(
            f"- {s3_uri(development_groups_s3)}"
        )

        print(
            f"- {s3_uri(test_groups_s3)}"
        )

        # ----------------------------------------------------
        # 12. Mostrar cópias locais
        # ----------------------------------------------------

        print()
        print(
            "=== CÓPIAS LOCAIS PARA INSPEÇÃO ==="
        )

        print(
            f"- {OUTPUT_DIR / 'development.parquet'}"
        )

        print(
            f"- {OUTPUT_DIR / 'test.parquet'}"
        )

        # ----------------------------------------------------
        # 13. Validar arquivos no MinIO
        # ----------------------------------------------------

        validate_minio_outputs(
            con,
            development_s3,
            test_s3,
            development,
            test,
        )

        # ----------------------------------------------------
        # 14. Próxima etapa
        # ----------------------------------------------------

        print()
        print(
            "=== PRÓXIMA ETAPA ==="
        )

        print(
            "Usar race_key como groups no "
            "conjunto de desenvolvimento "
            "durante a validação cruzada "
            "e o tuning."
        )

        print(
            "Nenhum modelo foi treinado."
        )

        print()
        print(
            "=== SEPARAÇÃO CONCLUÍDA COM SUCESSO ==="
        )

    finally:

        con.close()


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    main()