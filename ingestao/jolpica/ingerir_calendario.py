import json
from io import BytesIO

import boto3
import requests


# ==================================================
# CONFIGURAÇÕES
# ==================================================

ANO_INICIAL = 2015
ANO_FINAL = 2025

HEADERS = {
    "User-Agent": "F1DataEngineering/1.0"
}

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "minioadmin123"

BUCKET = "f1-data-lake"


# ==================================================
# CONECTAR AO MINIO
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
# PERCORRER AS TEMPORADAS
# ==================================================

for temporada in range(ANO_INICIAL, ANO_FINAL + 1):

    print()
    print("=" * 60)
    print(f"Processando temporada: {temporada}")
    print("=" * 60)

    URL = (
        f"https://api.jolpi.ca/ergast/f1/"
        f"{temporada}/races/"
    )

    try:

        # ==================================================
        # CONSUMIR JOLPICA
        # ==================================================

        response = requests.get(
            URL,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        dados = response.json()

        corridas = (
            dados["MRData"]
            ["RaceTable"]
            ["Races"]
        )

        print(
            f"Quantidade de corridas: "
            f"{len(corridas)}"
        )


        # ==================================================
        # LOCALIZAR INTERLAGOS
        # ==================================================

        interlagos = [
            corrida
            for corrida in corridas
            if corrida.get("Circuit", {}).get("circuitId")
            == "interlagos"
        ]


        if interlagos:

            corrida = interlagos[0]

            print(
                f"Interlagos encontrado!"
            )

            print(
                f"Round: {corrida['round']}"
            )

            print(
                f"Corrida: {corrida['raceName']}"
            )

            print(
                f"Data: {corrida['date']}"
            )

        else:

            print(
                "Interlagos não encontrado "
                f"na temporada {temporada}."
            )


        # ==================================================
        # SALVAR NO MINIO
        # ==================================================

        caminho = (
            f"bronze/jolpica/calendario/"
            f"{temporada}/calendario.json"
        )

        conteudo = json.dumps(
            dados,
            ensure_ascii=False,
            indent=2
        ).encode("utf-8")


        cliente_minio.put_object(
            Bucket=BUCKET,
            Key=caminho,
            Body=BytesIO(conteudo),
            ContentType="application/json"
        )

        print(
            f"Calendário {temporada} "
            "salvo no MinIO com sucesso!"
        )


    except Exception as erro:

        print(
            f"Erro ao processar a temporada "
            f"{temporada}: {erro}"
        )


print()
print("=" * 60)
print("INGESTÃO DOS CALENDÁRIOS CONCLUÍDA!")
print("=" * 60)