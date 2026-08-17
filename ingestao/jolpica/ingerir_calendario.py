import json
from io import BytesIO

import boto3
import requests


# ==================================================
# CONFIGURAÇÕES
# ==================================================

URL = "https://api.jolpi.ca/ergast/f1/2024/races/"

HEADERS = {
    "User-Agent": "F1DataEngineering/1.0"
}

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "minioadmin123"

BUCKET = "f1-data-lake"

CAMINHO_ARQUIVO = "bronze/jolpica/calendario/2024/calendario.json"


# ==================================================
# 1. CONSUMIR JOLPICA
# ==================================================

response = requests.get(
    URL,
    headers=HEADERS,
    timeout=30
)

response.raise_for_status()

dados = response.json()

corridas = dados["MRData"]["RaceTable"]["Races"]

print("API consultada com sucesso!")
print(f"Quantidade de corridas: {len(corridas)}")


# ==================================================
# 2. CONECTAR AO MINIO
# ==================================================

cliente_minio = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    region_name="us-east-1"
)

print("Conexão com o MinIO estabelecida!")


# ==================================================
# 3. CONVERTER JSON PARA BYTES
# ==================================================

conteudo = json.dumps(
    dados,
    ensure_ascii=False,
    indent=2
).encode("utf-8")


# ==================================================
# 4. SALVAR NA BRONZE
# ==================================================

cliente_minio.put_object(
    Bucket=BUCKET,
    Key=CAMINHO_ARQUIVO,
    Body=BytesIO(conteudo),
    ContentType="application/json"
)

print("Dados salvos no MinIO com sucesso!")
print(f"Local: {CAMINHO_ARQUIVO}")