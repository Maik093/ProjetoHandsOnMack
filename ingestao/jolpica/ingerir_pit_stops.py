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
        # 3. BUSCAR TODOS OS PIT STOPS
        # ==================================================

        limit = 100
        offset = 0

        todos_pit_stops = []
        dados_primeira_requisicao = None

        while True:

            URL = (
                f"https://api.jolpi.ca/ergast/f1/"
                f"{temporada}/{round_interlagos}/pitstops/"
                f"?limit={limit}&offset={offset}"
            )

            response = requests.get(
                URL,
                headers=HEADERS,
                timeout=30
            )

            response.raise_for_status()

            dados = response.json()

            # Guarda a estrutura original da primeira resposta
            if dados_primeira_requisicao is None:
                dados_primeira_requisicao = dados

            races = (
                dados.get("MRData", {})
                .get("RaceTable", {})
                .get("Races", [])
            )

            if not races:
                break

            corrida = races[0]

            pit_stops = corrida.get(
                "PitStops",
                []
            )

            todos_pit_stops.extend(pit_stops)

            # Informações da paginação
            mrdata = dados.get("MRData", {})

            total = int(mrdata.get("total", 0))
            current_limit = int(mrdata.get("limit", limit))
            current_offset = int(mrdata.get("offset", offset))

            print(
                f"Requisição: offset={current_offset} | "
                f"recebidos={len(pit_stops)} | "
                f"total={total}"
            )

            # Verifica se já buscou tudo
            if (
                current_offset + len(pit_stops)
                >= total
            ):
                break

            # Próxima página
            offset += current_limit

        # ==================================================
        # 4. MONTAR RESPOSTA COMPLETA
        # ==================================================

        dados["MRData"]["RaceTable"]["Races"][0][
            "PitStops"
        ] = todos_pit_stops

        print(
            f"Corrida: {corrida['raceName']}"
        )

        print(
            f"Quantidade total de pit stops: "
            f"{len(todos_pit_stops)}"
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