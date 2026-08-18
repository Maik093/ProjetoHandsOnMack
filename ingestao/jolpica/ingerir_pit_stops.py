import json
from io import BytesIO

import boto3
import requests


# ==================================================
# CONFIGURAÇÕES
# ==================================================

ANO_INICIAL = 2015
ANO_FINAL = 2025

CIRCUITO = "interlagos"

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
# PERCORRER TEMPORADAS
# ==================================================

for temporada in range(ANO_INICIAL, ANO_FINAL + 1):

    print()
    print("=" * 60)
    print(f"Processando pit stops: {temporada}")
    print("=" * 60)


    try:

        # ==================================================
        # 1. BUSCAR CALENDÁRIO
        # ==================================================

        URL_CALENDARIO = (
            f"https://api.jolpi.ca/ergast/f1/"
            f"{temporada}/races/"
        )

        response = requests.get(
            URL_CALENDARIO,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        dados_calendario = response.json()

        corridas = (
            dados_calendario["MRData"]
            ["RaceTable"]
            ["Races"]
        )


        # ==================================================
        # 2. ENCONTRAR INTERLAGOS
        # ==================================================

        interlagos = [
            corrida
            for corrida in corridas
            if corrida.get("Circuit", {}).get("circuitId")
            == CIRCUITO
        ]


        if not interlagos:

            print(
                f"Interlagos não encontrado "
                f"em {temporada}."
            )

            continue


        round_interlagos = interlagos[0]["round"]


        print(
            f"Interlagos encontrado - "
            f"Round {round_interlagos}"
        )


        # ==================================================
        # 3. BUSCAR PIT STOPS
        # ==================================================

        URL = (
            f"https://api.jolpi.ca/ergast/f1/"
            f"{temporada}/{round_interlagos}/pitstops/"
        )

        response = requests.get(
            URL,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        dados = response.json()


        # ==================================================
        # 4. EXTRAIR CORRIDA
        # ==================================================

        races = (
            dados.get("MRData", {})
            .get("RaceTable", {})
            .get("Races", [])
        )


        if not races:

            print(
                f"Sem dados de pit stops "
                f"para {temporada}."
            )

            continue


        corrida = races[0]

        pit_stops = corrida.get(
            "PitStops",
            []
        )


        print(
            f"Corrida: {corrida['raceName']}"
        )

        print(
            f"Quantidade de pit stops: "
            f"{len(pit_stops)}"
        )


        # ==================================================
        # 5. SALVAR NO MINIO
        # ==================================================

        caminho = (
            f"bronze/jolpica/pit_stops/"
            f"{temporada}/interlagos/"
            f"pit_stops.json"
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
            f"Pit stops {temporada} "
            "salvos no MinIO!"
        )


    except Exception as erro:

        print(
            f"Erro ao processar {temporada}: "
            f"{erro}"
        )


print()
print("=" * 60)
print("INGESTÃO DOS PIT STOPS CONCLUÍDA!")
print("=" * 60)