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
print("PRÉ-PROCESSAMENTO - PNEUS")
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
print("   Dados da sessão -> campos individuais")
print("   Laps            -> uma linha por piloto por volta")

print()

print("2. CONVERSÃO DE TIPOS REALIZADA PELO DUCKDB")
print("   season          -> INTEGER")
print("   event_date      -> DATE")
print("   driver_number   -> INTEGER")
print("   lap_number      -> INTEGER")
print("   stint           -> INTEGER")
print("   tyre_life       -> INTEGER")
print("   fresh_tyre      -> BOOLEAN")

print()

print("3. PADRONIZAÇÃO TEXTUAL")
print("   Campos VARCHAR  -> TRIM()")

print()

print("4. ESTRUTURA DOS PNEUS")
print("   Uma linha       -> um piloto em uma volta")
print("   compound        -> composto utilizado")
print("   tyre_life       -> idade do pneu em voltas")
print("   fresh_tyre      -> indica se o pneu era novo")

print()

print("5. QUALIDADE")
print("   Chave lógica:")
print("   season + session + driver_id + lap_number")

print()


# ======================================================================
# CONTADORES
# ======================================================================

temporadas_processadas = 0
temporadas_sem_bronze = 0
temporadas_com_erro = 0

total_registros_silver = 0
total_duplicidades_removidas = 0

lista_sem_bronze = []


# ======================================================================
# PROCESSAMENTO POR TEMPORADA
# ======================================================================

for temporada in range(
    ANO_INICIAL,
    ANO_FINAL + 1
):

    print(f"[{temporada}] Processando...")

    # ==================================================================
    # CAMINHOS
    # ==================================================================

    caminho_bronze = (
        f"bronze/fastf1/pneus/"
        f"{temporada}/interlagos/pneus.json"
    )

    caminho_silver = (
        f"silver/pneus/"
        f"season={temporada}/"
        f"interlagos/pneus.parquet"
    )

    try:

        # ==============================================================
        # VERIFICAR BRONZE
        # ==============================================================

        try:

            objeto = s3.get_object(
                Bucket=BUCKET,
                Key=caminho_bronze
            )

        except Exception:

            print("  ⚠ Bronze não encontrada.")

            temporadas_sem_bronze += 1

            lista_sem_bronze.append(
                temporada
            )

            continue


        # ==============================================================
        # LER JSON
        # ==============================================================

        conteudo = objeto["Body"].read()

        dados_json = json.loads(
            conteudo.decode("utf-8")
        )


        # ==============================================================
        # VALIDAR ESTRUTURA
        # ==============================================================

        if not isinstance(
            dados_json,
            dict
        ):

            raise ValueError(
                "JSON de pneus não possui "
                "estrutura de objeto esperada."
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
        # DADOS DA SESSÃO
        # ==============================================================

        season = dados_json.get(
            "season"
        )

        grand_prix = dados_json.get(
            "grand_prix"
        )

        circuit = dados_json.get(
            "circuit"
        )

        session = dados_json.get(
            "session"
        )

        session_name = dados_json.get(
            "session_name"
        )

        event_name = dados_json.get(
            "event_name"
        )

        location = dados_json.get(
            "location"
        )

        event_date = dados_json.get(
            "event_date"
        )

        laps = dados_json.get(
            "laps",
            []
        )


        # ==============================================================
        # VALIDAR LAPS
        # ==============================================================

        if not isinstance(
            laps,
            list
        ):

            raise ValueError(
                "Campo 'laps' não é uma lista."
            )


        print(
            f"  Registros recebidos: "
            f"{len(laps)}"
        )


        if len(laps) == 0:

            print(
                "  ⚠ Nenhum registro de volta."
            )

            continue


        # ==============================================================
        # ACHATAMENTO DO JSON
        # ==============================================================

        registros = []


        for lap in laps:

            if not isinstance(
                lap,
                dict
            ):
                continue


            registros.append({

                "season": season,

                "grand_prix": grand_prix,

                "circuit": circuit,

                "session": session,

                "session_name": session_name,

                "event_name": event_name,

                "location": location,

                "event_date": event_date,

                "driver_id": lap.get(
                    "Driver"
                ),

                "driver_number": lap.get(
                    "DriverNumber"
                ),

                "lap_number": lap.get(
                    "LapNumber"
                ),

                "stint": lap.get(
                    "Stint"
                ),

                "compound": lap.get(
                    "Compound"
                ),

                "tyre_life": lap.get(
                    "TyreLife"
                ),

                "fresh_tyre": lap.get(
                    "FreshTyre"
                )

            })


        # ==============================================================
        # LISTA PYTHON -> PYARROW
        #
        # DuckDB não aceita diretamente:
        #
        # list[dict]
        #
        # Portanto transformamos primeiro em Arrow Table.
        # ==============================================================

        tabela_bronze = pa.Table.from_pylist(
            registros
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

            -- ======================================================
            -- IDENTIFICAÇÃO DA SESSÃO
            -- ======================================================

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


            -- ======================================================
            -- PILOTO
            -- ======================================================

            TRIM(
                driver_id
            ) AS driver_id,

            CAST(
                driver_number
                AS INTEGER
            ) AS driver_number,


            -- ======================================================
            -- VOLTA
            -- ======================================================

            CAST(
                lap_number
                AS INTEGER
            ) AS lap_number,

            CAST(
                stint
                AS INTEGER
            ) AS stint,


            -- ======================================================
            -- PNEU
            -- ======================================================

            TRIM(
                compound
            ) AS compound,

            CAST(
                tyre_life
                AS INTEGER
            ) AS tyre_life,

            CAST(
                fresh_tyre
                AS BOOLEAN
            ) AS fresh_tyre


        FROM dados_bronze

        WHERE
            lap_number IS NOT NULL

        """


        # ==============================================================
        # EXECUTAR TRANSFORMAÇÃO
        # ==============================================================

        resultado = con.execute(
            query
        ).fetch_arrow_table()


        # ==============================================================
        # REGISTRAR SILVER NO DUCKDB
        # ==============================================================

        con.register(
            "dados_silver",
            resultado
        )


        # ==============================================================
        # VERIFICAR DUPLICIDADES
        # ==============================================================

        query_duplicidades = """

        SELECT
            COUNT(*) AS total_duplicidades

        FROM (

            SELECT
                season,
                session,
                driver_id,
                lap_number

            FROM dados_silver

            GROUP BY
                season,
                session,
                driver_id,
                lap_number

            HAVING COUNT(*) > 1

        )

        """

        duplicidades = con.execute(
            query_duplicidades
        ).fetchone()[0]


        print(
            "  Verificando duplicidades..."
        )


        # ==============================================================
        # REMOVER DUPLICIDADES
        # ==============================================================

        if duplicidades > 0:

            query_deduplicacao = """

            SELECT DISTINCT *

            FROM dados_silver

            """

            resultado = con.execute(
                query_deduplicacao
            ).fetch_arrow_table()

            total_duplicidades_removidas += (
                duplicidades
            )


        # ==============================================================
        # ESCREVER PARQUET
        # ==============================================================

        buffer = BytesIO()

        pq.write_table(
            resultado,
            buffer,
            compression="snappy"
        )

        buffer.seek(0)


        # ==============================================================
        # SALVAR NA SILVER
        # ==============================================================

        s3.put_object(

            Bucket=BUCKET,

            Key=caminho_silver,

            Body=buffer.getvalue(),

            ContentType="application/octet-stream"

        )


        # ==============================================================
        # CONTADORES
        # ==============================================================

        quantidade_registros = (
            resultado.num_rows
        )

        total_registros_silver += (
            quantidade_registros
        )

        temporadas_processadas += 1


        # ==============================================================
        # RESULTADO
        # ==============================================================

        print(
            "  ✓ Silver gerada."
        )

        print(
            f"  Registros Silver: "
            f"{quantidade_registros}"
        )

        print(
            f"  Arquivo: "
            f"{caminho_silver}"
        )

        print()


        # ==============================================================
        # LIMPAR REGISTROS DO DUCKDB
        # ==============================================================

        con.unregister(
            "dados_bronze"
        )

        con.unregister(
            "dados_silver"
        )


    # ==================================================================
    # ERRO
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
        # LIMPAR RELAÇÕES
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

if lista_sem_bronze:

    print(
        "  "
        + ", ".join(
            map(
                str,
                lista_sem_bronze
            )
        )
    )

print(
    f"Temporadas com erro: "
    f"{temporadas_com_erro}"
)

print(
    f"Total de registros Silver: "
    f"{total_registros_silver}"
)

print(
    f"Registros removidos por duplicidade: "
    f"{total_duplicidades_removidas}"
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
