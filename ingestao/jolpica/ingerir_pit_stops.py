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

# Quantidade máxima solicitada em cada página da API.
LIMIT = 100

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
        # 3. BUSCAR PIT STOPS COM PAGINAÇÃO
        # ==================================================

        URL_PIT_STOPS = (
            f"https://api.jolpi.ca/ergast/f1/"
            f"{temporada}/{round_interlagos}/pitstops/"
        )


        offset = 0
        total_esperado = None
        pit_stops_acumulados = []
        dados_consolidados = None


        while True:

            print(
                f"Consultando página de pit stops "
                f"com offset={offset}..."
            )

            response = requests.get(
                URL_PIT_STOPS,
                headers=HEADERS,
                params={
                    "limit": LIMIT,
                    "offset": offset
                },
                timeout=30
            )

            response.raise_for_status()

            dados_pagina = response.json()

            mrdata = dados_pagina.get(
                "MRData",
                {}
            )

            races = (
                mrdata
                .get("RaceTable", {})
                .get("Races", [])
            )


            if not races:

                raise ValueError(
                    f"Sem dados de pit stops para "
                    f"{temporada} no offset {offset}."
                )


            corrida = races[0]

            pit_stops_pagina = corrida.get(
                "PitStops",
                []
            )

            if dados_consolidados is None:

                dados_consolidados = dados_pagina


            try:

                total_esperado = int(
                    mrdata.get("total", 0)
                )

                limite_retorno = int(
                    mrdata.get("limit", LIMIT)
                )

                offset_retorno = int(
                    mrdata.get("offset", offset)
                )

            except (TypeError, ValueError) as erro:

                raise ValueError(
                    f"Metadados de paginação inválidos "
                    f"para {temporada}: {erro}"
                )


            print(
                f"Temporada: {temporada}"
            )

            print(
                f"Total esperado: {total_esperado}"
            )

            print(
                f"Página/offset consultado: "
                f"{offset_retorno}"
            )

            print(
                f"Registros retornados na página: "
                f"{len(pit_stops_pagina)}"
            )


            pit_stops_acumulados.extend(
                pit_stops_pagina
            )


            print(
                f"Registros coletados: "
                f"{len(pit_stops_acumulados)}"
            )


            proximo_offset = (
                offset_retorno
                + limite_retorno
            )


            if proximo_offset >= total_esperado:

                break


            if proximo_offset <= offset:

                raise ValueError(
                    f"Paginação sem avanço para "
                    f"{temporada}: offset atual {offset}, "
                    f"próximo offset {proximo_offset}."
                )


            offset = proximo_offset


        # ==================================================
        # 4. VALIDAR E CONSOLIDAR PIT STOPS
        # ==================================================

        if len(pit_stops_acumulados) != total_esperado:

            raise ValueError(
                f"Divergência na coleta de pit stops "
                f"para {temporada}: esperado "
                f"{total_esperado}, coletado "
                f"{len(pit_stops_acumulados)}."
            )


        dados_consolidados[
            "MRData"
        ][
            "RaceTable"
        ][
            "Races"
        ][
            0
        ][
            "PitStops"
        ] = pit_stops_acumulados


        pit_stops = pit_stops_acumulados


        print(
            f"Corrida: {corrida['raceName']}"
        )

        print(
            f"Quantidade de pit stops: "
            f"{len(pit_stops)}"
        )

        print(
            "Validação final: OK"
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
            dados_consolidados,
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
