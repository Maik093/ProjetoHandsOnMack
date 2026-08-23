import json
from io import BytesIO

import boto3
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq


# ======================================================================
# CONFIGURAÇÕES
# ======================================================================

ANO_INICIAL = 2015
ANO_FINAL = 2025

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "minioadmin123"

BUCKET = "f1-data-lake"

# ======================================================================
# CAMINHOS
# ======================================================================

BRONZE_BASE = "bronze/jolpica/calendario"
SILVER_BASE = "silver/calendario"


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

def arquivo_existe(caminho):

    try:

        s3.head_object(
            Bucket=BUCKET,
            Key=caminho
        )

        return True

    except Exception:

        return False


# ======================================================================
# FUNÇÃO - LER JSON DO MINIO
# ======================================================================

def ler_json_minio(caminho):

    response = s3.get_object(
        Bucket=BUCKET,
        Key=caminho
    )

    conteudo = response["Body"].read()

    return json.loads(
        conteudo.decode("utf-8")
    )


# ======================================================================
# FUNÇÃO - SALVAR PARQUET NO MINIO
# ======================================================================

def salvar_parquet_minio(
    tabela_arrow,
    caminho
):

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

print("PRÉ-PROCESSAMENTO - CALENDÁRIO")

print("=" * 70)

print(
    f"Período: {ANO_INICIAL}-{ANO_FINAL}"
)

print(
    "Ferramentas: Python + DuckDB + PyArrow"
)

print(
    "Origem: MinIO / Bronze"
)

print(
    "Destino: MinIO / Silver"
)

print()

print("=" * 70)

print("TRATAMENTOS REALIZADOS")

print("=" * 70)

print()


# ======================================================================
# 1. ESTRUTURAS JSON
# ======================================================================

print(
    "1. ACHATAMENTO DO JSON"
)

print(
    "   Race              -> campos individuais"
)

print(
    "   Circuit           -> campos individuais"
)

print(
    "   Location          -> campos individuais"
)

print(
    "   FirstPractice     -> campos individuais"
)

print(
    "   SecondPractice    -> campos individuais"
)

print(
    "   ThirdPractice     -> campos individuais"
)

print(
    "   Qualifying        -> campos individuais"
)

print()


# ======================================================================
# 2. CONVERSÃO DE TIPOS
# ======================================================================

print(
    "2. CONVERSÃO DE TIPOS REALIZADA PELO DUCKDB"
)

print(
    "   season                    -> INTEGER"
)

print(
    "   round                     -> INTEGER"
)

print(
    "   race_date                 -> DATE"
)

print(
    "   race_time                 -> mantém valor original"
)

print(
    "   race_time_millis          -> BIGINT"
)

print(
    "   circuit_lat               -> DOUBLE"
)

print(
    "   circuit_long              -> DOUBLE"
)

print(
    "   first_practice_date       -> DATE"
)

print(
    "   second_practice_date      -> DATE"
)

print(
    "   third_practice_date       -> DATE"
)

print(
    "   qualifying_date           -> DATE"
)

print()


# ======================================================================
# 3. TRATAMENTO DOS TEMPOS
# ======================================================================

print(
    "3. TRATAMENTO DOS TEMPOS"
)

print(
    "   race_time                 -> mantém valor original da API"
)

print(
    "   race_time_millis          -> milissegundos desde 00:00:00"
)

print()


# ======================================================================
# 4. PADRONIZAÇÃO TEXTUAL
# ======================================================================

print(
    "4. PADRONIZAÇÃO TEXTUAL"
)

print(
    "   Campos VARCHAR            -> TRIM()"
)

print()


# ======================================================================
# 5. RASTREABILIDADE
# ======================================================================

print(
    "5. RASTREABILIDADE"
)

print(
    "   source_url                -> URL presente no MRData.url"
)

print(
    "   race_url                  -> URL da corrida"
)

print(
    "   circuit_url               -> URL do circuito"
)

print()


# ======================================================================
# 6. QUALIDADE
# ======================================================================

print(
    "6. QUALIDADE"
)

print(
    "   Chave de duplicidade:"
)

print(
    "   season + round"
)

print()


# ======================================================================
# CONTROLE GERAL
# ======================================================================

temporadas_processadas = []

temporadas_sem_bronze = []

temporadas_com_erro = []

total_duplicidades_removidas = 0


# ======================================================================
# PROCESSAMENTO
# ======================================================================

for temporada in range(
    ANO_INICIAL,
    ANO_FINAL + 1
):

    print()

    print(
        f"[{temporada}] Processando..."
    )


    # ------------------------------------------------------------------
    # CAMINHOS
    # ------------------------------------------------------------------

    caminho_bronze = (
        f"{BRONZE_BASE}/"
        f"{temporada}/"
        f"calendario.json"
    )

    caminho_silver = (
        f"{SILVER_BASE}/"
        f"season={temporada}/"
        f"calendario.parquet"
    )


    # ------------------------------------------------------------------
    # VERIFICAR BRONZE
    # ------------------------------------------------------------------

    if not arquivo_existe(
        caminho_bronze
    ):

        print(
            "  ⚠ Bronze não encontrada."
        )

        temporadas_sem_bronze.append(
            temporada
        )

        continue


    try:

        # ==============================================================
        # LER JSON
        # ==============================================================

        dados = ler_json_minio(
            caminho_bronze
        )


        # ==============================================================
        # METADADOS DO MRData
        # ==============================================================

        mrdata = dados.get(
            "MRData",
            {}
        )


        source_url = mrdata.get(
            "url"
        )


        # ==============================================================
        # OBTER CORRIDAS
        # ==============================================================

        corridas = (
            mrdata
            .get("RaceTable", {})
            .get("Races", [])
        )


        print(
            f"  Registros recebidos: "
            f"{len(corridas)}"
        )


        # ==============================================================
        # ACHATAMENTO DO JSON
        # ==============================================================
        #
        # Cada corrida vira uma linha.
        #
        # As estruturas aninhadas:
        #
        # Circuit
        # Location
        # FirstPractice
        # SecondPractice
        # ThirdPractice
        # Qualifying
        #
        # são transformadas em campos individuais.
        # ==============================================================

        registros = []


        for corrida in corridas:

            circuito = corrida.get(
                "Circuit",
                {}
            )

            location = circuito.get(
                "Location",
                {}
            )

            first_practice = corrida.get(
                "FirstPractice",
                {}
            )

            second_practice = corrida.get(
                "SecondPractice",
                {}
            )

            third_practice = corrida.get(
                "ThirdPractice",
                {}
            )

            qualifying = corrida.get(
                "Qualifying",
                {}
            )


            registro = {

                # ------------------------------------------------------
                # CORRIDA
                # ------------------------------------------------------

                "season":
                    corrida.get(
                        "season"
                    ),

                "round":
                    corrida.get(
                        "round"
                    ),

                "race_name":
                    corrida.get(
                        "raceName"
                    ),

                "race_date":
                    corrida.get(
                        "date"
                    ),

                "race_time":
                    corrida.get(
                        "time"
                    ),

                "race_url":
                    corrida.get(
                        "url"
                    ),


                # ------------------------------------------------------
                # CIRCUITO
                # ------------------------------------------------------

                "circuit_id":
                    circuito.get(
                        "circuitId"
                    ),

                "circuit_name":
                    circuito.get(
                        "circuitName"
                    ),

                "circuit_url":
                    circuito.get(
                        "url"
                    ),


                # ------------------------------------------------------
                # LOCALIZAÇÃO
                # ------------------------------------------------------

                "circuit_lat":
                    location.get(
                        "lat"
                    ),

                "circuit_long":
                    location.get(
                        "long"
                    ),

                "circuit_locality":
                    location.get(
                        "locality"
                    ),

                "circuit_country":
                    location.get(
                        "country"
                    ),


                # ------------------------------------------------------
                # TREINOS
                # ------------------------------------------------------

                "first_practice_date":
                    first_practice.get(
                        "date"
                    ),

                "second_practice_date":
                    second_practice.get(
                        "date"
                    ),

                "third_practice_date":
                    third_practice.get(
                        "date"
                    ),


                # ------------------------------------------------------
                # CLASSIFICAÇÃO
                # ------------------------------------------------------

                "qualifying_date":
                    qualifying.get(
                        "date"
                    ),


                # ------------------------------------------------------
                # RASTREABILIDADE
                # ------------------------------------------------------

                "source_url":
                    source_url
            }


            registros.append(
                registro
            )


        # ==============================================================
        # CONVERTER PARA PYARROW
        #
        # IMPORTANTE:
        #
        # Não passamos a lista diretamente para:
        #
        # FROM dados_bronze
        #
        # porque DuckDB replacement scan não aceita list.
        #
        # Transformamos primeiro em PyArrow Table.
        # ==============================================================

        tabela_bronze = pa.Table.from_pylist(
            registros
        )


        # ==============================================================
        # REGISTRAR NO DUCKDB
        # ==============================================================

        con.register(
            "dados_bronze",
            tabela_bronze
        )


        # ==============================================================
        # TRANSFORMAÇÕES NO DUCKDB
        # ==============================================================

        query = """

        SELECT

            -- =========================================================
            -- CORRIDA
            -- =========================================================

            CAST(
                season
                AS INTEGER
            ) AS season,

            CAST(
                round
                AS INTEGER
            ) AS round,

            TRIM(
                race_name
            ) AS race_name,

            CAST(
                race_date
                AS DATE
            ) AS race_date,

            -- Mantém o valor original da API
            TRIM(
                race_time
            ) AS race_time,


            -- =========================================================
            -- RACE TIME EM MILISSEGUNDOS
            --
            -- Exemplo:
            --
            -- 16:00:00Z
            --
            -- = 16 horas
            -- = 57.600.000 milissegundos
            --
            -- A conversão é feita somente para facilitar análises.
            -- O valor original continua preservado em race_time.
            -- =========================================================

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


            -- =========================================================
            -- CIRCUITO
            -- =========================================================

            TRIM(
                race_url
            ) AS race_url,

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
                circuit_lat
                AS DOUBLE
            ) AS circuit_lat,

            CAST(
                circuit_long
                AS DOUBLE
            ) AS circuit_long,

            TRIM(
                circuit_locality
            ) AS circuit_locality,

            TRIM(
                circuit_country
            ) AS circuit_country,


            -- =========================================================
            -- TREINOS
            -- =========================================================

            CAST(
                first_practice_date
                AS DATE
            ) AS first_practice_date,

            CAST(
                second_practice_date
                AS DATE
            ) AS second_practice_date,

            CAST(
                third_practice_date
                AS DATE
            ) AS third_practice_date,


            -- =========================================================
            -- CLASSIFICAÇÃO
            -- =========================================================

            CAST(
                qualifying_date
                AS DATE
            ) AS qualifying_date,


            -- =========================================================
            -- RASTREABILIDADE
            -- =========================================================

            TRIM(
                source_url
            ) AS source_url


        FROM dados_bronze

        """


        # ==============================================================
        # EXECUTAR TRANSFORMAÇÕES
        # ==============================================================

        tabela_silver = con.sql(
            query
        ).to_arrow_table()


        # ==============================================================
        # VERIFICAÇÃO DE DUPLICIDADES
        # ==============================================================
        #
        # Não utilizar:
        #
        # COUNT(season, round)
        #
        # porque COUNT() aceita uma expressão, não duas colunas.
        #
        # Usamos GROUP BY season + round.
        # ==============================================================

        print(
            "  Verificando duplicidades..."
        )


        duplicidades_query = """

        SELECT
            season,
            round,
            COUNT(*) AS quantidade

        FROM dados_bronze

        GROUP BY
            season,
            round

        HAVING COUNT(*) > 1

        """


        duplicidades = con.sql(
            duplicidades_query
        ).fetchall()


        quantidade_duplicidades = sum(
            registro[2] - 1
            for registro in duplicidades
        )


        if quantidade_duplicidades > 0:

            print(
                f"  ⚠ Registros duplicados encontrados: "
                f"{quantidade_duplicidades}"
            )

            total_duplicidades_removidas += (
                quantidade_duplicidades
            )

            # ----------------------------------------------------------
            # Remover duplicidades
            #
            # Mantém apenas uma ocorrência de cada
            # season + round.
            # ----------------------------------------------------------

            deduplicacao_query = """

            SELECT *

            FROM (

                SELECT

                    *,

                    ROW_NUMBER() OVER (

                        PARTITION BY
                            season,
                            round

                        ORDER BY
                            race_date

                    ) AS rn

                FROM dados_bronze

            )

            WHERE rn = 1

            """


            tabela_deduplicada = con.sql(
                deduplicacao_query
            ).to_arrow_table()


            # ----------------------------------------------------------
            # Registrar tabela deduplicada
            # ----------------------------------------------------------

            con.register(
                "dados_bronze_deduplicados",
                tabela_deduplicada
            )


            # ----------------------------------------------------------
            # Executar novamente as transformações
            # ----------------------------------------------------------

            tabela_silver = con.sql(
                query.replace(
                    "FROM dados_bronze",
                    "FROM dados_bronze_deduplicados"
                )
            ).to_arrow_table()


        else:

            print(
                "  ✓ Nenhuma duplicidade encontrada."
            )


        # ==============================================================
        # SALVAR SILVER
        # ==============================================================

        salvar_parquet_minio(
            tabela_silver,
            caminho_silver
        )


        # ==============================================================
        # CONTAGEM FINAL
        # ==============================================================

        print(
            f"  Registros Silver: "
            f"{tabela_silver.num_rows}"
        )

        print(
            f"  ✓ Silver salva:"
        )

        print(
            f"    {caminho_silver}"
        )


        temporadas_processadas.append(
            temporada
        )


        # ==============================================================
        # LIMPAR REGISTRO DUCKDB
        # ==============================================================

        con.unregister(
            "dados_bronze"
        )


        if "dados_bronze_deduplicados" in [
            tabela[0]
            for tabela in con.sql(
                "SHOW TABLES"
            ).fetchall()
        ]:

            con.unregister(
                "dados_bronze_deduplicados"
            )


    except Exception as erro:

        print()

        print(
            f"  ✗ Erro ao processar {temporada}:"
        )

        print(
            f"    {type(erro).__name__}"
        )

        print(
            f"    {erro}"
        )

        temporadas_com_erro.append(
            temporada
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
    f"{len(temporadas_processadas)}"
)

print(
    f"Temporadas sem Bronze: "
    f"{len(temporadas_sem_bronze)}"
)


if temporadas_sem_bronze:

    print(
        "  "
        + ", ".join(
            str(ano)
            for ano in temporadas_sem_bronze
        )
    )


print(
    f"Temporadas com erro: "
    f"{len(temporadas_com_erro)}"
)


if temporadas_com_erro:

    print(
        "  "
        + ", ".join(
            str(ano)
            for ano in temporadas_com_erro
        )
    )


print(
    f"Registros removidos por duplicidade: "
    f"{total_duplicidades_removidas}"
)

print(
    "=" * 70
)

print(
    "✓ PRÉ-PROCESSAMENTO CONCLUÍDO!"
)

print(
    "=" * 70
)