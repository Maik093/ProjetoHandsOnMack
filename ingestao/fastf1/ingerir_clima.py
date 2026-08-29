import json
import unicodedata
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
SESSAO = "R"

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "minioadmin123"

BUCKET = "f1-data-lake"


# O GP do Brasil não ocorreu em 2020. A busca textual do FastF1 precisa ser
# confirmada pelos metadados retornados antes de salvar qualquer dado Bronze.
EVENTOS_INTERLAGOS = {
    2018: "Brazilian Grand Prix",
    2019: "Brazilian Grand Prix",
}


def normalizar_texto(valor):
    """Normaliza texto para comparações de metadados do evento."""
    if valor is None:
        return ""

    return " ".join(
        unicodedata.normalize("NFKD", str(valor))
        .encode("ascii", "ignore")
        .decode("ascii")
        .casefold()
        .split()
    )


def validar_evento_interlagos(temporada, evento):
    """Valida se o evento FastF1 é realmente o GP de Interlagos."""
    nome_evento = evento.EventName
    localizacao = evento.Location
    data_evento = evento.EventDate
    pais = evento.get("Country", None)

    nome_esperado = EVENTOS_INTERLAGOS.get(
        temporada,
        "São Paulo Grand Prix" if temporada >= 2021 else None
    )

    if nome_esperado is None:
        return False, "temporada sem GP de Interlagos no recorte atual"

    if normalizar_texto(nome_evento) != normalizar_texto(nome_esperado):
        return False, f"event_name inesperado: {nome_evento!r}"

    # FastF1 expõe a localização do circuito no metadado Location.
    if normalizar_texto(localizacao) != normalizar_texto("São Paulo"):
        return False, f"location/circuito FastF1 inesperado: {localizacao!r}"

    if pais is not None and normalizar_texto(pais) != normalizar_texto("Brazil"):
        return False, f"país FastF1 inesperado: {pais!r}"

    if data_evento is None or str(data_evento)[:4] != str(temporada):
        return False, f"event_date incompatível: {data_evento!r}"

    return True, None


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
# PROCESSAR TEMPORADAS
# ==================================================

for temporada in range(
    ANO_INICIAL,
    ANO_FINAL + 1
):

    print()
    print("=" * 60)
    print(
        f"Processando clima: {temporada}"
    )
    print("=" * 60)

    try:

        # ==================================================
        # CAMINHO DO ARQUIVO NO MINIO
        # ==================================================

        caminho_arquivo = (
            f"bronze/fastf1/clima/"
            f"{temporada}/interlagos/clima.json"
        )


        # ==================================================
        # 1. CARREGAR SESSÃO
        # ==================================================

        print()
        print(
            f"Carregando sessão "
            f"{GP} - {SESSAO}..."
        )

        sessao = fastf1.get_session(
            temporada,
            GP,
            SESSAO
        )


        # ==================================================
        # 2. CARREGAR DADOS
        # ==================================================

        print(
            "Carregando dados da sessão..."
        )

        sessao.load()

        print(
            "Sessão carregada com sucesso!"
        )


        # ==================================================
        # 2.1 VALIDAR EVENTO RETORNADO PELO FASTF1
        # ==================================================

        evento_valido, motivo_evento_invalido = (
            validar_evento_interlagos(
                temporada,
                sessao.event
            )
        )

        if not evento_valido:

            print(
                "⚠ Sessão rejeitada: não pertence ao GP de Interlagos."
            )

            print(f"  season: {temporada}")
            print(f"  event_name: {sessao.event.EventName}")
            print(f"  location: {sessao.event.Location}")
            print(f"  event_date: {sessao.event.EventDate}")
            print(f"  motivo: {motivo_evento_invalido}")
            print("  Nenhum objeto Bronze será persistido.")

            continue


        # ==================================================
        # 3. INFORMAÇÕES DA SESSÃO
        # ==================================================

        print()
        print("-" * 60)
        print("INFORMAÇÕES DA SESSÃO")
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
        # 4. PEGAR DADOS DE CLIMA
        # ==================================================

        print()
        print(
            "Extraindo dados de clima..."
        )

        weather = sessao.weather_data


        # ==================================================
        # 5. VALIDAR DADOS
        # ==================================================

        print()
        print("-" * 60)
        print("INFORMAÇÕES DO CLIMA")
        print("-" * 60)

        print(
            f"Quantidade de registros: "
            f"{len(weather)}"
        )

        print(
            "Colunas disponíveis:"
        )

        print(
            list(weather.columns)
        )


        if weather.empty:

            print(
                f"⚠ Nenhum dado de clima "
                f"encontrado para {temporada}."
            )

            continue


        # ==================================================
        # 6. CONVERTER DADOS PARA JSON
        # ==================================================

        weather_json = weather.copy()


        # Converter NaN / NaT para None

        weather_json = (
            weather_json
            .astype(object)
            .where(
                weather_json.notna(),
                None
            )
        )


        registros_clima = []


        for registro in weather_json.to_dict(
            orient="records"
        ):

            registro_convertido = {}


            for coluna, valor in registro.items():

                # ------------------------------------------
                # None
                # ------------------------------------------

                if valor is None:

                    registro_convertido[
                        coluna
                    ] = None


                # ------------------------------------------
                # Timedelta
                # ------------------------------------------

                elif hasattr(
                    valor,
                    "total_seconds"
                ):

                    registro_convertido[
                        coluna
                    ] = valor.total_seconds()


                # ------------------------------------------
                # Timestamp / datetime
                # ------------------------------------------

                elif hasattr(
                    valor,
                    "isoformat"
                ):

                    registro_convertido[
                        coluna
                    ] = valor.isoformat()


                # ------------------------------------------
                # Tipos NumPy
                # ------------------------------------------

                elif hasattr(
                    valor,
                    "item"
                ):

                    registro_convertido[
                        coluna
                    ] = valor.item()


                # ------------------------------------------
                # Valores normais
                # ------------------------------------------

                else:

                    registro_convertido[
                        coluna
                    ] = valor


            registros_clima.append(
                registro_convertido
            )


        # ==================================================
        # 7. MONTAR JSON CONSOLIDADO
        # ==================================================

        dados_clima = {

            "season": temporada,

            "grand_prix": sessao.event.EventName,

            "circuit": "Interlagos",

            "session": SESSAO,

            "session_name": sessao.name,

            "event_name": sessao.event.EventName,

            "location": sessao.event.Location,

            "event_date": str(
                sessao.event.EventDate
            ),

            "weather_records": len(
                registros_clima
            ),

            "weather": registros_clima
        }


        # ==================================================
        # 8. CONVERTER PARA JSON
        # ==================================================

        conteudo = json.dumps(

            dados_clima,

            ensure_ascii=False,

            indent=2

        ).encode(
            "utf-8"
        )


        # ==================================================
        # 9. SALVAR NO MINIO
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
        # 10. CONFIRMAÇÃO
        # ==================================================

        print()
        print(
            f"✓ Clima {temporada} "
            f"salvo no MinIO!"
        )

        print(
            f"Arquivo: "
            f"{caminho_arquivo}"
        )

        print(
            f"Registros: "
            f"{len(registros_clima)}"
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
            f"não será salva."
        )

        continue


# ==================================================
# FINAL
# ==================================================

print()
print("=" * 60)
print(
    "INGESTÃO DO CLIMA CONCLUÍDA!"
)
print("=" * 60)
