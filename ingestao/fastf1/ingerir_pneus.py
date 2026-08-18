import json
from io import BytesIO
from pathlib import Path

import boto3
import fastf1


# ==================================================
# CONFIGURAÇÕES
# ==================================================

ANO_INICIAL = 2018
ANO_FINAL = 2025

GP = "São Paulo"
CIRCUITO = "interlagos"
SESSAO = "R"

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "minioadmin123"

BUCKET = "f1-data-lake"


# ==================================================
# CACHE DO FASTF1
# ==================================================

CACHE_DIR = Path("cache_fastf1")

CACHE_DIR.mkdir(
    parents=True,
    exist_ok=True
)

fastf1.Cache.enable_cache(
    CACHE_DIR
)


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
# FUNÇÃO PARA CONVERTER VALORES
# ==================================================

def converter_valor(valor):

    # Timedelta
    if hasattr(
        valor,
        "total_seconds"
    ):
        return valor.total_seconds()


    # Timestamp / datetime
    if hasattr(
        valor,
        "isoformat"
    ):
        return valor.isoformat()


    # Tipos NumPy
    if hasattr(
        valor,
        "item"
    ):
        return valor.item()


    return valor


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
        f"Processando pneus: "
        f"{temporada}"
    )

    print("=" * 60)


    # ==================================================
    # CAMINHO DO ARQUIVO
    # ==================================================

    caminho_arquivo = (
        f"bronze/fastf1/pneus/"
        f"{temporada}/interlagos/pneus.json"
    )


    try:

        # ==================================================
        # 1. VERIFICAR SE JÁ EXISTE
        # ==================================================

        try:

            cliente_minio.head_object(
                Bucket=BUCKET,
                Key=caminho_arquivo
            )

            print(
                f"✓ Pneus de {temporada} "
                "já existem no MinIO."
            )

            print(
                "Temporada ignorada."
            )

            continue


        except Exception:

            # Arquivo não existe.
            # Podemos continuar a coleta.

            pass


        # ==================================================
        # 2. CARREGAR SESSÃO
        # ==================================================

        print()

        print(
            f"Carregando GP de São Paulo "
            f"{temporada}..."
        )


        sessao = fastf1.get_session(
            temporada,
            GP,
            SESSAO
        )


        # ==================================================
        # 3. CARREGAR DADOS DA SESSÃO
        # ==================================================

        print(
            "Carregando dados da sessão..."
        )

        sessao.load()


        print(
            "Sessão carregada com sucesso!"
        )


        # ==================================================
        # 4. INFORMAÇÕES DA SESSÃO
        # ==================================================

        print()
        print("-" * 60)

        print(
            f"Nome: "
            f"{sessao.event.EventName}"
        )

        print(
            f"Circuito: "
            f"{sessao.event.Location}"
        )

        print(
            f"Data: "
            f"{sessao.event.EventDate}"
        )

        print(
            f"Sessão: "
            f"{sessao.name}"
        )


        # ==================================================
        # 5. EXTRAIR DADOS DAS VOLTAS
        # ==================================================

        print()
        print(
            "Extraindo dados de pneus..."
        )


        laps = sessao.laps


        # ==================================================
        # 6. VALIDAR DADOS
        # ==================================================

        print()
        print("-" * 60)

        print(
            "INFORMAÇÕES DOS PNEUS"
        )

        print("-" * 60)


        print(
            f"Quantidade total de "
            f"registros de voltas: "
            f"{len(laps)}"
        )


        print()

        print(
            "Colunas disponíveis:"
        )


        print(
            list(laps.columns)
        )


        # ==================================================
        # 7. DEFINIR COLUNAS DE PNEUS
        # ==================================================

        colunas_pneus = [

            "Driver",

            "DriverNumber",

            "LapNumber",

            "Stint",

            "Compound",

            "TyreLife",

            "FreshTyre"
        ]


        # ==================================================
        # 8. VERIFICAR COLUNAS EXISTENTES
        # ==================================================

        colunas_disponiveis = [

            coluna

            for coluna in colunas_pneus

            if coluna in laps.columns
        ]


        print()

        print(
            "Colunas de pneus encontradas:"
        )


        print(
            colunas_disponiveis
        )


        if not colunas_disponiveis:

            print(
                "✗ Nenhuma coluna de "
                "pneus encontrada."
            )

            continue


        # ==================================================
        # 9. SELECIONAR DADOS
        # ==================================================

        pneus = laps[
            colunas_disponiveis
        ].copy()


        # ==================================================
        # 10. REMOVER VOLTAS SEM NÚMERO
        # ==================================================

        if "LapNumber" in pneus.columns:

            pneus = pneus[
                pneus["LapNumber"].notna()
            ]


        # ==================================================
        # 11. CONVERTER NaN / NaT
        # ==================================================

        pneus = (

            pneus

            .astype(object)

            .where(
                pneus.notna(),
                None
            )
        )


        # ==================================================
        # 12. CONVERTER PARA LISTA DE REGISTROS
        # ==================================================

        registros_pneus = []


        for registro in pneus.to_dict(
            orient="records"
        ):

            registro_convertido = {}


            for coluna, valor in registro.items():

                registro_convertido[
                    coluna
                ] = converter_valor(
                    valor
                )


            registros_pneus.append(
                registro_convertido
            )


        # ==================================================
        # 13. VERIFICAR COMPOSTOS
        # ==================================================

        if "Compound" in pneus.columns:

            compostos = sorted(
                {

                    valor

                    for valor in pneus[
                        "Compound"
                    ]

                    if valor is not None
                }
            )

        else:

            compostos = []


        print()

        print(
            "Compostos encontrados:"
        )

        print(
            compostos
        )


        # ==================================================
        # 14. MOSTRAR PRIMEIROS REGISTROS
        # ==================================================

        print()
        print("-" * 60)

        print(
            "PRIMEIROS REGISTROS"
        )

        print("-" * 60)


        for registro in registros_pneus[:10]:

            print(
                json.dumps(
                    registro,
                    ensure_ascii=False,
                    indent=2
                )
            )


        # ==================================================
        # 15. MONTAR JSON
        # ==================================================

        dados_pneus = {

            "season": temporada,

            "grand_prix": GP,

            "circuit": "Interlagos",

            "session": SESSAO,

            "session_name": sessao.name,

            "event_name": (
                sessao.event.EventName
            ),

            "location": (
                sessao.event.Location
            ),

            "event_date": str(
                sessao.event.EventDate
            ),

            "lap_records": len(
                registros_pneus
            ),

            "compounds": compostos,

            "laps": registros_pneus
        }


        # ==================================================
        # 16. CONVERTER PARA JSON
        # ==================================================

        conteudo = json.dumps(

            dados_pneus,

            ensure_ascii=False,

            indent=2

        ).encode(
            "utf-8"
        )


        # ==================================================
        # 17. SALVAR NO MINIO
        # ==================================================

        cliente_minio.put_object(

            Bucket=BUCKET,

            Key=caminho_arquivo,

            Body=BytesIO(
                conteudo
            ),

            ContentType="application/json"
        )


        # ==================================================
        # 18. CONFIRMAÇÃO
        # ==================================================

        print()

        print(
            f"✓ Pneus {temporada} "
            "salvos no MinIO!"
        )

        print(
            f"Arquivo: "
            f"{caminho_arquivo}"
        )

        print(
            f"Registros: "
            f"{len(registros_pneus)}"
        )

        print(
            f"Compostos: "
            f"{compostos}"
        )


    # ==================================================
    # ERRO DA TEMPORADA
    # ==================================================

    except Exception as erro:

        print()

        print(
            f"✗ Erro ao processar "
            f"{temporada}:"
        )

        print(
            erro
        )

        print(
            f"Temporada {temporada} "
            "não será salva."
        )


# ==================================================
# FINAL
# ==================================================

print()
print("=" * 60)

print(
    "INGESTÃO DOS PNEUS CONCLUÍDA!"
)

print("=" * 60)