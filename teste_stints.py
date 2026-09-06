import duckdb


MINIO_BUCKET = "f1-data-lake"
DATASET = "ml/prepared/model_data_base.parquet"


def main():

    con = duckdb.connect()

    try:
        con.execute("INSTALL httpfs")
        con.execute("LOAD httpfs")

        con.execute(
            "SET s3_endpoint='localhost:9000'"
        )
        con.execute(
            "SET s3_access_key_id='admin'"
        )
        con.execute(
            "SET s3_secret_access_key='minioadmin123'"
        )
        con.execute(
            "SET s3_use_ssl=false"
        )
        con.execute(
            "SET s3_url_style='path'"
        )

        con.execute(
            "SET disabled_optimizers="
            "'statistics_propagation'"
        )

        uri = (
            f"s3://{MINIO_BUCKET}/{DATASET}"
        )

        print("=== SCHEMA model_data_base ===")
        print(f"Arquivo: {uri}")
        print()

        schema = con.execute(
            f"""
            DESCRIBE
            SELECT *
            FROM read_parquet('{uri}')
            """
        ).fetchdf()

        print(
            schema[
                [
                    "column_name",
                    "column_type",
                ]
            ].to_string(index=False)
        )

        print()
        print(
            f"Total de colunas: {len(schema)}"
        )

    finally:
        con.close()


if __name__ == "__main__":
    main()