import os
from pathlib import Path
import duckdb
import streamlit as st

DATASETS = {
    "calendario": "s3://f1-data-lake/silver/consolidado/calendario.parquet",
    "resultados": "s3://f1-data-lake/silver/consolidado/resultados.parquet",
    "voltas": "s3://f1-data-lake/silver/consolidado/voltas.parquet",
    "pit_stops": "s3://f1-data-lake/silver/consolidado/pit_stops.parquet",
    "pneus": "s3://f1-data-lake/silver/consolidado/pneus.parquet",
    "clima": "s3://f1-data-lake/silver/consolidado/clima.parquet",
    "driver_mapping": "s3://f1-data-lake/silver/driver_mapping/driver_mapping.parquet",
}


def _secret(section, key, env_name, default=None):
    try:
        value = st.secrets[section][key]
        if value is not None:
            return value
    except Exception:
        pass
    return os.getenv(env_name, default)


def _minio_config():
    return {
        "endpoint": _secret("minio", "endpoint", "MINIO_ENDPOINT", "localhost:9000"),
        "access_key": _secret("minio", "access_key", "MINIO_ACCESS_KEY", "admin"),
        "secret_key": _secret("minio", "secret_key", "MINIO_SECRET_KEY", None),
        "use_ssl": str(_secret("minio", "use_ssl", "MINIO_USE_SSL", "false")).lower()
        == "true",
    }


@st.cache_resource
def get_duckdb_connection():
    cfg = _minio_config()
    if not cfg["secret_key"]:
        raise RuntimeError(
            "MINIO_SECRET_KEY não configurada. Defina-a em .streamlit/secrets.toml "
            "ou como variável de ambiente."
        )

    extension_dir = Path(".duckdb_extensions")
    extension_dir.mkdir(exist_ok=True)

    con = duckdb.connect(
        config={"extension_directory": str(extension_dir)}
    )
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    con.execute(
        f"""
        SET s3_endpoint='{cfg["endpoint"]}';
        SET s3_access_key_id='{cfg["access_key"]}';
        SET s3_secret_access_key='{cfg["secret_key"]}';
        SET s3_use_ssl={'true' if cfg["use_ssl"] else 'false'};
        SET s3_url_style='path';
        """
    )
    return con


@st.cache_data(show_spinner="Carregando Parquets do MinIO...")
def load_all_datasets():
    con = get_duckdb_connection()
    data = {}
    for name, path in DATASETS.items():
        data[name] = con.sql(
            f"SELECT * FROM read_parquet('{path}')"
        ).df()
    return data
