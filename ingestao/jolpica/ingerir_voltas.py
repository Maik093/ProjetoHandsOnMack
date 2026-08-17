import json
from io import BytesIO

import boto3
import requests


# ==================================================
# CONFIGURAÇÕES
# ==================================================

TEMPORADA = 2024
ROUND = 21

HEADERS = {
    "User-Agent": "F1DataEngineering/1.0"
}

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "minioadmin123"

BUCKET = "f1-data-lake"

CAMINHO_ARQUIVO = (
    f"bronze/jolpica/voltas/{TEMPORADA}/"
    f"round_{ROUND}/voltas.json"
)


# ==================================================
# 1. DESCOBRIR QUANTIDADE DE VOLTAS DA CORRIDA
# ==================================================

URL_RESULTADOS = (
    f"https://api.jolpi.ca/ergast/f1/"
    f"{TEMPORADA}/{ROUND}/results/"
)

response = requests.get(
    URL_RESULTADOS,
    headers=HEADERS,
    timeout=30
)

response.raise_for_status()

dados_resultados = response.json()

corrida = dados_resultados["MRData"]["RaceTable"]["Races"][0]

resultados = corrida["Results"]


# Pega a maior quantidade de voltas registrada
total_voltas = max(
    int(resultado["laps"])
    for resultado in resultados
)

print("Corrida encontrada!")
print(f"Temporada: {TEMPORADA}")
print(f"Round: {ROUND}")
print(f"Corrida: {corrida['raceName']}")
print(f"Total de voltas: {total_voltas}")


# ==================================================
# 2. BUSCAR TODAS AS VOLTAS
# ==================================================

todas_as_voltas = []

for volta in range(1, total_voltas + 1):

    print(f"Consultando volta {volta}/{total_voltas}...")

    url = (
        f"https://api.jolpi.ca/ergast/f1/"
        f"{TEMPORADA}/{ROUND}/laps/{volta}/"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    dados_volta = response.json()

    races = (
        dados_volta
        .get("MRData", {})
        .get("RaceTable", {})
        .get("Races", [])
    )

    # Se não houver dados para a volta, pula
    if not races:
        print(f"Volta {volta}: sem dados")
        continue

    laps = races[0].get("Laps", [])

    if not laps:
        print(f"Volta {volta}: sem dados")
        continue

    todas_as_voltas.extend(laps)


# ==================================================
# 3. MONTAR JSON CONSOLIDADO
# ==================================================

dados_consolidados = {
    "season": TEMPORADA,
    "round": ROUND,
    "raceName": corrida["raceName"],
    "circuit": corrida["Circuit"],
    "date": corrida["date"],
    "time": corrida["time"],
    "totalLaps": total_voltas,
    "Laps": todas_as_voltas
}


print()
print("Coleta das voltas concluída!")
print(f"Voltas coletadas: {len(todas_as_voltas)}")


# ==================================================
# 4. CONECTAR AO MINIO
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
# 5. CONVERTER JSON PARA BYTES
# ==================================================

conteudo = json.dumps(
    dados_consolidados,
    ensure_ascii=False,
    indent=2
).encode("utf-8")


# ==================================================
# 6. SALVAR NO MINIO
# ==================================================

cliente_minio.put_object(
    Bucket=BUCKET,
    Key=CAMINHO_ARQUIVO,
    Body=BytesIO(conteudo),
    ContentType="application/json"
)

print("Dados de voltas salvos no MinIO com sucesso!")
print(f"Local: {CAMINHO_ARQUIVO}")