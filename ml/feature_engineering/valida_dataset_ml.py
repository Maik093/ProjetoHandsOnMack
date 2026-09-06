from __future__ import annotations

import os
import duckdb


ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
ACCESS = os.getenv("MINIO_ACCESS_KEY", "admin")
SECRET = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
BUCKET = os.getenv("MINIO_BUCKET", "f1-data-lake")

DATASET = "ml/dataset/dataset_ml_interlagos.parquet"


def s3(path: str) -> str:
    return f"s3://{BUCKET}/{path}"


def main():

    con = duckdb.connect()

    try:
        # =========================
        # Configuração MinIO
        # =========================

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

        # =========================
        # Dataset ML
        # =========================

        con.execute(f"""
            CREATE OR REPLACE VIEW dataset_ml AS
            SELECT *
            FROM read_parquet('{s3(DATASET)}')
        """)

        # =========================
        # 1. Cobertura geral por temporada
        # =========================

        print("\n=== COBERTURA GERAL POR TEMPORADA ===")

        cobertura = con.execute("""
            SELECT
                season,
                COUNT(*) AS registros,

                COUNT(ritmo_representativo_pct)
                    AS pace_disponivel,

                COUNT(duracao_mediana_pit_convencional)
                    AS pit_duracao_disponivel,

                COUNT(qtd_stints)
                    AS stints_disponivel,

                COUNT(primeiro_composto)
                    AS primeiro_composto_disponivel,

                COUNT(composto_mais_utilizado)
                    AS composto_mais_utilizado_disponivel,

                COUNT(air_temp_media)
                    AS air_temp_disponivel,

                COUNT(track_temp_media)
                    AS track_temp_disponivel,

                COUNT(humidity_media)
                    AS humidity_disponivel,

                COUNT(pressure_media)
                    AS pressure_disponivel,

                COUNT(wind_speed_medio)
                    AS wind_disponivel,

                COUNT(rainfall_ocorreu)
                    AS rainfall_disponivel

            FROM dataset_ml

            GROUP BY season

            ORDER BY season
        """).df()

        # Percentuais de cobertura
        colunas_cobertura = [
            "pace_disponivel",
            "pit_duracao_disponivel",
            "stints_disponivel",
            "primeiro_composto_disponivel",
            "composto_mais_utilizado_disponivel",
            "air_temp_disponivel",
            "track_temp_disponivel",
            "humidity_disponivel",
            "pressure_disponivel",
            "wind_disponivel",
            "rainfall_disponivel",
        ]

        for coluna in colunas_cobertura:

            percentual = coluna.replace(
                "_disponivel",
                "_cobertura_pct"
            )

            cobertura[percentual] = (
                cobertura[coluna]
                / cobertura["registros"]
                * 100
            ).round(2)

        print(
            cobertura.to_string(index=False)
        )

        # =========================
        # 2. Cobertura resumida
        # =========================

        print("\n=== RESUMO DE COBERTURA POR TEMPORADA ===")

        resumo = con.execute("""
            SELECT
                season,
                COUNT(*) AS registros,

                ROUND(
                    100.0 *
                    COUNT(ritmo_representativo_pct)
                    / COUNT(*),
                    2
                ) AS pace_pct,

                ROUND(
                    100.0 *
                    COUNT(primeiro_composto)
                    / COUNT(*),
                    2
                ) AS pneus_pct,

                ROUND(
                    100.0 *
                    COUNT(air_temp_media)
                    / COUNT(*),
                    2
                ) AS clima_pct

            FROM dataset_ml

            GROUP BY season

            ORDER BY season
        """).df()

        print(
            resumo.to_string(index=False)
        )

        # =========================
        # 3. Nulos por variável
        # =========================

        print("\n=== NULOS NO DATASET ===")

        nulos = con.execute("""
            SELECT
                COUNT(*) AS total
            FROM dataset_ml
        """).fetchone()[0]

        variaveis = [
            "grid",
            "ritmo_representativo_pct",
            "voltas_analisadas",
            "voltas_disponiveis",
            "cobertura_ritmo_pct",
            "qtd_pit_stops",
            "duracao_mediana_pit_convencional",
            "qtd_stints",
            "qtd_compostos_distintos",
            "primeiro_composto",
            "composto_mais_utilizado",
            "voltas_stint_medio",
            "air_temp_media",
            "track_temp_media",
            "humidity_media",
            "pressure_media",
            "wind_speed_medio",
            "rainfall_ocorreu",
        ]

        resultado_nulos = []

        for coluna in variaveis:

            qtd_nulos = con.execute(
                f"""
                SELECT COUNT(*)
                FROM dataset_ml
                WHERE "{coluna}" IS NULL
                """
            ).fetchone()[0]

            resultado_nulos.append(
                (
                    coluna,
                    qtd_nulos,
                    round(
                        qtd_nulos / nulos * 100,
                        2
                    ),
                    round(
                        (nulos - qtd_nulos)
                        / nulos * 100,
                        2
                    ),
                )
            )

        print(
            f"{'Variável':35}"
            f"{'Nulos':>10}"
            f"{'% Nulos':>12}"
            f"{'% Disponível':>15}"
        )

        print("-" * 75)

        for (
            coluna,
            qtd_nulos,
            pct_nulos,
            pct_disponivel,
        ) in resultado_nulos:

            print(
                f"{coluna:35}"
                f"{qtd_nulos:>10}"
                f"{pct_nulos:>11.2f}%"
                f"{pct_disponivel:>14.2f}%"
            )

        # =========================
        # 4. Cobertura dos principais
        #    grupos de features
        # =========================

        print(
            "\n=== COBERTURA DOS GRUPOS DE FEATURES ==="
        )

        grupos = {
            "Pace": [
                "ritmo_representativo_pct",
                "voltas_analisadas",
                "voltas_disponiveis",
                "cobertura_ritmo_pct",
            ],

            "Pit stops": [
                "qtd_pit_stops",
                "duracao_mediana_pit_convencional",
            ],

            "Stints/Pneus": [
                "qtd_stints",
                "qtd_compostos_distintos",
                "primeiro_composto",
                "composto_mais_utilizado",
                "voltas_stint_medio",
            ],

            "Clima": [
                "air_temp_media",
                "track_temp_media",
                "humidity_media",
                "pressure_media",
                "wind_speed_medio",
                "rainfall_ocorreu",
            ],
        }

        for grupo, colunas in grupos.items():

            disponibilidades = []

            for coluna in colunas:

                disponivel = con.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM dataset_ml
                    WHERE "{coluna}" IS NOT NULL
                    """
                ).fetchone()[0]

                disponibilidades.append(
                    disponivel / nulos * 100
                )

            print(
                f"{grupo:20} "
                f"mínimo={min(disponibilidades):6.2f}% "
                f"máximo={max(disponibilidades):6.2f}%"
            )

        # =========================
        # 5. Distribuição de vitórias
        # por temporada
        # =========================

        print(
            "\n=== VITÓRIAS POR TEMPORADA ==="
        )

        vitorias = con.execute("""
            SELECT
                season,
                COUNT(*) AS pilotos,
                SUM(
                    CASE
                        WHEN vitoria
                        THEN 1
                        ELSE 0
                    END
                ) AS vitorias
            FROM dataset_ml
            GROUP BY season
            ORDER BY season
        """).df()

        print(
            vitorias.to_string(index=False)
        )

        # =========================
        # 6. Avisos automáticos
        # =========================

        print("\n=== DIAGNÓSTICO ===")

        baixa_cobertura = resumo[
            (
                (resumo["pace_pct"] < 80)
                |
                (resumo["pneus_pct"] < 80)
                |
                (resumo["clima_pct"] < 80)
            )
        ]

        if len(baixa_cobertura) > 0:

            print(
                "Temporadas com pelo menos "
                "uma cobertura principal abaixo de 80%:"
            )

            print(
                baixa_cobertura.to_string(
                    index=False
                )
            )

        else:

            print(
                "Nenhuma temporada apresentou "
                "cobertura principal abaixo de 80%."
            )

    finally:
        con.close()


if __name__ == "__main__":
    main()