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
# CONSOLIDAÇÃO
# ============================================================

for base in BASES:

    origem = f"s3://{BUCKET}/{PASTA_ENTRADA}/{base}/**/*.parquet"

    destino = f"s3://{BUCKET}/{PASTA_SAIDA}/{base}.parquet"

    print("=" * 60)
    print(f"Consolidando: {base}")
    print(f"Origem:  {origem}")
    print(f"Destino: {destino}")

    try:

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

        quantidade = con.execute(f"""
            SELECT COUNT(*)
            FROM read_parquet('{destino}')
        """).fetchone()[0]

        print(f"✓ Concluído: {quantidade:,} registros")

    except Exception as erro:

        print(f"✗ Erro ao consolidar {base}")
        print(f"  {erro}")


# ============================================================
# FINALIZAÇÃO
# ============================================================

con.close()

print("=" * 60)
print("Consolidação finalizada.")