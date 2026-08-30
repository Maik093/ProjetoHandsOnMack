import argparse

import duckdb


# ============================================================
# CONFIGURAÇÃO DO MINIO
# ============================================================

MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "minioadmin123"

BUCKET = "f1-data-lake"

PASTA_ENTRADA = "silver"
PASTA_SAIDA = "silver/consolidado"


# ============================================================
# BASES QUE SERÃO CONSOLIDADAS
# ============================================================

BASES = [
    "clima",
    "pneus",
    "resultados",
    "voltas",
    "pit_stops",
    "calendario",
]


# ============================================================
# ARGUMENTOS DE EXECUÇÃO
# ============================================================

parser = argparse.ArgumentParser(
    description="Consolida datasets da camada Silver."
)

parser.add_argument(
    "--dataset",
    choices=BASES,
    help=(
        "Dataset Silver a consolidar. "
        "Sem este parâmetro, mantém o comportamento atual "
        "e consolida todas as bases."
    )
)

argumentos = parser.parse_args()


if argumentos.dataset:

    bases_para_consolidar = [
        argumentos.dataset
    ]

else:

    bases_para_consolidar = BASES


# ============================================================
# CONEXÃO DUCKDB
# ============================================================

con = duckdb.connect()

con.execute("INSTALL httpfs;")
con.execute("LOAD httpfs;")

con.execute(f"""
    SET s3_endpoint='{MINIO_ENDPOINT}';
    SET s3_access_key_id='{MINIO_ACCESS_KEY}';
    SET s3_secret_access_key='{MINIO_SECRET_KEY}';
    SET s3_use_ssl=false;
    SET s3_url_style='path';
""")


# ============================================================
# VALIDAÇÕES DE PIT STOPS
# ============================================================

def validar_pit_stops(
    caminho
):

    quantidade = con.execute(f"""
        SELECT COUNT(*)
        FROM read_parquet(
            '{caminho}',
            hive_partitioning=true,
            union_by_name=true
        )
    """).fetchone()[0]

    grupos_duplicados = con.execute(f"""
        SELECT COUNT(*)
        FROM (
            SELECT
                season,
                round,
                driver_id,
                stop,
                COUNT(*) AS quantidade
            FROM read_parquet(
                '{caminho}',
                hive_partitioning=true,
                union_by_name=true
            )
            GROUP BY
                season,
                round,
                driver_id,
                stop
            HAVING COUNT(*) > 1
        )
    """).fetchone()[0]

    return quantidade, grupos_duplicados


# ============================================================
# CONSOLIDAÇÃO
# ============================================================

for base in bases_para_consolidar:

    origem = f"s3://{BUCKET}/{PASTA_ENTRADA}/{base}/**/*.parquet"

    destino = f"s3://{BUCKET}/{PASTA_SAIDA}/{base}.parquet"

    print("=" * 60)
    print(f"Consolidando: {base}")
    print(f"Origem:  {origem}")
    print(f"Destino: {destino}")

    try:

        quantidade_origem = None

        if base == "pit_stops":

            (
                quantidade_origem,
                grupos_duplicados_origem
            ) = validar_pit_stops(
                origem
            )

            print(
                f"Registros na origem: "
                f"{quantidade_origem:,}"
            )

            print(
                f"Grupos duplicados na origem: "
                f"{grupos_duplicados_origem:,}"
            )

            if grupos_duplicados_origem > 0:

                raise ValueError(
                    "Foram encontrados grupos duplicados "
                    "em pit_stops pela chave "
                    "season + round + driver_id + stop."
                )

        con.execute(f"""
            COPY (
                SELECT *
                FROM read_parquet(
                    '{origem}',
                    hive_partitioning=true,
                    union_by_name=true
                )
            )
            TO '{destino}'
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            );
        """)

        quantidade_destino = con.execute(f"""
            SELECT COUNT(*)
            FROM read_parquet('{destino}')
        """).fetchone()[0]

        if base == "pit_stops":

            (
                quantidade_validada,
                grupos_duplicados_destino
            ) = validar_pit_stops(
                destino
            )

            if quantidade_destino != quantidade_origem:

                raise ValueError(
                    "Divergência na consolidação de pit_stops: "
                    f"origem={quantidade_origem:,}, "
                    f"destino={quantidade_destino:,}."
                )

            if quantidade_validada != quantidade_destino:

                raise ValueError(
                    "Divergência na validação final de pit_stops: "
                    f"leitura final={quantidade_validada:,}, "
                    f"destino={quantidade_destino:,}."
                )

            if grupos_duplicados_destino > 0:

                raise ValueError(
                    "Foram encontrados grupos duplicados "
                    "no consolidado de pit_stops pela chave "
                    "season + round + driver_id + stop."
                )

            print("Validação final de pit_stops: OK")

        print(
            f"✓ Concluído: "
            f"{quantidade_destino:,} registros"
        )

    except Exception as erro:

        print(f"✗ Erro ao consolidar {base}")
        print(f"  {erro}")

        if argumentos.dataset == "pit_stops":

            con.close()

            raise


# ============================================================
# FINALIZAÇÃO
# ============================================================

con.close()

print("=" * 60)
print("Consolidação finalizada.")
