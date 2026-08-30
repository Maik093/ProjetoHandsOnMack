"""Gera a dimensão Silver de mapeamento entre pilotos FastF1 e Jolpica."""

from io import BytesIO

import boto3
import duckdb
import pyarrow.parquet as pq


# ======================================================================
# CONFIGURAÇÕES
# ======================================================================

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "minioadmin123"

BUCKET = "f1-data-lake"

PNEUS_ORIGEM = "silver/pneus/**/*.parquet"
RESULTADOS_ORIGEM = "silver/resultados/**/*.parquet"
DESTINO = "silver/driver_mapping/driver_mapping.parquet"

MATCH_OK_ESPERADO = 137
AMBIGUO_ESPERADO = 0
SEM_MATCH_ESPERADO = 0


# ======================================================================
# CONEXÕES
# ======================================================================

s3 = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    region_name="us-east-1"
)

con = duckdb.connect()

con.execute("INSTALL httpfs;")
con.execute("LOAD httpfs;")

con.execute(f"""
    SET s3_endpoint='localhost:9000';
    SET s3_access_key_id='{MINIO_ACCESS_KEY}';
    SET s3_secret_access_key='{MINIO_SECRET_KEY}';
    SET s3_use_ssl=false;
    SET s3_url_style='path';
""")


# ======================================================================
# FUNÇÕES
# ======================================================================

def abortar(mensagem):
    """Encerra a execução antes de qualquer gravação no MinIO."""
    raise ValueError(mensagem)


def salvar_parquet_minio(tabela_arrow, caminho):
    """Salva o Parquet somente após todas as validações críticas."""
    buffer = BytesIO()

    pq.write_table(
        tabela_arrow,
        buffer,
        compression="snappy"
    )

    buffer.seek(0)

    s3.put_object(
        Bucket=BUCKET,
        Key=caminho,
        Body=buffer.getvalue(),
        ContentType="application/octet-stream"
    )


# ======================================================================
# LEITURA DAS FONTES
# ======================================================================

print("=" * 70)
print("GERAÇÃO DA DIMENSÃO SILVER - DRIVER MAPPING")
print("=" * 70)

print("Lendo pneus e resultados da camada Silver...")

con.execute(f"""
    CREATE OR REPLACE VIEW pneus_silver AS
    SELECT *
    FROM read_parquet(
        's3://{BUCKET}/{PNEUS_ORIGEM}',
        hive_partitioning=true,
        union_by_name=true
    )
""")

con.execute(f"""
    CREATE OR REPLACE VIEW resultados_silver AS
    SELECT *
    FROM read_parquet(
        's3://{BUCKET}/{RESULTADOS_ORIGEM}',
        hive_partitioning=true,
        union_by_name=true
    )
""")


# ======================================================================
# VALIDAÇÃO DA CHAVE FASTF1 ANTES DO MATCH
# ======================================================================

inconsistencias_fastf1 = con.execute("""
    SELECT
        season,
        driver_id AS fastf1_driver_id,
        COUNT(DISTINCT driver_number) AS numeros_distintos,
        COUNT(DISTINCT event_name) AS eventos_distintos
    FROM pneus_silver
    GROUP BY
        season,
        driver_id
    HAVING
        COUNT(DISTINCT driver_number) > 1
        OR COUNT(DISTINCT event_name) > 1
""").fetchall()

if inconsistencias_fastf1:

    abortar(
        "A chave FastF1 season + fastf1_driver_id não é única "
        "em driver_number ou event_name. Exemplos: "
        f"{inconsistencias_fastf1[:5]}"
    )


# ======================================================================
# MAPEAMENTO
# ======================================================================

query_mapping = """
WITH fastf1 AS (

    SELECT DISTINCT
        season,
        driver_id AS fastf1_driver_id,
        driver_number,
        event_name AS source_event_name
    FROM pneus_silver

),

jolpica AS (

    SELECT DISTINCT
        season,
        driver_id AS jolpica_driver_id,
        driver_number,
        driver_code,
        TRIM(driver_given_name || ' ' || driver_family_name)
            AS driver_name
    FROM resultados_silver

),

jolpica_agrupada AS (

    SELECT
        season,
        driver_number,
        COUNT(*) AS quantidade_candidatos,
        MIN(jolpica_driver_id) AS jolpica_driver_id,
        MIN(driver_code) AS driver_code,
        MIN(driver_name) AS driver_name
    FROM jolpica
    GROUP BY
        season,
        driver_number

),

candidatos AS (

    SELECT
        fastf1.season,
        fastf1.fastf1_driver_id,
        fastf1.driver_number,
        fastf1.source_event_name,
        jolpica_agrupada.jolpica_driver_id,
        jolpica_agrupada.driver_code,
        jolpica_agrupada.driver_name,
        COALESCE(
            jolpica_agrupada.quantidade_candidatos,
            0
        ) AS quantidade_candidatos

    FROM fastf1

    LEFT JOIN jolpica_agrupada
        ON fastf1.season = jolpica_agrupada.season
        AND fastf1.driver_number = jolpica_agrupada.driver_number

)

SELECT
    season,
    fastf1_driver_id,
    driver_number,

    CASE
        WHEN quantidade_candidatos = 1
            AND UPPER(fastf1_driver_id) = UPPER(driver_code)
        THEN jolpica_driver_id
        ELSE NULL
    END AS jolpica_driver_id,

    CASE
        WHEN quantidade_candidatos = 1
            AND UPPER(fastf1_driver_id) = UPPER(driver_code)
        THEN driver_code
        ELSE NULL
    END AS driver_code,

    CASE
        WHEN quantidade_candidatos = 1
            AND UPPER(fastf1_driver_id) = UPPER(driver_code)
        THEN driver_name
        ELSE NULL
    END AS driver_name,

    CASE
        WHEN quantidade_candidatos = 1
            AND UPPER(fastf1_driver_id) = UPPER(driver_code)
        THEN 'NUMBER_AND_CODE'
        WHEN quantidade_candidatos > 1
        THEN 'AMBIGUOUS_NUMBER'
        WHEN quantidade_candidatos = 1
        THEN 'NUMBER_WITH_CODE_MISMATCH'
        ELSE 'NO_CANDIDATE'
    END AS match_method,

    CASE
        WHEN quantidade_candidatos > 1
        THEN 'AMBIGUO'
        WHEN quantidade_candidatos = 1
            AND UPPER(fastf1_driver_id) = UPPER(driver_code)
        THEN 'MATCH_OK'
        ELSE 'SEM_MATCH'
    END AS match_status,

    source_event_name

FROM candidatos

ORDER BY
    season,
    driver_number
"""

tabela_mapping = con.execute(
    query_mapping
).fetch_arrow_table()

con.register(
    "driver_mapping",
    tabela_mapping
)


# ======================================================================
# VALIDAÇÕES CRÍTICAS
# ======================================================================

duplicidades = con.execute("""
    SELECT COUNT(*)
    FROM (
        SELECT
            season,
            fastf1_driver_id,
            COUNT(*) AS quantidade
        FROM driver_mapping
        GROUP BY
            season,
            fastf1_driver_id
        HAVING COUNT(*) > 1
    )
""").fetchone()[0]

if duplicidades > 0:

    abortar(
        "Foram encontrados registros duplicados na chave "
        "season + fastf1_driver_id."
    )


match_ok_ambiguo = con.execute("""
    SELECT COUNT(*)
    FROM driver_mapping
    WHERE
        match_status = 'MATCH_OK'
        AND match_method = 'AMBIGUOUS_NUMBER'
""").fetchone()[0]

if match_ok_ambiguo > 0:

    abortar(
        "Existem registros MATCH_OK marcados como ambíguos."
    )


match_ok_incompleto = con.execute("""
    SELECT COUNT(*)
    FROM driver_mapping
    WHERE
        match_status = 'MATCH_OK'
        AND (
            jolpica_driver_id IS NULL
            OR driver_number IS NULL
            OR driver_code IS NULL
        )
""").fetchone()[0]

if match_ok_incompleto > 0:

    abortar(
        "Existem registros MATCH_OK com campos obrigatórios nulos."
    )


codigos_incompativeis = con.execute("""
    SELECT COUNT(*)
    FROM driver_mapping
    WHERE
        match_status = 'MATCH_OK'
        AND UPPER(fastf1_driver_id) <> UPPER(driver_code)
""").fetchone()[0]

if codigos_incompativeis > 0:

    abortar(
        "Existem registros MATCH_OK com FastF1 driver_id "
        "diferente de driver_code."
    )


resumo = con.execute("""
    SELECT
        season,
        COUNT(*) AS total_fastf1,
        COUNT(*) FILTER (
            WHERE match_status = 'MATCH_OK'
        ) AS match_ok,
        COUNT(*) FILTER (
            WHERE match_status = 'SEM_MATCH'
        ) AS sem_match,
        COUNT(*) FILTER (
            WHERE match_status = 'AMBIGUO'
        ) AS ambiguo
    FROM driver_mapping
    GROUP BY season
    ORDER BY season
""").fetchall()

print()
print("RESUMO DE COBERTURA")
print("season | total_fastf1 | match_ok | sem_match | ambiguo")

for linha in resumo:

    print(
        f"{linha[0]} | {linha[1]} | {linha[2]} | "
        f"{linha[3]} | {linha[4]}"
    )


totais = con.execute("""
    SELECT
        COUNT(*) FILTER (
            WHERE match_status = 'MATCH_OK'
        ) AS match_ok,
        COUNT(*) FILTER (
            WHERE match_status = 'SEM_MATCH'
        ) AS sem_match,
        COUNT(*) FILTER (
            WHERE match_status = 'AMBIGUO'
        ) AS ambiguo,
        COUNT(*) FILTER (
            WHERE season = 2020
        ) AS registros_2020
    FROM driver_mapping
""").fetchone()

if totais[0] != MATCH_OK_ESPERADO:

    abortar(
        f"Quantidade inesperada de MATCH_OK: "
        f"esperado {MATCH_OK_ESPERADO}, encontrado {totais[0]}."
    )

if totais[1] != SEM_MATCH_ESPERADO:

    abortar(
        f"Quantidade inesperada de SEM_MATCH: "
        f"esperado {SEM_MATCH_ESPERADO}, encontrado {totais[1]}."
    )

if totais[2] != AMBIGUO_ESPERADO:

    abortar(
        f"Quantidade inesperada de AMBIGUO: "
        f"esperado {AMBIGUO_ESPERADO}, encontrado {totais[2]}."
    )

if totais[3] != 0:

    abortar(
        "Foram encontrados registros de 2020 em driver_mapping. "
        "A fonte pneus de 2020 deve estar ausente para Interlagos."
    )


# ======================================================================
# PERSISTÊNCIA
# ======================================================================

salvar_parquet_minio(
    tabela_mapping,
    DESTINO
)

print()
print("Validações críticas: OK")
print(f"Dimensão Silver salva em: {DESTINO}")

con.unregister("driver_mapping")
con.close()
