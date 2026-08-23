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

# Bronze
BRONZE_BASE = "bronze/jolpica/resultados"

# Silver
SILVER_BASE = "silver/resultados"

# API de origem
API_BASE_URL = "https://api.jolpi.ca/ergast/f1"


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
# FUNÇÕES
# ======================================================================

def ler_json_minio(caminho):
    """
    Lê um arquivo JSON armazenado no MinIO.
    """

    response = s3.get_object(
        Bucket=BUCKET,
        Key=caminho
    )

    conteudo = response["Body"].read()

    return json.loads(
        conteudo.decode("utf-8")
    )


def salvar_parquet_minio(tabela_arrow, caminho):
    """
    Salva uma tabela PyArrow como Parquet no MinIO.
    """

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
print("PRÉ-PROCESSAMENTO - RESULTADOS")
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

# ================================================================
# 1. ESTRUTURAS JSON
# ================================================================

print("1. ESTRUTURAS JSON")
print("-" * 70)

print("Estruturas aninhadas disponibilizadas como campos individuais:")
print("  Driver      -> campos individuais")
print("  Constructor -> campos individuais")
print("  Circuit     -> campos individuais")
print("  FastestLap  -> campos individuais")

print()

# ================================================================
# 2. CONVERSÃO DE TIPOS
# ================================================================

print("2. CONVERSÃO DE TIPOS REALIZADA PELO DUCKDB")
print("-" * 70)

print("INTEGER:")
print("  season                       -> INTEGER")
print("  round                        -> INTEGER")
print("  driver_number                -> INTEGER")
print("  driver_permanent_number      -> INTEGER")
print("  position                     -> INTEGER")
print("  grid                         -> INTEGER")
print("  laps                         -> INTEGER")
print("  fastest_lap_rank             -> INTEGER")
print("  fastest_lap                  -> INTEGER")

print()

print("DOUBLE:")
print("  circuit_lat                  -> DOUBLE")
print("  circuit_long                 -> DOUBLE")
print("  points                       -> DOUBLE")
print("  fastest_lap_average_speed    -> DOUBLE")

print()

print("DATE:")
print("  race_date                    -> DATE")
print("  driver_date_of_birth         -> DATE")

print()

print("BIGINT:")
print("  race_time_millis             -> BIGINT")
print("  fastest_lap_time_millis      -> BIGINT")

print()

# ================================================================
# 3. TRATAMENTO DOS TEMPOS
# ================================================================

print("3. TRATAMENTO DOS TEMPOS")
print("-" * 70)

print("Tempo da corrida:")
print("  race_time                    -> VARCHAR / valor original")
print("  race_time_millis             -> BIGINT")

print()

print("Volta mais rápida:")
print("  fastest_lap_time              -> VARCHAR / valor original")
print("  fastest_lap_time_millis       -> BIGINT")

print()

print("Os valores originais de tempo são preservados.")
print("Também são criadas representações numéricas em milissegundos")
print("para permitir comparações e cálculos.")

print()

# ================================================================
# 4. PADRONIZAÇÃO TEXTUAL
# ================================================================

print("4. PADRONIZAÇÃO TEXTUAL")
print("-" * 70)

print("Aplicação de TRIM() nos campos textuais.")
print("Objetivo: remover espaços em branco nas extremidades.")

print()

# ================================================================
# 5. RASTREABILIDADE
# ================================================================

print("5. RASTREABILIDADE")
print("-" * 70)

print("source_url                   -> VARCHAR")
print("Tratamento                   -> TRIM()")
print("Conteúdo                     -> URL da API de origem")

print()

# ================================================================
# 6. QUALIDADE
# ================================================================

print("6. QUALIDADE")
print("-" * 70)

print("Chave utilizada para identificação de duplicidades:")
print("  season + round + driver_id")

print()

# ================================================================
# 7. SAÍDA
# ================================================================

print("7. SAÍDA")
print("-" * 70)

print("Formato                     -> Apache Parquet")
print("Destino                     -> MinIO / Silver")
print("Particionamento             -> season")

print()

# ======================================================================
# CONTROLE GERAL
# ======================================================================

temporadas_processadas = 0
temporadas_sem_bronze = []
temporadas_com_erro = []

total_registros_removidos = 0


# ======================================================================
# PROCESSAMENTO
# ======================================================================

for temporada in range(
    ANO_INICIAL,
    ANO_FINAL + 1
):

    print(f"[{temporada}] Processando...")

    # ------------------------------------------------------------------
    # CAMINHO BRONZE
    # ------------------------------------------------------------------

    caminho_bronze = (
        f"{BRONZE_BASE}/"
        f"{temporada}/"
        f"interlagos/"
        f"resultados.json"
    )

    # ------------------------------------------------------------------
    # CAMINHO SILVER
    # ------------------------------------------------------------------

    caminho_silver = (
        f"{SILVER_BASE}/"
        f"season={temporada}/"
        f"resultados.parquet"
    )

    # ------------------------------------------------------------------
    # URL DA API
    #
    # Para Interlagos:
    # /temporada/20/results/
    # ------------------------------------------------------------------

    source_url = (
        f"{API_BASE_URL}/"
        f"{temporada}/"
        f"20/"
        f"results/"
    )

    # ------------------------------------------------------------------
    # VERIFICAR EXISTÊNCIA DA BRONZE
    # ------------------------------------------------------------------

    try:

        s3.head_object(
            Bucket=BUCKET,
            Key=caminho_bronze
        )

    except Exception:

        print("  ⚠ Bronze não encontrada.")
        temporadas_sem_bronze.append(temporada)
        print()

        continue

    # ==================================================================
    # PROCESSAMENTO DA TEMPORADA
    # ==================================================================

    try:

        # --------------------------------------------------------------
        # LER JSON DA BRONZE
        # --------------------------------------------------------------

        dados = ler_json_minio(
            caminho_bronze
        )

        corrida = (
            dados
            ["MRData"]
            ["RaceTable"]
            ["Races"][0]
        )

        resultados = corrida.get(
            "Results",
            []
        )

        registros = []

        # --------------------------------------------------------------
        # ACHATAMENTO DO JSON
        # --------------------------------------------------------------

        for resultado in resultados:

            # ----------------------------------------------------------
            # DRIVER
            # ----------------------------------------------------------

            driver = resultado.get(
                "Driver",
                {}
            )

            # ----------------------------------------------------------
            # CONSTRUCTOR
            # ----------------------------------------------------------

            constructor = resultado.get(
                "Constructor",
                {}
            )

            # ----------------------------------------------------------
            # CIRCUIT
            # ----------------------------------------------------------

            circuito = corrida.get(
                "Circuit",
                {}
            )

            # ----------------------------------------------------------
            # FASTEST LAP
            # ----------------------------------------------------------

            fastest_lap = resultado.get(
                "FastestLap",
                {}
            )

            fastest_lap_time = (
                fastest_lap
                .get("Time", {})
                .get("time")
            )

            average_speed = (
                fastest_lap
                .get("AverageSpeed", {})
                .get("speed")
            )

            average_speed_unit = (
                fastest_lap
                .get("AverageSpeed", {})
                .get("units")
            )

            # ----------------------------------------------------------
            # TEMPO DA CORRIDA
            # ----------------------------------------------------------

            race_time = resultado.get(
                "Time",
                {}
            )

            race_time_value = race_time.get(
                "time"
            )

            race_time_millis = race_time.get(
                "millis"
            )

            # ----------------------------------------------------------
            # REGISTRO ACHATADO
            # ----------------------------------------------------------

            registros.append({

                # ======================================================
                # CORRIDA
                # ======================================================

                "season":
                    temporada,

                "round":
                    corrida.get("round"),

                "race_name":
                    corrida.get("raceName"),

                "race_date":
                    corrida.get("date"),

                "race_time":
                    race_time_value,

                "race_time_millis":
                    race_time_millis,

                # ======================================================
                # CIRCUITO
                # ======================================================

                "circuit_id":
                    circuito.get("circuitId"),

                "circuit_name":
                    circuito.get("circuitName"),

                "circuit_lat":
                    circuito.get("Location", {}).get("lat"),

                "circuit_long":
                    circuito.get("Location", {}).get("long"),

                "circuit_locality":
                    circuito.get("Location", {}).get("locality"),

                "circuit_country":
                    circuito.get("Location", {}).get("country"),

                # ======================================================
                # PILOTO
                # ======================================================

                "driver_id":
                    driver.get("driverId"),

                "driver_number":
                    resultado.get("number"),

                "driver_permanent_number":
                    driver.get("permanentNumber"),

                "driver_code":
                    driver.get("code"),

                "driver_given_name":
                    driver.get("givenName"),

                "driver_family_name":
                    driver.get("familyName"),

                "driver_date_of_birth":
                    driver.get("dateOfBirth"),

                "driver_nationality":
                    driver.get("nationality"),

                # ======================================================
                # CONSTRUTOR
                # ======================================================

                "constructor_id":
                    constructor.get("constructorId"),

                "constructor_name":
                    constructor.get("name"),

                "constructor_nationality":
                    constructor.get("nationality"),

                # ======================================================
                # RESULTADO
                # ======================================================

                "position":
                    resultado.get("position"),

                "position_text":
                    resultado.get("positionText"),

                "points":
                    resultado.get("points"),

                "grid":
                    resultado.get("grid"),

                "laps":
                    resultado.get("laps"),

                "status":
                    resultado.get("status"),

                # ======================================================
                # VOLTA MAIS RÁPIDA
                # ======================================================

                "fastest_lap_rank":
                    fastest_lap.get("rank"),

                "fastest_lap":
                    fastest_lap.get("lap"),

                "fastest_lap_time":
                    fastest_lap_time,

                "fastest_lap_average_speed":
                    average_speed,

                "fastest_lap_average_speed_unit":
                    average_speed_unit,

                # ======================================================
                # RASTREABILIDADE
                # ======================================================

                "source_url":
                    source_url
            })

        print(
            f"  Registros recebidos: {len(registros)}"
        )

        if not registros:

            print(
                "  ⚠ Nenhum resultado encontrado."
            )

            print()
            continue

        # ==============================================================
        # PYTHON -> PYARROW
        # ==============================================================

        tabela_bronze = pa.Table.from_pylist(
            registros
        )

        # ==============================================================
        # PYARROW -> DUCKDB
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
            -- IDENTIFICAÇÃO DA CORRIDA
            -- =========================================================

            CAST(season AS INTEGER)
                AS season,

            CAST(round AS INTEGER)
                AS round,

            TRIM(race_name)
                AS race_name,

            CAST(race_date AS DATE)
                AS race_date,

            -- Mantém o valor original da API
            TRIM(race_time)
                AS race_time,

            -- Valor original fornecido pela API
            CAST(
                race_time_millis
                AS BIGINT
            ) AS race_time_millis,


            -- =========================================================
            -- CIRCUITO
            -- =========================================================

            TRIM(circuit_id)
                AS circuit_id,

            TRIM(circuit_name)
                AS circuit_name,

            CAST(circuit_lat AS DOUBLE)
                AS circuit_lat,

            CAST(circuit_long AS DOUBLE)
                AS circuit_long,

            TRIM(circuit_locality)
                AS circuit_locality,

            TRIM(circuit_country)
                AS circuit_country,


            -- =========================================================
            -- PILOTO
            -- =========================================================

            TRIM(driver_id)
                AS driver_id,

            CAST(
                driver_number
                AS INTEGER
            ) AS driver_number,

            CAST(
                driver_permanent_number
                AS INTEGER
            ) AS driver_permanent_number,

            TRIM(driver_code)
                AS driver_code,

            TRIM(driver_given_name)
                AS driver_given_name,

            TRIM(driver_family_name)
                AS driver_family_name,

            CAST(
                driver_date_of_birth
                AS DATE
            ) AS driver_date_of_birth,

            TRIM(driver_nationality)
                AS driver_nationality,


            -- =========================================================
            -- CONSTRUTOR
            -- =========================================================

            TRIM(constructor_id)
                AS constructor_id,

            TRIM(constructor_name)
                AS constructor_name,

            TRIM(constructor_nationality)
                AS constructor_nationality,


            -- =========================================================
            -- RESULTADO
            -- =========================================================

            CAST(
                position
                AS INTEGER
            ) AS position,

            TRIM(position_text)
                AS position_text,

            CAST(
                points
                AS DOUBLE
            ) AS points,

            CAST(
                grid
                AS INTEGER
            ) AS grid,

            CAST(
                laps
                AS INTEGER
            ) AS laps,

            TRIM(status)
                AS status,


            -- =========================================================
            -- VOLTA MAIS RÁPIDA
            -- =========================================================

            CAST(
                fastest_lap_rank
                AS INTEGER
            ) AS fastest_lap_rank,

            CAST(
                fastest_lap
                AS INTEGER
            ) AS fastest_lap,

            -- Mantém:
            -- 1:25.639
            -- 1:26.524
            -- etc.
            TRIM(fastest_lap_time)
                AS fastest_lap_time,

            -- =========================================================
            -- CONVERSÃO DA VOLTA MAIS RÁPIDA
            --
            -- Exemplo:
            --
            -- 1:25.639
            --
            -- 1 minuto
            -- + 25.639 segundos
            --
            -- = 85.639 segundos
            -- = 85639 milissegundos
            -- =========================================================

            CASE

                WHEN
                    fastest_lap_time IS NOT NULL
                    AND TRIM(fastest_lap_time) <> ''
                    AND contains(
                        fastest_lap_time,
                        ':'
                    )

                THEN CAST(

                    ROUND(

                        (
                            CAST(
                                split_part(
                                    TRIM(fastest_lap_time),
                                    ':',
                                    1
                                ) AS DOUBLE
                            ) * 60

                            +

                            CAST(
                                split_part(
                                    TRIM(fastest_lap_time),
                                    ':',
                                    2
                                ) AS DOUBLE
                            )
                        ) * 1000

                    ) AS BIGINT

                )

                ELSE NULL

            END AS fastest_lap_time_millis,


            -- =========================================================
            -- VELOCIDADE MÉDIA DA VOLTA
            -- =========================================================

            CAST(
                fastest_lap_average_speed
                AS DOUBLE
            ) AS fastest_lap_average_speed,

            TRIM(
                fastest_lap_average_speed_unit
            ) AS fastest_lap_average_speed_unit,


            -- =========================================================
            -- RASTREABILIDADE
            -- =========================================================

            TRIM(source_url)
                AS source_url


        FROM dados_bronze

        """

        tabela_silver = (
            con.execute(query)
            .to_arrow_table()
        )

        # ==============================================================
        # REGISTRAR SILVER NO DUCKDB
        # ==============================================================

        con.register(
            "dados_silver",
            tabela_silver
        )

        # ==============================================================
        # VALIDAÇÃO DE DUPLICIDADES
        # ==============================================================

        resultado_qualidade = con.execute("""

            SELECT

                COUNT(*) AS registros_recebidos,

                COUNT(*) FILTER (
                    WHERE quantidade > 1
                ) AS grupos_duplicados,

                COALESCE(
                    SUM(
                        quantidade - 1
                    ) FILTER (
                        WHERE quantidade > 1
                    ),
                    0
                ) AS registros_duplicados

            FROM (

                SELECT

                    season,
                    round,
                    driver_id,

                    COUNT(*) AS quantidade

                FROM dados_silver

                GROUP BY

                    season,
                    round,
                    driver_id

            ) grupos

        """).fetchone()

        registros_recebidos = (
            resultado_qualidade[0]
        )

        grupos_duplicados = (
            resultado_qualidade[1]
        )

        registros_duplicados = (
            resultado_qualidade[2]
        )

        # ==============================================================
        # REMOÇÃO DE DUPLICIDADES
        # ==============================================================

        tabela_final = con.execute("""

            SELECT *

            EXCLUDE (rn)

            FROM (

                SELECT

                    *,

                    ROW_NUMBER() OVER (

                        PARTITION BY

                            season,
                            round,
                            driver_id

                        ORDER BY

                            driver_id

                    ) AS rn

                FROM dados_silver

            )

            WHERE rn = 1

        """).to_arrow_table()

        registros_finais = (
            tabela_final.num_rows
        )

        registros_removidos = (
            registros_recebidos
            - registros_finais
        )

        # ==============================================================
        # LOG DE QUALIDADE
        # ==============================================================

        print()
        print("  QUALIDADE E RESULTADO")

        print(
            f"  Registros recebidos:     "
            f"{registros_recebidos}"
        )

        print(
            f"  Grupos duplicados:       "
            f"{grupos_duplicados}"
        )

        print(
            f"  Registros duplicados:    "
            f"{registros_duplicados}"
        )

        print(
            f"  Registros removidos:     "
            f"{registros_removidos}"
        )

        print(
            f"  Registros finais:        "
            f"{registros_finais}"
        )

        # ==============================================================
        # VALIDAÇÃO DOS TEMPOS
        # ==============================================================

        verificacao_tempos = con.execute("""

            SELECT

                COUNT(*) FILTER (
                    WHERE race_time IS NOT NULL
                ) AS race_time_preenchido,

                COUNT(*) FILTER (
                    WHERE race_time_millis IS NOT NULL
                ) AS race_time_millis_preenchido,

                COUNT(*) FILTER (
                    WHERE fastest_lap_time IS NOT NULL
                ) AS fastest_lap_time_preenchido,

                COUNT(*) FILTER (
                    WHERE fastest_lap_time_millis IS NOT NULL
                ) AS fastest_lap_time_millis_preenchido

            FROM dados_silver

        """).fetchone()

        print()
        print("  VALIDAÇÃO DOS TEMPOS")

        print(
            f"  race_time: "
            f"{verificacao_tempos[0]} registros"
        )

        print(
            f"  race_time_millis: "
            f"{verificacao_tempos[1]} registros"
        )

        print(
            f"  fastest_lap_time: "
            f"{verificacao_tempos[2]} registros"
        )

        print(
            f"  fastest_lap_time_millis: "
            f"{verificacao_tempos[3]} registros"
        )

        # ==============================================================
        # EXEMPLO DE CONVERSÃO
        # ==============================================================

        exemplo_tempo = con.execute("""

            SELECT

                race_time,
                race_time_millis,
                fastest_lap_time,
                fastest_lap_time_millis

            FROM dados_silver

            WHERE

                fastest_lap_time IS NOT NULL
                AND fastest_lap_time_millis IS NOT NULL

            LIMIT 1

        """).fetchone()

        if exemplo_tempo:

            print()
            print("  EXEMPLO DE TEMPO")

            print(
                f"  race_time: "
                f"{exemplo_tempo[0]}"
            )

            print(
                f"  race_time_millis: "
                f"{exemplo_tempo[1]}"
            )

            print(
                f"  fastest_lap_time: "
                f"{exemplo_tempo[2]}"
            )

            print(
                f"  fastest_lap_time_millis: "
                f"{exemplo_tempo[3]}"
            )

        # ==============================================================
        # SALVAR PARQUET NA SILVER
        # ==============================================================

        salvar_parquet_minio(
            tabela_final,
            caminho_silver
        )

        print()
        print(
            f"  ✓ Silver gerada: "
            f"{caminho_silver}"
        )

        # ==============================================================
        # CONTROLE
        # ==============================================================

        temporadas_processadas += 1

        total_registros_removidos += (
            registros_removidos
        )

        # ==============================================================
        # LIMPEZA DAS TABELAS TEMPORÁRIAS
        # ==============================================================

        con.unregister(
            "dados_bronze"
        )

        con.unregister(
            "dados_silver"
        )

        print()

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

        print()

        temporadas_com_erro.append(
            temporada
        )

        # --------------------------------------------------------------
        # LIMPEZA EM CASO DE ERRO
        # --------------------------------------------------------------

        try:
            con.unregister(
                "dados_bronze"
            )
        except:
            pass

        try:
            con.unregister(
                "dados_silver"
            )
        except:
            pass


# ======================================================================
# RESUMO
# ======================================================================

print("=" * 70)
print("RESUMO DO PRÉ-PROCESSAMENTO")
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
    f"{total_registros_removidos}"
)

print("=" * 70)
print("✓ PRÉ-PROCESSAMENTO CONCLUÍDO!")
print("=" * 70)


# ======================================================================
# ENCERRAR DUCKDB
# ======================================================================

con.close()