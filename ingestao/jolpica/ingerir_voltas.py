import json
import time
from io import BytesIO

import boto3
import requests
from botocore.exceptions import ClientError


# ==================================================
# CONFIGURAÇÕES
# ==================================================

ANO_INICIAL = 2015
ANO_FINAL = 2025

CIRCUITO = "interlagos"

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "minioadmin123"

BUCKET = "f1-data-lake"

HEADERS = {
    "User-Agent": "F1DataEngineering/1.0"
}


# ==================================================
# CONTROLE DA API
# ==================================================

LIMIT = 100

# Pausa entre requisições
ESPERA_ENTRE_REQUISICOES = 2

# Pausa entre temporadas
ESPERA_ENTRE_TEMPORADAS = 30


# ==================================================
# CONEXÃO COM MINIO
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
# SESSION HTTP
# ==================================================

session = requests.Session()

session.headers.update(HEADERS)


# ==================================================
# VERIFICAR ARQUIVO NO MINIO
# ==================================================

def arquivo_existe_no_minio(caminho):

    try:

        cliente_minio.head_object(
            Bucket=BUCKET,
            Key=caminho
        )

        return True

    except ClientError as erro:

        codigo = (
            erro.response
            .get("Error", {})
            .get("Code")
        )

        if codigo in ["404", "NoSuchKey"]:

            return False

        raise


# ==================================================
# SALVAR CHECKPOINT
# ==================================================

def salvar_checkpoint(
    temporada,
    offset,
    voltas_por_numero
):

    caminho = (
        f"bronze/jolpica/voltas/"
        f"checkpoints/"
        f"{temporada}_checkpoint.json"
    )

    dados = {

        "season": temporada,

        "next_offset": offset,

        "voltas": voltas_por_numero
    }

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
        f"Checkpoint salvo: "
        f"offset {offset}"
    )


# ==================================================
# LER CHECKPOINT
# ==================================================

def ler_checkpoint(temporada):

    caminho = (
        f"bronze/jolpica/voltas/"
        f"checkpoints/"
        f"{temporada}_checkpoint.json"
    )

    try:

        response = cliente_minio.get_object(

            Bucket=BUCKET,

            Key=caminho
        )

        conteudo = (
            response["Body"]
            .read()
            .decode("utf-8")
        )

        return json.loads(
            conteudo
        )

    except ClientError as erro:

        codigo = (
            erro.response
            .get("Error", {})
            .get("Code")
        )

        if codigo in ["404", "NoSuchKey"]:

            return None

        raise


# ==================================================
# REMOVER CHECKPOINT
# ==================================================

def remover_checkpoint(temporada):

    caminho = (
        f"bronze/jolpica/voltas/"
        f"checkpoints/"
        f"{temporada}_checkpoint.json"
    )

    try:

        cliente_minio.delete_object(

            Bucket=BUCKET,

            Key=caminho
        )

        print(
            f"Checkpoint da temporada "
            f"{temporada} removido."
        )

    except ClientError:

        pass


# ==================================================
# FAZER REQUISIÇÃO
# ==================================================

def fazer_requisicao(
    url,
    params=None
):

    try:

        response = session.get(

            url,

            params=params,

            timeout=30
        )

        # ==========================================
        # RATE LIMIT
        # ==========================================

        if response.status_code == 429:

            print()
            print(
                "429 - Too Many Requests."
            )

            print(
                "A API está aplicando "
                "rate limit."
            )

            return None


        # ==========================================
        # OUTROS ERROS HTTP
        # ==========================================

        response.raise_for_status()


        # ==========================================
        # PAUSA ENTRE REQUISIÇÕES
        # ==========================================

        time.sleep(
            ESPERA_ENTRE_REQUISICOES
        )


        return response


    except requests.exceptions.RequestException as erro:

        print()
        print(
            f"Erro na requisição: "
            f"{erro}"
        )

        return None


# ==================================================
# PROCESSAR TEMPORADAS
# ==================================================

for temporada in range(
    ANO_INICIAL,
    ANO_FINAL + 1
):

    print()
    print("=" * 60)

    print(
        f"Processando voltas: "
        f"{temporada}"
    )

    print("=" * 60)


    # ==================================================
    # CAMINHO DO ARQUIVO FINAL
    # ==================================================

    caminho = (
        f"bronze/jolpica/voltas/"
        f"{temporada}/interlagos/"
        f"voltas.json"
    )


    try:

        # ==================================================
        # 1. VERIFICAR SE JÁ EXISTE
        # ==================================================

        if arquivo_existe_no_minio(
            caminho
        ):

            print(
                f"✓ Voltas {temporada} "
                f"já existem no MinIO."
            )

            print(
                "Temporada ignorada."
            )

            continue


        # ==================================================
        # 2. BUSCAR CALENDÁRIO
        # ==================================================

        url = (
            f"https://api.jolpi.ca/ergast/f1/"
            f"{temporada}/races/"
        )


        response = fazer_requisicao(
            url
        )


        if response is None:

            print(
                f"Não foi possível consultar "
                f"o calendário de {temporada}."
            )

            print(
                "Execução encerrada."
            )

            break


        corridas = (
            response.json()
            .get("MRData", {})
            .get("RaceTable", {})
            .get("Races", [])
        )


        # ==================================================
        # 3. ENCONTRAR INTERLAGOS
        # ==================================================

        interlagos = next(
            (
                corrida
                for corrida in corridas
                if corrida
                .get("Circuit", {})
                .get("circuitId")
                == CIRCUITO
            ),
            None
        )


        if interlagos is None:

            print(
                f"Interlagos não encontrado "
                f"em {temporada}."
            )

            continue


        round_interlagos = (
            interlagos["round"]
        )


        print(
            f"Interlagos encontrado - "
            f"Round {round_interlagos}"
        )


        # ==================================================
        # 4. BUSCAR RESULTADOS
        # ==================================================

        url = (
            f"https://api.jolpi.ca/ergast/f1/"
            f"{temporada}/"
            f"{round_interlagos}/"
            f"results/"
        )


        response = fazer_requisicao(
            url
        )


        if response is None:

            print(
                f"Não foi possível consultar "
                f"os resultados de {temporada}."
            )

            print(
                "Execução encerrada."
            )

            break


        races = (
            response.json()
            .get("MRData", {})
            .get("RaceTable", {})
            .get("Races", [])
        )


        if not races:

            print(
                "Corrida não encontrada."
            )

            continue


        corrida = races[0]


        resultados = corrida.get(
            "Results",
            []
        )


        if not resultados:

            print(
                "Resultados não encontrados."
            )

            continue


        # ==================================================
        # 5. DESCOBRIR TOTAL DE VOLTAS
        # ==================================================

        voltas_resultados = [

            int(resultado["laps"])

            for resultado in resultados

            if resultado.get("laps") is not None
        ]


        if not voltas_resultados:

            print(
                "Não foi possível descobrir "
                "o total de voltas."
            )

            continue


        total_voltas = max(
            voltas_resultados
        )


        print(
            f"Corrida: "
            f"{corrida['raceName']}"
        )


        print(
            f"Total de voltas: "
            f"{total_voltas}"
        )


        # ==================================================
        # 6. RECUPERAR CHECKPOINT
        # ==================================================

        checkpoint = ler_checkpoint(
            temporada
        )


        if checkpoint:

            offset = int(
                checkpoint[
                    "next_offset"
                ]
            )


            voltas_por_numero = {

                int(numero): dados

                for numero, dados
                in checkpoint["voltas"].items()
            }


            print()
            print(
                "Checkpoint encontrado."
            )


            print(
                f"Continuando a partir "
                f"do offset {offset}."
            )


            print(
                f"Voltas já coletadas: "
                f"{len(voltas_por_numero)}"
            )


        else:

            offset = 0

            voltas_por_numero = {}


        # ==================================================
        # 7. PAGINAÇÃO
        # ==================================================

        temporada_interrompida = False


        while True:

            print()
            print(
                f"Consultando página "
                f"offset={offset}..."
            )


            url = (
                f"https://api.jolpi.ca/ergast/f1/"
                f"{temporada}/"
                f"{round_interlagos}/"
                f"laps/"
            )


            params = {

                "limit": LIMIT,

                "offset": offset
            }


            response = fazer_requisicao(
                url,
                params=params
            )


            # ==================================================
            # FALHA / 429
            # ==================================================

            if response is None:

                print()

                print(
                    "Não foi possível continuar "
                    "a coleta."
                )


                salvar_checkpoint(

                    temporada,

                    offset,

                    voltas_por_numero
                )


                print()

                print(
                    "✓ Progresso salvo."
                )


                print(
                    "Execute novamente "
                    "quando a API estiver "
                    "disponível."
                )


                temporada_interrompida = True

                break


            # ==================================================
            # LER RESPOSTA
            # ==================================================

            mrdata = (
                response.json()
                .get("MRData", {})
            )


            races = (
                mrdata
                .get("RaceTable", {})
                .get("Races", [])
            )


            if not races:

                print(
                    "Nenhuma corrida "
                    "encontrada na página."
                )


                salvar_checkpoint(

                    temporada,

                    offset,

                    voltas_por_numero
                )


                temporada_interrompida = True

                break


            laps = races[0].get(
                "Laps",
                []
            )


            print(
                f"Objetos Laps recebidos: "
                f"{len(laps)}"
            )


            # ==================================================
            # AGRUPAR VOLTAS
            # ==================================================

            for lap in laps:

                numero = lap.get(
                    "number"
                )


                if numero is None:

                    continue


                numero = int(
                    numero
                )


                if numero not in voltas_por_numero:

                    voltas_por_numero[
                        numero
                    ] = {

                        "number": str(
                            numero
                        ),

                        "Timings": []
                    }


                voltas_por_numero[
                    numero
                ][
                    "Timings"
                ].extend(
                    lap.get(
                        "Timings",
                        []
                    )
                )


            print(
                f"Voltas únicas acumuladas: "
                f"{len(voltas_por_numero)}"
            )


            # ==================================================
            # VERIFICAR FIM DA PAGINAÇÃO
            # ==================================================

            total_registros = int(
                mrdata.get(
                    "total",
                    0
                )
            )


            offset_atual = int(
                mrdata.get(
                    "offset",
                    offset
                )
            )


            limite_atual = int(
                mrdata.get(
                    "limit",
                    LIMIT
                )
            )


            if (
                offset_atual
                + limite_atual
                >= total_registros
            ):

                print()
                print(
                    "Fim da paginação."
                )

                break


            # Próxima página

            offset = (
                offset_atual
                + limite_atual
            )


        # ==================================================
        # 8. SE A TEMPORADA FOI INTERROMPIDA
        # ==================================================

        if temporada_interrompida:

            print()

            print(
                f"Temporada {temporada} "
                f"não foi concluída."
            )


            print(
                "Execução encerrada."
            )


            break


        # ==================================================
        # 9. VALIDAR VOLTAS
        # ==================================================

        numeros_voltas = set(
            voltas_por_numero.keys()
        )


        voltas_esperadas = set(
            range(
                1,
                total_voltas + 1
            )
        )


        faltantes = (
            voltas_esperadas
            - numeros_voltas
        )


        print()

        print(
            f"Voltas esperadas: "
            f"{total_voltas}"
        )


        print(
            f"Voltas encontradas: "
            f"{len(numeros_voltas)}"
        )


        # ==================================================
        # 10. VERIFICAR VOLTAS FALTANTES
        # ==================================================

        if faltantes:

            print()

            print(
                "⚠ Existem voltas faltantes:"
            )


            print(
                sorted(faltantes)
            )


            salvar_checkpoint(

                temporada,

                offset,

                voltas_por_numero
            )


            print(
                "Checkpoint salvo."
            )


            continue


        # ==================================================
        # 11. VALIDAR QUANTIDADE
        # ==================================================

        if (
            len(numeros_voltas)
            != total_voltas
        ):

            print()

            print(
                "⚠ Quantidade de voltas "
                "incompatível."
            )


            salvar_checkpoint(

                temporada,

                offset,

                voltas_por_numero
            )


            continue


        # ==================================================
        # 12. ORGANIZAR VOLTAS
        # ==================================================

        todas_as_voltas = [

            voltas_por_numero[
                numero
            ]

            for numero
            in sorted(
                voltas_por_numero
            )
        ]


        # ==================================================
        # 13. MONTAR JSON
        # ==================================================

        dados_consolidados = {

            "season": temporada,

            "round": round_interlagos,

            "raceName": corrida[
                "raceName"
            ],

            "circuit": corrida[
                "Circuit"
            ],

            "date": corrida[
                "date"
            ],

            "time": corrida[
                "time"
            ],

            "totalLaps": total_voltas,

            "Laps": todas_as_voltas
        }


        # ==================================================
        # 14. CONVERTER PARA JSON
        # ==================================================

        conteudo = json.dumps(

            dados_consolidados,

            ensure_ascii=False,

            indent=2

        ).encode(
            "utf-8"
        )


        # ==================================================
        # 15. SALVAR NO MINIO
        # ==================================================

        cliente_minio.put_object(

            Bucket=BUCKET,

            Key=caminho,

            Body=BytesIO(
                conteudo
            ),

            ContentType="application/json"
        )


        print()

        print(
            f"✓ Voltas {temporada} "
            f"salvas no MinIO!"
        )


        print(
            f"Arquivo: {caminho}"
        )


        # ==================================================
        # 16. REMOVER CHECKPOINT
        # ==================================================

        remover_checkpoint(
            temporada
        )


        # ==================================================
        # 17. PAUSA ENTRE TEMPORADAS
        # ==================================================

        if temporada < ANO_FINAL:

            print()

            print(
                f"Aguardando "
                f"{ESPERA_ENTRE_TEMPORADAS} "
                f"segundos..."
            )


            time.sleep(
                ESPERA_ENTRE_TEMPORADAS
            )


    # ==================================================
    # CTRL + C
    # ==================================================

    except KeyboardInterrupt:

        print()

        print(
            "Execução interrompida "
            "manualmente."
        )


        print(
            "Execute novamente "
            "para continuar."
        )


        break


    # ==================================================
    # ERRO INESPERADO
    # ==================================================

    except Exception as erro:

        print()

        print(
            f"✗ Erro ao processar "
            f"{temporada}: {erro}"
        )


        print(
            "Execução encerrada."
        )


        break


# ==================================================
# FINAL
# ==================================================

print()

print("=" * 60)

print(
    "INGESTÃO DAS VOLTAS FINALIZADA!"
)

print("=" * 60)