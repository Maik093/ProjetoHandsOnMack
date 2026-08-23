import json
from io import BytesIO

import boto3
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from botocore.exceptions import ClientError


# ======================================================================
# CONFIGURAÇÕES
# ======================================================================

ANO_INICIAL = 2015
ANO_FINAL = 2025

BUCKET = "f1-data-lake"

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "minioadmin123"

PREFIXO_BRONZE = "bronze/jolpica/voltas"
PREFIXO_SILVER = "silver/voltas"


# ======================================================================
# CONEXÃO COM MINIO
# ======================================================================

s3 = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    region_name="us-east-1"
)

print("Conexão com o MinIO estabelecida!")


# ======================================================================
# CONEXÃO COM DUCKDB
# ======================================================================

con = duckdb.connect()

print("DuckDB iniciado!")


# ======================================================================
# FUNÇÃO - VERIFICAR ARQUIVO NO MINIO
# ======================================================================

def arquivo_existe_no_minio(caminho):

    try:

        s3.head_object(
            Bucket=BUCKET,
            Key=caminho
        )

        return True

    except ClientError as erro:

        codigo = (
            erro.response
            .get("Error", {})
            .get("Code")
        )

        if codigo in ["404", "NoSuchKey"]:

            return False

        raise


# ======================================================================
# FUNÇÃO - LER JSON DO MINIO
# ======================================================================

def ler_json_minio(caminho):

    response = s3.get_object(
        Bucket=BUCKET,
        Key=caminho
    )

    conteudo = (
        response["Body"]
        .read()
        .decode("utf-8")
    )

    return json.loads(conteudo)


# ======================================================================
# FUNÇÃO - SALVAR PARQUET NO MINIO
# ======================================================================

def salvar_parquet_minio(tabela_arrow, caminho):

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
# CABEÇALHO
# ======================================================================

print()

print("=" * 70)

print("PRÉ-PROCESSAMENTO - VOLTAS")

print("=" * 70)

print(f"Período: {ANO_INICIAL}-{ANO_FINAL}")

print("Ferramentas: Python + DuckDB + PyArrow")

print("Origem: MinIO / Bronze")

print("Destino: MinIO / Silver")

print()

print("=" * 70)

print("TRATAMENTOS REALIZADOS")

print("=" * 70)

print()

print("1. ACHATAMENTO DO JSON")

print("   Race               -> campos individuais")

print("   Circuit            -> campos individuais")

print("   Location            -> campos individuais")

print("   Laps                -> uma linha por volta/piloto")

print("   Timings             -> uma linha por piloto em cada volta")

print()

print("2. CONVERSÃO DE TIPOS REALIZADA PELO DUCKDB")

print("   season              -> INTEGER")

print("   round               -> INTEGER")

print("   race_date           -> DATE")

print("   race_time           -> mantém valor original")

print("   race_time_millis    -> BIGINT")

print("   total_laps          -> INTEGER")

print("   lap                 -> INTEGER")

print("   position            -> INTEGER")

print()

print("3. TRATAMENTO DOS TEMPOS")

print("   race_time           -> mantém horário original")

print("   race_time_millis    -> milissegundos desde 00:00:00")

print("   lap_time            -> mantém valor original da API")

print("   lap_time_seconds    -> segundos")

print("   lap_time_millis     -> milissegundos")

print()

print("4. PADRONIZAÇÃO TEXTUAL")

print("   Campos VARCHAR -> TRIM()")

print()

print("5. RASTREABILIDADE")

print("   circuit_url -> URL do circuito presente no JSON")

print()

print("6. QUALIDADE")

print("   Chave de duplicidade:")

print("   season + round + lap + driver_id")

print()


# ======================================================================
# CONTROLE
# ======================================================================

temporadas_processadas = 0
temporadas_sem_bronze = []
registros_removidos = 0


# ======================================================================
# PROCESSAMENTO
# ======================================================================

for temporada in range(
    ANO_INICIAL,
    ANO_FINAL + 1
):

    print(f"[{temporada}] Processando...")

    # --------------------------------------------------------------
    # CAMINHO BRONZE
    # --------------------------------------------------------------

    caminho_bronze = (
        f"{PREFIXO_BRONZE}/"
        f"{temporada}/"
        f"interlagos/"
        f"voltas.json"
    )

    # --------------------------------------------------------------
    # VERIFICAR BRONZE
    # --------------------------------------------------------------

    if not arquivo_existe_no_minio(
        caminho_bronze
    ):

        print("  ⚠ Bronze não encontrada.")

        temporadas_sem_bronze.append(
            temporada
        )

        continue


    try:

        # ==========================================================
        # 1. LER JSON
        # ==========================================================

        dados_json = ler_json_minio(
            caminho_bronze
        )


        # ==========================================================
        # 2. EXTRAIR INFORMAÇÕES DA CORRIDA
        # ==========================================================

        season = dados_json.get(
            "season"
        )

        round_number = dados_json.get(
            "round"
        )

        race_name = dados_json.get(
            "raceName"
        )

        race_date = dados_json.get(
            "date"
        )

        race_time = dados_json.get(
            "time"
        )

        total_laps = dados_json.get(
            "totalLaps"
        )


        # ==========================================================
        # 3. EXTRAIR CIRCUITO
        # ==========================================================

        circuit = dados_json.get(
            "circuit",
            {}
        )

        circuit_id = circuit.get(
            "circuitId"
        )

        circuit_name = circuit.get(
            "circuitName"
        )

        circuit_url = circuit.get(
            "url"
        )

        location = circuit.get(
            "Location",
            {}
        )

        circuit_lat = location.get(
            "lat"
        )

        circuit_long = location.get(
            "long"
        )

        circuit_locality = location.get(
            "locality"
        )

        circuit_country = location.get(
            "country"
        )


        # ==========================================================
        # 4. ACHATAR LAPS -> TIMINGS
        # ==========================================================

        registros = []

        laps = dados_json.get(
            "Laps",
            []
        )

        for lap in laps:

            numero_lap = lap.get(
                "number"
            )

            timings = lap.get(
                "Timings",
                []
            )

            for timing in timings:

                registros.append({

                    "season": season,

                    "round": round_number,

                    "race_name": race_name,

                    "race_date": race_date,

                    "race_time": race_time,

                    "total_laps": total_laps,

                    "circuit_id": circuit_id,

                    "circuit_name": circuit_name,

                    "circuit_url": circuit_url,

                    "circuit_lat": circuit_lat,

                    "circuit_long": circuit_long,

                    "circuit_locality": circuit_locality,

                    "circuit_country": circuit_country,

                    "lap": numero_lap,

                    "driver_id": timing.get(
                        "driverId"
                    ),

                    "lap_time": timing.get(
                        "time"
                    ),

                    "position": timing.get(
                        "position"
                    )

                })


        print(
            f"  Registros recebidos: "
            f"{len(registros)}"
        )


        # ==========================================================
        # 5. PYARROW
        # ==========================================================

        tabela_bronze = pa.Table.from_pylist(
            registros
        )


        # ==========================================================
        # 6. REGISTRAR NO DUCKDB
        # ==========================================================

        con.register(
            "dados_bronze",
            tabela_bronze
        )


        # ==========================================================
        # 7. TRANSFORMAÇÕES NO DUCKDB
        # ==========================================================

        query = """

        SELECT

            -- ======================================================
            -- CORRIDA
            -- ======================================================

            CAST(
                season AS INTEGER
            ) AS season,

            CAST(
                round AS INTEGER
            ) AS round,

            TRIM(
                race_name
            ) AS race_name,

            CAST(
                race_date AS DATE
            ) AS race_date,

            -- Mantém o valor original da API
            TRIM(
                race_time
            ) AS race_time,

            -- ======================================================
            -- RACE TIME EM MILISSEGUNDOS
            --
            -- Exemplo:
            --
            -- 17:00:00Z
            --
            -- 17 horas
            -- = 61.200.000 milissegundos
            -- ======================================================

            CASE

                WHEN
                    race_time IS NULL
                    OR TRIM(race_time) = ''

                THEN NULL

                ELSE CAST(

                    EXTRACT(
                        HOUR
                        FROM CAST(
                            REPLACE(
                                TRIM(race_time),
                                'Z',
                                ''
                            )
                            AS TIME
                        )
                    ) * 3600000

                    +

                    EXTRACT(
                        MINUTE
                        FROM CAST(
                            REPLACE(
                                TRIM(race_time),
                                'Z',
                                ''
                            )
                            AS TIME
                        )
                    ) * 60000

                    +

                    EXTRACT(
                        SECOND
                        FROM CAST(
                            REPLACE(
                                TRIM(race_time),
                                'Z',
                                ''
                            )
                            AS TIME
                        )
                    ) * 1000

                    AS BIGINT

                )

            END AS race_time_millis,

            CAST(
                total_laps AS INTEGER
            ) AS total_laps,


            -- ======================================================
            -- CIRCUITO
            -- ======================================================

            TRIM(
                circuit_id
            ) AS circuit_id,

            TRIM(
                circuit_name
            ) AS circuit_name,

            TRIM(
                circuit_url
            ) AS circuit_url,

            CAST(
                circuit_lat AS DOUBLE
            ) AS circuit_lat,

            CAST(
                circuit_long AS DOUBLE
            ) AS circuit_long,

            TRIM(
                circuit_locality
            ) AS circuit_locality,

            TRIM(
                circuit_country
            ) AS circuit_country,


            -- ======================================================
            -- VOLTA
            -- ======================================================

            CAST(
                lap AS INTEGER
            ) AS lap,

            TRIM(
                driver_id
            ) AS driver_id,

            TRIM(
                lap_time
            ) AS lap_time,

            CAST(
                position AS INTEGER
            ) AS position,


            -- ======================================================
            -- TEMPO DA VOLTA EM SEGUNDOS
            --
            -- Exemplo:
            --
            -- 1:30.516
            --
            -- 1 minuto
            -- + 30.516 segundos
            --
            -- = 90.516 segundos
            -- ======================================================

            CASE

                WHEN
                    lap_time IS NULL
                    OR TRIM(lap_time) = ''

                THEN NULL

                WHEN
                    contains(
                        TRIM(lap_time),
                        ':'
                    )

                THEN

                    CAST(
                        split_part(
                            TRIM(lap_time),
                            ':',
                            1
                        ) AS DOUBLE
                    ) * 60

                    +

                    CAST(
                        split_part(
                            TRIM(lap_time),
                            ':',
                            2
                        ) AS DOUBLE
                    )

                ELSE

                    CAST(
                        TRIM(lap_time)
                        AS DOUBLE
                    )

            END AS lap_time_seconds,


            -- ======================================================
            -- TEMPO DA VOLTA EM MILISSEGUNDOS
            --
            -- 1:30.516
            -- =
            -- 90.516 segundos
            -- =
            -- 90516 milissegundos
            -- ======================================================

            CASE

                WHEN
                    lap_time IS NULL
                    OR TRIM(lap_time) = ''

                THEN NULL

                WHEN
                    contains(
                        TRIM(lap_time),
                        ':'
                    )

                THEN CAST(

                    ROUND(

                        (

                            CAST(
                                split_part(
                                    TRIM(lap_time),
                                    ':',
                                    1
                                ) AS DOUBLE
                            ) * 60

                            +

                            CAST(
                                split_part(
                                    TRIM(lap_time),
                                    ':',
                                    2
                                ) AS DOUBLE
                            )

                        ) * 1000

                    ) AS BIGINT

                )

                ELSE CAST(

                    ROUND(

                        CAST(
                            TRIM(lap_time)
                            AS DOUBLE
                        ) * 1000

                    ) AS BIGINT

                )

            END AS lap_time_millis


        FROM dados_bronze

        """


        # ==========================================================
        # 8. EXECUTAR DUCKDB
        # ==========================================================

        resultado = con.execute(
            query
        ).to_arrow_table()


        # ==========================================================
        # 9. VERIFICAR DUPLICIDADES
        # ==========================================================

        print(
            "  Verificando duplicidades..."
        )


        tabela_qualidade = con.execute("""

            SELECT

                COUNT(*) AS registros_recebidos,

                COUNT(
                    DISTINCT (
                        season,
                        round,
                        lap,
                        driver_id
                    )
                ) AS registros_unicos

            FROM dados_bronze

        """).fetchone()


        quantidade_recebida = (
            tabela_qualidade[0]
        )

        quantidade_unica = (
            tabela_qualidade[1]
        )

        duplicidades = (
            quantidade_recebida
            - quantidade_unica
        )


        # ==========================================================
        # 10. REMOVER DUPLICIDADES
        # ==========================================================

        resultado_final = con.execute("""

            SELECT *

            FROM (

                SELECT

                    *,

                    ROW_NUMBER() OVER (

                        PARTITION BY

                            season,
                            round,
                            lap,
                            driver_id

                        ORDER BY

                            position

                    ) AS rn

                FROM resultado_temp

            )

            WHERE rn = 1

            ORDER BY

                season,
                round,
                lap,
                position

        """) if False else None


        # ==========================================================
        # APLICAR DEDUPLICAÇÃO SOBRE O RESULTADO
        # ==========================================================

        con.register(
            "resultado_temp",
            resultado
        )

        resultado_final = con.execute("""

            SELECT

                season,

                round,

                race_name,

                race_date,

                race_time,

                race_time_millis,

                total_laps,

                circuit_id,

                circuit_name,

                circuit_url,

                circuit_lat,

                circuit_long,

                circuit_locality,

                circuit_country,

                lap,

                driver_id,

                lap_time,

                lap_time_seconds,

                lap_time_millis,

                position

            FROM (

                SELECT

                    *,

                    ROW_NUMBER() OVER (

                        PARTITION BY

                            season,
                            round,
                            lap,
                            driver_id

                        ORDER BY

                            position

                    ) AS rn

                FROM resultado_temp

            )

            WHERE rn = 1

            ORDER BY

                season,

                round,

                lap,

                position

        """).to_arrow_table()


        registros_finais = (
            resultado_final.num_rows
        )


        removidos = (
            quantidade_recebida
            - registros_finais
        )


        registros_removidos += removidos


        # ==========================================================
        # 11. QUALIDADE
        # ==========================================================

        print()

        print(
            "  QUALIDADE E RESULTADO"
        )

        print(
            f"  Registros recebidos: "
            f"{quantidade_recebida}"
        )

        print(
            f"  Registros únicos: "
            f"{quantidade_unica}"
        )

        print(
            f"  Duplicidades encontradas: "
            f"{duplicidades}"
        )

        print(
            f"  Registros removidos: "
            f"{removidos}"
        )

        print(
            f"  Registros finais: "
            f"{registros_finais}"
        )


        # ==========================================================
        # 12. SALVAR SILVER
        # ==========================================================

        caminho_silver = (

            f"{PREFIXO_SILVER}/"

            f"season={temporada}/"

            f"voltas.parquet"

        )


        salvar_parquet_minio(
            resultado_final,
            caminho_silver
        )


        print()

        print(
            f"✓ Silver gerada: "
            f"{caminho_silver}"
        )


        temporadas_processadas += 1


    # ==================================================================
    # ERRO DA TEMPORADA
    # ==================================================================

    except Exception as erro:

        print()

        print(
            f"  ✗ Erro ao processar "
            f"{temporada}:"
        )

        print(
            f"    {type(erro).__name__}"
        )

        print(
            f"    {erro}"
        )


# ======================================================================
# RESUMO
# ======================================================================

print()

print("=" * 70)

print(
    "RESUMO DO PRÉ-PROCESSAMENTO"
)

print("=" * 70)

print(
    f"Temporadas processadas: "
    f"{temporadas_processadas}"
)

print(
    f"Temporadas sem Bronze: "
    f"{len(temporadas_sem_bronze)}"
)


if temporadas_sem_bronze:

    print(
        "  "
        + ", ".join(
            map(
                str,
                temporadas_sem_bronze
            )
        )
    )


print(
    f"Registros removidos por duplicidade: "
    f"{registros_removidos}"
)

print("=" * 70)

print(
    "✓ PRÉ-PROCESSAMENTO CONCLUÍDO!"
)

print("=" * 70)


# ======================================================================
# ENCERRAR DUCKDB
# ======================================================================

con.close()