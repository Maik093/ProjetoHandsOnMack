from __future__ import annotations

import os
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]

# =========================
# Configuração MinIO
# =========================

ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
ACCESS = os.getenv("MINIO_ACCESS_KEY", "admin")
SECRET = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
BUCKET = os.getenv("MINIO_BUCKET", "f1-data-lake")


# =========================
# Saídas
# =========================

# Destino principal: MinIO
OUTPUT_S3 = "ml/dataset/dataset_ml_interlagos.parquet"

# Saída local opcional
OUTPUT_LOCAL = ROOT / "ml" / "dataset" / "dataset_ml_interlagos.parquet"


# =========================
# Gold
# =========================

GOLD = {
    "dim_corrida": "gold/dim_corrida.parquet",
    "dim_piloto": "gold/dim_piloto.parquet",
    "dim_equipe": "gold/dim_equipe.parquet",
    "fct_piloto_corrida": "gold/fct_piloto_corrida.parquet",
    "fct_voltas": "gold/fct_voltas.parquet",
    "fct_pit_stops": "gold/fct_pit_stops.parquet",
    "fct_stints": "gold/fct_stints.parquet",
    "fct_clima": "gold/fct_clima.parquet",
}


def s3(rel: str) -> str:
    return f"s3://{BUCKET}/{rel}"


def main():

    con = duckdb.connect()

    try:

        # =====================================================
        # 1. Configuração DuckDB + MinIO
        # =====================================================

        con.execute("INSTALL httpfs")
        con.execute("LOAD httpfs")

        endpoint = (
            ENDPOINT
            .replace("http://", "")
            .replace("https://", "")
        )

        con.execute(f"SET s3_endpoint='{endpoint}'")
        con.execute(f"SET s3_access_key_id='{ACCESS}'")
        con.execute(f"SET s3_secret_access_key='{SECRET}'")
        con.execute("SET s3_use_ssl=false")
        con.execute("SET s3_url_style='path'")

        # Workaround DuckDB + MinIO
        con.execute(
            "SET disabled_optimizers='statistics_propagation'"
        )

        # =====================================================
        # 2. Leitura das tabelas Gold
        # =====================================================

        for name, path in GOLD.items():

            con.execute(
                f"""
                CREATE OR REPLACE VIEW src_{name} AS
                SELECT *
                FROM read_parquet('{s3(path)}')
                """
            )

        # =====================================================
        # 3. Agregação de clima
        # =====================================================

        con.execute(
            """
            CREATE OR REPLACE TEMP VIEW climate AS

            SELECT
                race_key,

                AVG(air_temp) AS air_temp_media,
                AVG(track_temp) AS track_temp_media,
                AVG(humidity) AS humidity_media,
                AVG(pressure) AS pressure_media,
                AVG(wind_speed) AS wind_speed_medio,

                CAST(
                    MAX(
                        CASE
                            WHEN COALESCE(rainfall, 0) > 0
                            THEN 1
                            ELSE 0
                        END
                    ) AS BOOLEAN
                ) AS rainfall_ocorreu

            FROM src_fct_clima

            GROUP BY race_key
            """
        )

        # =====================================================
        # 4. Agregação de stints / pneus
        # =====================================================

        con.execute(
            """
            CREATE OR REPLACE TEMP VIEW stints AS

            WITH usage AS (

                SELECT
                    race_key,
                    driver_key,
                    compound,
                    SUM(voltas_observadas) AS total_laps

                FROM src_fct_stints

                WHERE compound IS NOT NULL

                GROUP BY
                    race_key,
                    driver_key,
                    compound
            ),

            ranked AS (

                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY race_key, driver_key
                        ORDER BY
                            total_laps DESC,
                            compound ASC
                    ) AS rn

                FROM usage
            )

            SELECT
                s.race_key,
                s.driver_key,

                COUNT(*)::INTEGER
                    AS qtd_stints,

                COUNT(DISTINCT s.compound)::INTEGER
                    AS qtd_compostos_distintos,

                MAX(
                    CASE
                        WHEN s.stint_number = 1
                        THEN s.compound
                    END
                ) AS primeiro_composto,

                MAX(
                    CASE
                        WHEN r.rn = 1
                        THEN r.compound
                    END
                ) AS composto_mais_utilizado,

                AVG(s.voltas_observadas)
                    AS voltas_stint_medio

            FROM src_fct_stints s

            LEFT JOIN ranked r
                ON r.race_key = s.race_key
               AND r.driver_key = s.driver_key
               AND r.compound = s.compound

            GROUP BY
                s.race_key,
                s.driver_key
            """
        )

        # =====================================================
        # 5. Agregação de pit stops
        # =====================================================

        con.execute(
            """
            CREATE OR REPLACE TEMP VIEW pits AS

            SELECT
                race_key,
                driver_key,

                COUNT(*)::INTEGER
                    AS qtd_pit_stops,

                MEDIAN(
                    CASE
                        WHEN pit_stop_convencional
                        THEN duration_seconds
                    END
                ) AS duracao_mediana_pit_convencional

            FROM src_fct_pit_stops

            GROUP BY
                race_key,
                driver_key
            """
        )

        # =====================================================
        # 6. Dataset ML
        # =====================================================

        con.execute(
            """
            CREATE OR REPLACE TEMP VIEW dataset_ml AS

            SELECT

                -- Identificadores
                p.pilot_race_key,
                p.race_key,
                p.driver_key,
                p.team_key,

                -- Contexto
                r.season,
                r.round,
                r.race_name,

                d.name AS full_name,
                e.constructor_name,

                -- Pace
                p.grid,
                p.ritmo_representativo_pct,
                p.voltas_analisadas,
                p.voltas_disponiveis,
                p.cobertura_ritmo_pct,
                p.amostra_reduzida,

                -- Pit stops
                COALESCE(
                    ps.qtd_pit_stops,
                    0
                )::INTEGER AS qtd_pit_stops,

                ps.duracao_mediana_pit_convencional,

                -- Stints / pneus
                COALESCE(
                    st.qtd_stints,
                    0
                )::INTEGER AS qtd_stints,

                COALESCE(
                    st.qtd_compostos_distintos,
                    0
                )::INTEGER AS qtd_compostos_distintos,

                st.primeiro_composto,
                st.composto_mais_utilizado,
                st.voltas_stint_medio,

                -- Clima
                c.air_temp_media,
                c.track_temp_media,
                c.humidity_media,
                c.pressure_media,
                c.wind_speed_medio,
                c.rainfall_ocorreu,

                -- Target
                CAST(
                    CASE
                        WHEN p.position = 1
                        THEN 1
                        ELSE 0
                    END
                    AS BOOLEAN
                ) AS vitoria

            FROM src_fct_piloto_corrida p

            INNER JOIN src_dim_corrida r

                ON r.race_key = p.race_key

               AND r.circuit_name =
                   'Autódromo José Carlos Pace'

               -- Dataset enriquecido:
               -- somente 2018–2025
               AND r.season BETWEEN 2018 AND 2025

            LEFT JOIN src_dim_piloto d
                ON d.driver_key = p.driver_key

            LEFT JOIN src_dim_equipe e
                ON e.team_key = p.team_key

            LEFT JOIN pits ps
                ON ps.race_key = p.race_key
               AND ps.driver_key = p.driver_key

            LEFT JOIN stints st
                ON st.race_key = p.race_key
               AND st.driver_key = p.driver_key

            LEFT JOIN climate c
                ON c.race_key = p.race_key
            """
        )

        # =====================================================
        # 7. Validações
        # =====================================================

        cols = [
            r[0]
            for r in con.execute(
                """
                SELECT column_name
                FROM duckdb_columns()
                WHERE table_name = 'dataset_ml'
                """
            ).fetchall()
        ]

        assert "position" not in cols
        assert "vitoria" in cols

        total, wins, nonwins = con.execute(
            """
            SELECT
                COUNT(*),

                SUM(
                    CASE
                        WHEN vitoria
                        THEN 1
                        ELSE 0
                    END
                ),

                SUM(
                    CASE
                        WHEN NOT vitoria
                        THEN 1
                        ELSE 0
                    END
                )

            FROM dataset_ml
            """
        ).fetchone()

        dup = con.execute(
            """
            SELECT COUNT(*)

            FROM (
                SELECT
                    race_key,
                    driver_key

                FROM dataset_ml

                GROUP BY
                    race_key,
                    driver_key

                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]

        assert dup == 0, (
            f"Duplicidades piloto-corrida: {dup}"
        )

        # =====================================================
        # 8. Salvar no MinIO
        # =====================================================

        caminho_minio = s3(OUTPUT_S3)

        print("\n=== SALVANDO DATASET NO MINIO ===")
        print(f"Destino: {caminho_minio}")

        con.execute(
            f"""
            COPY (
                SELECT *
                FROM dataset_ml
                ORDER BY
                    season,
                    round,
                    grid,
                    driver_key
            )

            TO '{caminho_minio}'

            (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """
        )

        # =====================================================
        # 9. Validar o arquivo gravado no MinIO
        # =====================================================

        minio_total, minio_wins = con.execute(
            f"""
            SELECT
                COUNT(*),

                SUM(
                    CASE
                        WHEN vitoria
                        THEN 1
                        ELSE 0
                    END
                )

            FROM read_parquet('{caminho_minio}')
            """
        ).fetchone()

        assert minio_total == total, (
            f"Quantidade divergente após gravação: "
            f"dataset={total}, minio={minio_total}"
        )

        assert minio_wins == wins, (
            f"Vitórias divergentes após gravação: "
            f"dataset={wins}, minio={minio_wins}"
        )

        # =====================================================
        # 10. Salvar cópia local
        # =====================================================

        OUTPUT_LOCAL.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        caminho_local = str(OUTPUT_LOCAL).replace(
            "'",
            "''"
        )

        con.execute(
            f"""
            COPY (
                SELECT *
                FROM dataset_ml
                ORDER BY
                    season,
                    round,
                    grid,
                    driver_key
            )

            TO '{caminho_local}'

            (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """
        )

        # =====================================================
        # 11. Resultado
        # =====================================================

        print("\n=== DATASET ML INTERLAGOS ===")

        print(f"Linhas: {total}")
        print(f"Colunas: {len(cols)}")
        print(f"Vitórias: {wins}")
        print(f"Não vitórias: {nonwins}")
        print(f"Duplicidades piloto-corrida: {dup}")

        print("\n=== DESTINOS ===")
        print(
            f"MinIO: s3://{BUCKET}/{OUTPUT_S3}"
        )
        print(
            f"Local: {OUTPUT_LOCAL}"
        )

        print("\n=== VALIDAÇÃO DO MINIO ===")
        print(
            f"Linhas no MinIO: {minio_total}"
        )
        print(
            f"Vitórias no MinIO: {minio_wins}"
        )

        print("\n=== EXEMPLO ===")

        print(
            con.execute(
                """
                SELECT
                    season,
                    round,
                    full_name,
                    constructor_name,
                    grid,
                    ritmo_representativo_pct,
                    qtd_pit_stops,
                    qtd_stints,
                    primeiro_composto,
                    composto_mais_utilizado,
                    rainfall_ocorreu,
                    vitoria

                FROM dataset_ml

                ORDER BY
                    season,
                    round,
                    grid

                LIMIT 5
                """
            )
            .df()
            .to_string(index=False)
        )

    finally:
        con.close()


if __name__ == "__main__":
    main()