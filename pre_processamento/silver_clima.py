import json
import unicodedata
from io import BytesIO

import boto3
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq


# ======================================================================
# CONFIGURAÇÕES
# ======================================================================

ANO_INICIAL = 2018
ANO_FINAL = 2025

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "minioadmin123"

BUCKET = "f1-data-lake"


EVENTOS_INTERLAGOS = {
    2018: "Brazilian Grand Prix",
    2019: "Brazilian Grand Prix",
}


def normalizar_texto(valor):
    """Normaliza texto para validações dos metadados Bronze."""
    if valor is None:
        return ""

    return " ".join(
        unicodedata.normalize("NFKD", str(valor))
        .encode("ascii", "ignore")
        .decode("ascii")
        .casefold()
        .split()
    )


def validar_metadados_interlagos(dados_json, temporada):
    """Impede que Bronze de outro evento seja promovida para a Silver."""
    nome_esperado = EVENTOS_INTERLAGOS.get(
        temporada,
        "São Paulo Grand Prix" if temporada >= 2021 else None
    )

    if nome_esperado is None:
        return False, "temporada sem GP de Interlagos no recorte atual"

    if dados_json.get("season") != temporada:
        return False, f"season Bronze inválida: {dados_json.get('season')!r}"

    if normalizar_texto(dados_json.get("event_name")) != normalizar_texto(nome_esperado):
        return False, f"event_name inválido: {dados_json.get('event_name')!r}"

    if normalizar_texto(dados_json.get("location")) != normalizar_texto("São Paulo"):
        return False, f"location/circuito inválido: {dados_json.get('location')!r}"

    if normalizar_texto(dados_json.get("circuit")) != normalizar_texto("Interlagos"):
        return False, f"circuit inválido: {dados_json.get('circuit')!r}"

    if not dados_json.get("event_date") or str(dados_json["event_date"])[:4] != str(temporada):
        return False, f"event_date inválida: {dados_json.get('event_date')!r}"

    return True, None


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
# CABEÇALHO
# ======================================================================

print()
print("=" * 70)
print("PRÉ-PROCESSAMENTO - CLIMA")
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


# ======================================================================
# TRATAMENTOS REALIZADOS
# ======================================================================

print("=" * 70)
print("TRATAMENTOS REALIZADOS")
print("=" * 70)

print()

print("1. ACHATAMENTO DO JSON")

print(
    "   Dados da sessão -> campos individuais"
)

print(
    "   Weather -> uma linha por medição"
)

print()

print("2. CONVERSÃO DE TIPOS REALIZADA PELO DUCKDB")

print(
    "   season                -> INTEGER"
)

print(
    "   event_date            -> DATE"
)

print(
    "   weather_time_seconds  -> DOUBLE"
)

print(
    "   weather_time_millis   -> BIGINT"
)

print(
    "   air_temp              -> DOUBLE"
)

print(
    "   humidity              -> DOUBLE"
)

print(
    "   pressure              -> DOUBLE"
)

print(
    "   rainfall              -> BOOLEAN"
)

print(
    "   track_temp            -> DOUBLE"
)

print(
    "   wind_direction        -> INTEGER"
)

print(
    "   wind_speed            -> DOUBLE"
)

print()

print("3. TRATAMENTO DO TEMPO")

print(
    "   Time -> segundos desde o início da sessão"
)

print(
    "   weather_time_millis -> milissegundos"
)

print()

print("4. PADRONIZAÇÃO TEXTUAL")

print(
    "   Campos VARCHAR -> TRIM()"
)

print()

print("5. QUALIDADE")

print(
    "   Chave lógica:"
)

print(
    "   season + session + weather_time_seconds"
)

print()


# ======================================================================
# CONTADORES
# ======================================================================

temporadas_processadas = 0
temporadas_sem_bronze = 0
temporadas_com_erro = 0

total_registros = 0
total_duplicidades = 0


# ======================================================================
# PROCESSAMENTO DAS TEMPORADAS
# ======================================================================

for temporada in range(
    ANO_INICIAL,
    ANO_FINAL + 1
):

    print(
        f"[{temporada}] Processando..."
    )

    try:

        # ==============================================================
        # CAMINHO BRONZE
        # ==============================================================

        bronze_key = (
            f"bronze/fastf1/clima/"
            f"{temporada}/interlagos/clima.json"
        )


        # ==============================================================
        # BUSCAR JSON NO MINIO
        # ==============================================================

        try:

            objeto = s3.get_object(
                Bucket=BUCKET,
                Key=bronze_key
            )

        except Exception:

            print(
                "  ⚠ Bronze não encontrada."
            )

            temporadas_sem_bronze += 1

            continue


        # ==============================================================
        # LER JSON
        # ==============================================================

        conteudo = objeto[
            "Body"
        ].read()

        dados_json = json.loads(
            conteudo.decode("utf-8")
        )


        # ==============================================================
        # VALIDAR IDENTIDADE DO EVENTO
        # ==============================================================

        evento_valido, motivo_evento_invalido = (
            validar_metadados_interlagos(
                dados_json,
                temporada
            )
        )

        if not evento_valido:

            raise ValueError(
                "Bronze rejeitada: não representa o GP de Interlagos. "
                f"season={temporada}; "
                f"event_name={dados_json.get('event_name')!r}; "
                f"location={dados_json.get('location')!r}; "
                f"circuit={dados_json.get('circuit')!r}; "
                f"event_date={dados_json.get('event_date')!r}; "
                f"motivo={motivo_evento_invalido}"
            )


        # ==============================================================
        # VALIDAR ESTRUTURA DO JSON
        # ==============================================================

        if "weather" not in dados_json:

            print(
                "  ⚠ Campo 'weather' não encontrado."
            )

            temporadas_com_erro += 1

            continue


        weather = dados_json[
            "weather"
        ]


        # ==============================================================
        # VALIDAR REGISTROS
        # ==============================================================

        if not isinstance(
            weather,
            list
        ):

            print(
                "  ⚠ Campo 'weather' não possui uma lista."
            )

            temporadas_com_erro += 1

            continue


        if len(weather) == 0:

            print(
                "  ⚠ Nenhum registro de clima encontrado."
            )

            temporadas_com_erro += 1

            continue


        print(
            f"  Registros recebidos: "
            f"{len(weather)}"
        )


        # ==============================================================
        # ACHATAMENTO DO JSON
        # ==============================================================
        #
        # Cada elemento de weather vira uma linha.
        #
        # Exemplo:
        #
        # {
        #     "Time": 18.37,
        #     "AirTemp": 23.9,
        #     ...
        # }
        #
        # será transformado em:
        #
        # season
        # grand_prix
        # circuit
        # session
        # ...
        # weather_time_seconds
        # air_temp
        # ...
        #
        # =============================================================

        dados_bronze = []


        for registro in weather:

            dados_bronze.append({

                # ------------------------------------------------------
                # IDENTIFICAÇÃO DA SESSÃO
                # ------------------------------------------------------

                "season":
                    dados_json.get(
                        "season"
                    ),

                "grand_prix":
                    dados_json.get(
                        "grand_prix"
                    ),

                "circuit":
                    dados_json.get(
                        "circuit"
                    ),

                "session":
                    dados_json.get(
                        "session"
                    ),

                "session_name":
                    dados_json.get(
                        "session_name"
                    ),

                "event_name":
                    dados_json.get(
                        "event_name"
                    ),

                "location":
                    dados_json.get(
                        "location"
                    ),

                "event_date":
                    dados_json.get(
                        "event_date"
                    ),


                # ------------------------------------------------------
                # WEATHER
                # ------------------------------------------------------

                "weather_time_seconds":
                    registro.get(
                        "Time"
                    ),

                "air_temp":
                    registro.get(
                        "AirTemp"
                    ),

                "humidity":
                    registro.get(
                        "Humidity"
                    ),

                "pressure":
                    registro.get(
                        "Pressure"
                    ),

                "rainfall":
                    registro.get(
                        "Rainfall"
                    ),

                "track_temp":
                    registro.get(
                        "TrackTemp"
                    ),

                "wind_direction":
                    registro.get(
                        "WindDirection"
                    ),

                "wind_speed":
                    registro.get(
                        "WindSpeed"
                    )

            })


        # ==============================================================
        # CONVERTER LISTA PYTHON PARA PYARROW
        # ==============================================================
        #
        # IMPORTANTE:
        #
        # DuckDB não consegue utilizar diretamente:
        #
        #     dados_bronze = []
        #
        # como uma tabela.
        #
        # Por isso transformamos explicitamente a lista
        # em uma PyArrow Table.
        #
        # =============================================================

        tabela_bronze = pa.Table.from_pylist(
            dados_bronze
        )


        # ==============================================================
        # REGISTRAR PYARROW NO DUCKDB
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
            -- IDENTIFICAÇÃO DA SESSÃO
            -- =========================================================

            CAST(
                season
                AS INTEGER
            ) AS season,

            TRIM(
                grand_prix
            ) AS grand_prix,

            TRIM(
                circuit
            ) AS circuit,

            TRIM(
                session
            ) AS session,

            TRIM(
                session_name
            ) AS session_name,

            TRIM(
                event_name
            ) AS event_name,

            TRIM(
                location
            ) AS location,

            CAST(
                event_date
                AS DATE
            ) AS event_date,


            -- =========================================================
            -- TEMPO DA MEDIÇÃO
            --
            -- Time representa segundos decorridos desde o início
            -- da sessão.
            -- =========================================================

            CAST(
                weather_time_seconds
                AS DOUBLE
            ) AS weather_time_seconds,


            -- =========================================================
            -- TEMPO EM MILISSEGUNDOS
            -- =========================================================

            CASE

                WHEN
                    weather_time_seconds IS NULL

                THEN NULL

                ELSE CAST(

                    ROUND(
                        weather_time_seconds * 1000
                    )

                    AS BIGINT

                )

            END AS weather_time_millis,


            -- =========================================================
            -- TEMPERATURA DO AR
            -- =========================================================

            CAST(
                air_temp
                AS DOUBLE
            ) AS air_temp,


            -- =========================================================
            -- UMIDADE
            -- =========================================================

            CAST(
                humidity
                AS DOUBLE
            ) AS humidity,


            -- =========================================================
            -- PRESSÃO ATMOSFÉRICA
            -- =========================================================

            CAST(
                pressure
                AS DOUBLE
            ) AS pressure,


            -- =========================================================
            -- CHUVA
            -- =========================================================

            CAST(
                rainfall
                AS BOOLEAN
            ) AS rainfall,


            -- =========================================================
            -- TEMPERATURA DA PISTA
            -- =========================================================

            CAST(
                track_temp
                AS DOUBLE
            ) AS track_temp,


            -- =========================================================
            -- DIREÇÃO DO VENTO
            -- =========================================================

            CAST(
                wind_direction
                AS INTEGER
            ) AS wind_direction,


            -- =========================================================
            -- VELOCIDADE DO VENTO
            -- =========================================================

            CAST(
                wind_speed
                AS DOUBLE
            ) AS wind_speed


        FROM dados_bronze

        """


        # ==============================================================
        # EXECUTAR TRANSFORMAÇÃO
        # ==============================================================

        resultado = con.execute(
            query
        ).fetch_arrow_table()


        # ==============================================================
        # CONTAGEM DE REGISTROS
        # ==============================================================

        quantidade = resultado.num_rows

        print(
            f"  Registros após tratamento: "
            f"{quantidade}"
        )


        # ==============================================================
        # REGISTRAR RESULTADO NO DUCKDB
        # ==============================================================
        #
        # Usamos outro nome para evitar conflito com dados_bronze.
        #
        # =============================================================

        con.register(
            "dados_silver",
            resultado
        )


        # ==============================================================
        # VERIFICAR DUPLICIDADES
        # ==============================================================
        #
        # Não utilizamos:
        #
        # COUNT(season, session, weather_time_seconds)
        #
        # porque o DuckDB interpreta COUNT() como uma função
        # de um único argumento.
        #
        # Aqui fazemos:
        #
        # COUNT(*)
        #
        # depois GROUP BY nas colunas da chave.
        #
        # =============================================================

        duplicidades = con.execute(
            """

            SELECT
                COUNT(*) AS quantidade_duplicidades

            FROM (

                SELECT

                    season,
                    session,
                    weather_time_seconds

                FROM dados_silver

                GROUP BY

                    season,
                    session,
                    weather_time_seconds

                HAVING COUNT(*) > 1

            ) AS duplicados

            """
        ).fetchone()[0]


        print(
            f"  Grupos duplicados encontrados: "
            f"{duplicidades}"
        )


        # ==============================================================
        # SALVAR PARQUET NA SILVER
        # ==============================================================

        silver_key = (
            f"silver/clima/"
            f"season={temporada}/"
            f"clima.parquet"
        )


        # ==============================================================
        # SERIALIZAR PARQUET
        # ==============================================================

        buffer = BytesIO()


        pq.write_table(
            resultado,
            buffer,
            compression="snappy"
        )


        buffer.seek(0)


        # ==============================================================
        # ENVIAR PARA MINIO
        # ==============================================================

        s3.put_object(
            Bucket=BUCKET,
            Key=silver_key,
            Body=buffer.getvalue(),
            ContentType="application/octet-stream"
        )


        # ==============================================================
        # RESULTADO DA TEMPORADA
        # ==============================================================

        print(
            "  ✓ Silver salva:"
        )

        print(
            f"    {silver_key}"
        )


        temporadas_processadas += 1

        total_registros += quantidade

        total_duplicidades += duplicidades


        # ==============================================================
        # REMOVER REGISTROS TEMPORÁRIOS DO DUCKDB
        # ==============================================================

        con.unregister(
            "dados_bronze"
        )

        con.unregister(
            "dados_silver"
        )


    # ==================================================================
    # TRATAMENTO DE ERRO
    # ==================================================================

    except Exception as erro:

        temporadas_com_erro += 1

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


        # ==============================================================
        # LIMPAR REGISTROS DO DUCKDB CASO EXISTAM
        # ==============================================================

        try:

            con.unregister(
                "dados_bronze"
            )

        except Exception:

            pass


        try:

            con.unregister(
                "dados_silver"
            )

        except Exception:

            pass


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
    f"{temporadas_sem_bronze}"
)

print(
    f"Temporadas com erro: "
    f"{temporadas_com_erro}"
)

print(
    f"Total de registros Silver: "
    f"{total_registros}"
)

print(
    f"Grupos duplicados encontrados: "
    f"{total_duplicidades}"
)

print("=" * 70)

print(
    "✓ PRÉ-PROCESSAMENTO CONCLUÍDO!"
)

print("=" * 70)


# ======================================================================
# FECHAR DUCKDB
# ======================================================================

con.close()
