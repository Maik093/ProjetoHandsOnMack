import json
from io import BytesIO

import boto3
import requests


# ==================================================
# CONFIGURAÇÕES
# ==================================================

TEMPORADA = 2024
ROUND = 21

URL = f"https://api.jolpi.ca/ergast/f1/{TEMPORADA}/{ROUND}/pitstops/"

HEADERS = {
    "User-Agent": "F1DataEngineering/1.0"
}

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "minioadmin123"

BUCKET = "f1-data-lake"

CAMINHO_ARQUIVO = (
    f"bronze/jolpica/pit_stops/{TEMPORADA}/"
    f"round_{ROUND}/pit_stops.json"
)


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

corrida = dados["MRData"]["RaceTable"]["Races"][0]

pit_stops = corrida["PitStops"]

print("API consultada com sucesso!")
print(f"Temporada: {TEMPORADA}")
print(f"Round: {ROUND}")
print(f"Corrida: {corrida['raceName']}")
print(f"Quantidade de pit stops: {len(pit_stops)}")


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

print("Pit stops salvos no MinIO com sucesso!")
print(f"Local: {CAMINHO_ARQUIVO}")