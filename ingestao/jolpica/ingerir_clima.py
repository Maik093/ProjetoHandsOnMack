import json
from io import BytesIO

import boto3
import requests


# ==================================================
# CONFIGURAÇÕES
# ==================================================

TEMPORADA = 2024
CIRCUITO = "Interlagos"

HEADERS = {
    "User-Agent": "F1DataEngineering/1.0"
}

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "minioadmin123"

BUCKET = "f1-data-lake"

CAMINHO_ARQUIVO = (
    f"bronze/openf1/clima/{TEMPORADA}/"
    f"{CIRCUITO.lower()}/clima.json"
)


# ==================================================
# 1. BUSCAR TODAS AS SESSÕES DA TEMPORADA
# ==================================================

URL_SESSOES = (
    f"https://api.openf1.org/v1/sessions?year={TEMPORADA}"
)

response = requests.get(
    URL_SESSOES,
    headers=HEADERS,
    timeout=30
)

response.raise_for_status()

sessoes = response.json()

print(f"Quantidade de sessões encontradas: {len(sessoes)}")


# ==================================================
# 2. FILTRAR O CIRCUITO
# ==================================================

sessoes_gp = [
    sessao
    for sessao in sessoes
    if sessao.get("circuit_short_name") == CIRCUITO
    and sessao.get("year") == TEMPORADA
]


if not sessoes_gp:
    raise ValueError(
        f"Nenhuma sessão encontrada para "
        f"{CIRCUITO} em {TEMPORADA}."
    )


print(f"\nSessões encontradas em {CIRCUITO}:")

for sessao in sessoes_gp:
    print(
        f"- {sessao['session_name']} | "
        f"session_key={sessao['session_key']} | "
        f"meeting_key={sessao['meeting_key']}"
    )


# ==================================================
# 3. DESCOBRIR O MEETING_KEY
# ==================================================

meeting_keys = {
    sessao["meeting_key"]
    for sessao in sessoes_gp
}


if len(meeting_keys) != 1:
    raise ValueError(
        f"Foram encontrados múltiplos meeting_keys: "
        f"{meeting_keys}"
    )


meeting_key = meeting_keys.pop()

print(f"\nMeeting Key encontrado: {meeting_key}")


# ==================================================
# 4. LOCALIZAR A CORRIDA PRINCIPAL
# ==================================================

corridas = [
    sessao
    for sessao in sessoes_gp
    if sessao.get("session_name") == "Race"
]


if not corridas:
    raise ValueError(
        f"Nenhuma sessão 'Race' encontrada para "
        f"{CIRCUITO} em {TEMPORADA}."
    )


if len(corridas) != 1:
    raise ValueError(
        f"Foram encontradas múltiplas sessões 'Race': "
        f"{corridas}"
    )


corrida = corridas[0]

session_key = corrida["session_key"]


print(f"Session Key encontrado: {session_key}")
print(f"Sessão: {corrida['session_name']}")
print(f"Data inicial: {corrida['date_start']}")
print(f"Data final: {corrida['date_end']}")


# ==================================================
# 5. BUSCAR CLIMA DA CORRIDA
# ==================================================

URL_CLIMA = (
    f"https://api.openf1.org/v1/weather"
    f"?session_key={session_key}"
)

response = requests.get(
    URL_CLIMA,
    headers=HEADERS,
    timeout=30
)

response.raise_for_status()

clima = response.json()


print(
    f"\nQuantidade de registros de clima: "
    f"{len(clima)}"
)


# ==================================================
# 6. CRIAR JSON CONSOLIDADO
# ==================================================

dados_clima = {
    "season": TEMPORADA,
    "circuit": CIRCUITO,
    "meeting_key": meeting_key,
    "session_key": session_key,
    "session_name": corrida["session_name"],
    "date_start": corrida["date_start"],
    "date_end": corrida["date_end"],
    "weather": clima
}


# ==================================================
# 7. CONECTAR AO MINIO
# ==================================================

cliente_minio = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    region_name="us-east-1"
)

print("\nConexão com o MinIO estabelecida!")


# ==================================================
# 8. CONVERTER JSON PARA BYTES
# ==================================================

conteudo = json.dumps(
    dados_clima,
    ensure_ascii=False,
    indent=2
).encode("utf-8")


# ==================================================
# 9. SALVAR NO MINIO
# ==================================================

cliente_minio.put_object(
    Bucket=BUCKET,
    Key=CAMINHO_ARQUIVO,
    Body=BytesIO(conteudo),
    ContentType="application/json"
)


print("\nClima salvo no MinIO com sucesso!")
print(f"Local: {CAMINHO_ARQUIVO}")