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
# BRONZE
# ======================================================================

BRONZE_BASE = "bronze/jolpica/pit_stops"


# ======================================================================
# SILVER
# ======================================================================

SILVER_BASE = "silver/pit_stops"


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
# CONTROLES
# ======================================================================

temporadas_processadas = 0
temporadas_sem_bronze = []
temporadas_com_erro = []

total_registros_removidos = 0


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


def encontrar_bronze_temporada(temporada):
    """
    Procura o arquivo pit_stops.json da temporada.

    Como o round varia entre temporadas, o código consulta os objetos
    existentes dentro de:

        bronze/jolpica/pit_stops/{temporada}/

    e localiza o primeiro arquivo:

        round_X/pit_stops.json
    """

    prefixo = (
        f"{BRONZE_BASE}/"
        f"{temporada}/"
    )

    resposta = s3.list_objects_v2(
        Bucket=BUCKET,
        Prefix=prefixo
    )

    objetos = resposta.get(
        "Contents",
        []
    )

    arquivos = [
        objeto["Key"]
        for objeto in objetos
        if objeto["Key"].endswith(
            "/pit_stops.json"
        )
    ]

    if not arquivos:
        return None

    return arquivos[0]


# ======================================================================
# CABEÇALHO
# ======================================================================

print()

print("=" * 70)
print("PRÉ-PROCESSAMENTO - PIT STOPS")
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


# ======================================================================
# 1. ESTRUTURAS JSON
# ======================================================================

print("1. ESTRUTURAS JSON")
print("-" * 70)

print(
    "Estruturas aninhadas disponibilizadas como campos individuais:"
)

print("  Race              -> campos individuais")
print("  Circuit           -> campos individuais")
print("  Location          -> campos individuais")
print("  PitStops          -> uma linha por pit stop")

print()


# ======================================================================
# 2. CONVERSÃO DE TIPOS
# ======================================================================

print("2. CONVERSÃO DE TIPOS REALIZADA PELO DUCKDB")
print("-" * 70)

print("INTEGER:")

print("  season                       -> INTEGER")
print("  round                        -> INTEGER")
print("  lap                          -> INTEGER")
print("  stop                         -> INTEGER")

print()

print("DOUBLE:")

print("  circuit_lat                  -> DOUBLE")
print("  circuit_long                 -> DOUBLE")
print("  duration                     -> DOUBLE")

print()

print("DATE:")

print("  race_date                    -> DATE")

print()

print("TIME:")

print("  race_time                    -> TIME")
print("  pit_stop_time                -> TIME")

print()

print("BIGINT:")

print("  race_time_millis             -> BIGINT")
print("  duration_millis              -> BIGINT")

print()


# ======================================================================
# 3. TRATAMENTO DOS TEMPOS
# ======================================================================

print("3. TRATAMENTO DOS TEMPOS")
print("-" * 70)

print("  race_time                    -> TIME")
print("  race_time_millis             -> milissegundos desde 00:00:00")
print("  pit_stop_time                -> TIME")
print("  duration                     -> segundos")
print("  duration_millis              -> milissegundos")

print()


# ======================================================================
# 4. PADRONIZAÇÃO TEXTUAL
# ======================================================================

print("4. PADRONIZAÇÃO TEXTUAL")
print("-" * 70)

print("  Campos VARCHAR -> TRIM()")

print()


# ======================================================================
# 5. RASTREABILIDADE
# ======================================================================

print("5. RASTREABILIDADE")
print("-" * 70)

print("  race_url          -> URL da corrida")
print("  circuit_url       -> URL do circuito")

print()


# ======================================================================
# 6. QUALIDADE
# ======================================================================

print("6. QUALIDADE")
print("-" * 70)

print("  Chave de duplicidade:")
print("  season + round + driver_id + stop")

print()


# ======================================================================
# PROCESSAMENTO
# ======================================================================

for temporada in range(
    ANO_INICIAL,
    ANO_FINAL + 1
):

    print(
        f"[{temporada}] Processando..."
    )

    # ------------------------------------------------------------------
    # LOCALIZAR BRONZE
    # ------------------------------------------------------------------

    caminho_bronze = encontrar_bronze_temporada(
        temporada
    )

    if caminho_bronze is None:

        print(
            "  ⚠ Bronze não encontrada."
        )

        temporadas_sem_bronze.append(
            temporada
        )

        print()

        continue

    # ------------------------------------------------------------------
    # LER JSON
    # ------------------------------------------------------------------

    try:

        dados = ler_json_minio(
            caminho_bronze
        )

        # --------------------------------------------------------------
        # EXTRAIR RACE
        # --------------------------------------------------------------

        races = (
            dados
            .get("MRData", {})
            .get("RaceTable", {})
            .get("Races", [])
        )

        if not races:

            print(
                "  ⚠ Nenhuma corrida encontrada."
            )

            temporadas_com_erro.append(
                temporada
            )

            print()

            continue

        corrida = races[0]

        # --------------------------------------------------------------
        # EXTRAIR PIT STOPS
        # --------------------------------------------------------------

        pit_stops = corrida.get(
            "PitStops",
            []
        )

        registros = []

        # --------------------------------------------------------------
        # CIRCUITO
        # --------------------------------------------------------------

        circuito = corrida.get(
            "Circuit",
            {}
        )

        # --------------------------------------------------------------
        # LOCATION
        # --------------------------------------------------------------

        location = circuito.get(
            "Location",
            {}
        )

        # --------------------------------------------------------------
        # TEMPO DA CORRIDA
        # --------------------------------------------------------------

        race_time = corrida.get(
            "time"
        )

        # --------------------------------------------------------------
        # MILISSEGUNDOS DO TEMPO DA CORRIDA
        #
        # A API fornece o horário no formato:
        #
        # 14:00:00Z
        #
        # Para análise, mantemos:
        #
        # race_time
        #
        # e também calculamos:
        #
        # race_time_millis
        #
        # como milissegundos desde 00:00:00.
        # --------------------------------------------------------------

        race_time_millis = None

        if race_time:

            try:

                tempo_sem_timezone = (
                    race_time
                    .replace("Z", "")
                )

                partes = tempo_sem_timezone.split(
                    ":"
                )

                horas = int(
                    partes[0]
                )

                minutos = int(
                    partes[1]
                )

                segundos = float(
                    partes[2]
                )

                race_time_millis = int(
                    round(
                        (
                            horas * 3600
                            + minutos * 60
                            + segundos
                        ) * 1000
                    )
                )

            except Exception:

                race_time_millis = None

        # --------------------------------------------------------------
        # ACHATAMENTO DOS PIT STOPS
        # --------------------------------------------------------------

        for pit_stop in pit_stops:

            registros.append({

                # ======================================================
                # CORRIDA
                # ======================================================

                "season":
                    temporada,

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
                    race_time,

                "race_time_millis":
                    race_time_millis,

                "race_url":
                    corrida.get(
                        "url"
                    ),

                # ======================================================
                # CIRCUITO
                # ======================================================

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

                # ======================================================
                # PIT STOP
                # ======================================================

                "driver_id":
                    pit_stop.get(
                        "driverId"
                    ),

                "lap":
                    pit_stop.get(
                        "lap"
                    ),

                "stop":
                    pit_stop.get(
                        "stop"
                    ),

                "pit_stop_time":
                    pit_stop.get(
                        "time"
                    ),

                "duration":
                    pit_stop.get(
                        "duration"
                    )

            })

        print(
            f"  Registros recebidos: "
            f"{len(registros)}"
        )

        if not registros:

            print(
                "  ⚠ Nenhum pit stop encontrado."
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

            CAST(
                race_time
                AS TIME
            ) AS race_time,

            CAST(
                race_time_millis
                AS BIGINT
            ) AS race_time_millis,

            TRIM(
                race_url
            ) AS race_url,


            -- =========================================================
            -- CIRCUITO
            -- =========================================================

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
            -- PIT STOP
            -- =========================================================

            TRIM(
                driver_id
            ) AS driver_id,

            CAST(
                lap
                AS INTEGER
            ) AS lap,

            CAST(
                stop
                AS INTEGER
            ) AS stop,

            CAST(
                pit_stop_time
                AS TIME
            ) AS pit_stop_time,


            -- =========================================================
            -- DURAÇÃO
            --
            -- Exemplo:
            --
            -- 23.937
            --
            -- significa:
            --
            -- 23.937 segundos
            --
            -- Portanto:
            --
            -- duration       = 23.937
            -- duration_millis = 23937
            --
            -- =========================================================

            CASE

                WHEN
                    duration IS NULL
                    OR TRIM(duration) = ''

                THEN NULL

                WHEN
                    contains(
                        TRIM(duration),
                        ':'
                    )

                THEN

                    (
                        CAST(
                            split_part(
                                TRIM(duration),
                                ':',
                                1
                            ) AS DOUBLE
                        ) * 60

                        +

                        CAST(
                            split_part(
                                TRIM(duration),
                                ':',
                                2
                            ) AS DOUBLE
                        )
                    )

                ELSE

                    CAST(
                        TRIM(duration)
                        AS DOUBLE
                    )

            END AS duration,


            -- =========================================================
            -- DURAÇÃO EM MILISSEGUNDOS
            -- =========================================================

            CASE

                WHEN
                    duration IS NULL
                    OR TRIM(duration) = ''

                THEN NULL

                WHEN
                    contains(
                        TRIM(duration),
                        ':'
                    )

                THEN CAST(

                    ROUND(

                        (

                            CAST(
                                split_part(
                                    TRIM(duration),
                                    ':',
                                    1
                                ) AS DOUBLE
                            ) * 60

                            +

                            CAST(
                                split_part(
                                    TRIM(duration),
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
                            TRIM(duration)
                            AS DOUBLE
                        ) * 1000

                    ) AS BIGINT

                )

            END AS duration_millis

        FROM dados_bronze

        """

        tabela_silver = (
            con.execute(
                query
            )
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

        print(
            "  Verificando duplicidades..."
        )

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

                    stop,

                    COUNT(*) AS quantidade

                FROM dados_silver

                GROUP BY

                    season,

                    round,

                    driver_id,

                    stop

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

                            driver_id,

                            stop

                        ORDER BY

                            driver_id,

                            stop

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

        print(
            "  QUALIDADE E RESULTADO"
        )

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
                    WHERE pit_stop_time IS NOT NULL
                ) AS pit_stop_time_preenchido,

                COUNT(*) FILTER (
                    WHERE duration IS NOT NULL
                ) AS duration_preenchido,

                COUNT(*) FILTER (
                    WHERE duration_millis IS NOT NULL
                ) AS duration_millis_preenchido

            FROM dados_silver

        """).fetchone()

        print()

        print(
            "  VALIDAÇÃO DOS TEMPOS"
        )

        print(
            f"  race_time: "
            f"{verificacao_tempos[0]} registros"
        )

        print(
            f"  race_time_millis: "
            f"{verificacao_tempos[1]} registros"
        )

        print(
            f"  pit_stop_time: "
            f"{verificacao_tempos[2]} registros"
        )

        print(
            f"  duration: "
            f"{verificacao_tempos[3]} registros"
        )

        print(
            f"  duration_millis: "
            f"{verificacao_tempos[4]} registros"
        )

        # ==============================================================
        # EXEMPLO DE TEMPO
        # ==============================================================

        exemplo_tempo = con.execute("""

            SELECT

                race_time,

                race_time_millis,

                pit_stop_time,

                duration,

                duration_millis

            FROM dados_silver

            WHERE

                duration IS NOT NULL

                AND duration_millis IS NOT NULL

            LIMIT 1

        """).fetchone()

        if exemplo_tempo:

            print()

            print(
                "  EXEMPLO DE TEMPO"
            )

            print(
                f"  race_time: "
                f"{exemplo_tempo[0]}"
            )

            print(
                f"  race_time_millis: "
                f"{exemplo_tempo[1]}"
            )

            print(
                f"  pit_stop_time: "
                f"{exemplo_tempo[2]}"
            )

            print(
                f"  duration: "
                f"{exemplo_tempo[3]}"
            )

            print(
                f"  duration_millis: "
                f"{exemplo_tempo[4]}"
            )

        # ==============================================================
        # CAMINHO SILVER
        # ==============================================================
        #
        # Partitionamento por temporada:
        #
        # silver/pit_stops/
        # └── season=2015/
        #     └── pit_stops.parquet
        #
        # ==============================================================

        caminho_silver = (
            f"{SILVER_BASE}/"
            f"season={temporada}/"
            f"pit_stops.parquet"
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
        # LIMPEZA
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