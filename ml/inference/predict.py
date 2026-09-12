from pathlib import Path
import argparse
import json

import joblib
import pandas as pd


# ============================================================
# CAMINHOS PADRÃO
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MODEL_PATH = (
    ROOT
    / "ml"
    / "models"
    / "random_forest_interlagos.joblib"
)

DEFAULT_METADATA_PATH = (
    ROOT
    / "ml"
    / "models"
    / "random_forest_interlagos_metadata.json"
)


# ============================================================
# CARREGAMENTO DOS ARTEFATOS
# ============================================================

def carregar_artefatos(
    model_path=DEFAULT_MODEL_PATH,
    metadata_path=DEFAULT_METADATA_PATH,
):
    """
    Carrega o Pipeline treinado e os metadados do modelo.

    O arquivo .joblib contém a Pipeline completa:
    - imputação;
    - normalização;
    - encoding categórico;
    - Random Forest.

    A metadata contém informações de versão, features,
    limitações e métricas do modelo.
    """

    model_path = Path(model_path)
    metadata_path = Path(metadata_path)

    if not model_path.exists():
        raise FileNotFoundError(
            f"Modelo não encontrado: {model_path}"
        )

    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Metadata não encontrada: {metadata_path}"
        )

    modelo = joblib.load(model_path)

    with open(
        metadata_path,
        "r",
        encoding="utf-8",
    ) as file:
        metadata = json.load(file)

    return modelo, metadata


# ============================================================
# FEATURES ESPERADAS
# ============================================================

def obter_features_metadata(metadata):
    """
    Recupera as features diretamente da metadata.

    Isso evita manter uma lista duplicada de features
    dentro do pipeline de inferência.
    """

    numeric = metadata[
        "features"
    ][
        "numeric"
    ]

    categorical = metadata[
        "features"
    ][
        "categorical"
    ]

    return numeric + categorical


# ============================================================
# VALIDAÇÃO DE ENTRADA
# ============================================================

def validar_entrada_inferencia(
    df,
    metadata,
):
    """
    Valida os dados antes da aplicação do modelo.

    Verificações:
    - DataFrame não vazio;
    - todas as features esperadas presentes;
    - ausência explícita de variáveis proibidas por leakage.
    """

    if not isinstance(
        df,
        pd.DataFrame,
    ):
        raise TypeError(
            "A entrada deve ser um pandas DataFrame."
        )

    if df.empty:
        raise ValueError(
            "O DataFrame de inferência está vazio."
        )

    features = obter_features_metadata(
        metadata
    )

    missing_features = [
        feature
        for feature in features
        if feature not in df.columns
    ]

    if missing_features:
        raise ValueError(
            "Features ausentes para inferência: "
            + ", ".join(
                missing_features
            )
        )

    forbidden_features = {
        "position",
        "posicoes_ganhas",
        "points",
        "race_time",
        "laps",
        "status",
    }

    leakage_detected = sorted(
        forbidden_features.intersection(
            set(df.columns)
        )
    )

    if leakage_detected:
        raise ValueError(
            "Features proibidas por risco de leakage "
            "foram encontradas: "
            + ", ".join(
                leakage_detected
            )
        )

    return features


# ============================================================
# GERAÇÃO DE SCORE
# ============================================================

def prever_scores(
    df,
    modelo=None,
    metadata=None,
):
    """
    Aplica o modelo e gera o score de vitória.

    Importante:
    score_modelo_vitoria NÃO deve ser interpretado como
    probabilidade real calibrada de vitória.

    Ele representa o score produzido pelo classificador
    para a classe positiva.
    """

    if modelo is None or metadata is None:
        modelo, metadata = carregar_artefatos()

    features = validar_entrada_inferencia(
        df,
        metadata,
    )

    entrada_modelo = df[
        features
    ].copy()

    scores = modelo.predict_proba(
        entrada_modelo
    )[:, 1]

    resultado = df.copy()

    resultado[
        "score_modelo_vitoria"
    ] = scores

    return resultado


# ============================================================
# RANKING POR CORRIDA
# ============================================================

def ranquear_por_corrida(
    df,
    race_col="race_key",
    driver_col="full_name",
):
    """
    Ordena os pilotos pelo score do modelo dentro de cada corrida.

    Retorna:
    - rank_modelo;
    - eh_top1;
    - eh_top3.

    Em caso de empate de score, utiliza o nome do piloto
    como critério determinístico de desempate.
    """

    required_columns = {
        race_col,
        driver_col,
        "score_modelo_vitoria",
    }

    missing_columns = (
        required_columns
        - set(df.columns)
    )

    if missing_columns:
        raise ValueError(
            "Colunas ausentes para ranking: "
            + ", ".join(
                sorted(
                    missing_columns
                )
            )
        )

    resultado = df.copy()

    resultado = resultado.sort_values(
        by=[
            race_col,
            "score_modelo_vitoria",
            driver_col,
        ],
        ascending=[
            True,
            False,
            True,
        ],
    ).reset_index(
        drop=True
    )

    resultado[
        "rank_modelo"
    ] = (
        resultado
        .groupby(
            race_col,
            sort=False,
        )
        .cumcount()
        + 1
    )

    resultado[
        "eh_top1"
    ] = (
        resultado[
            "rank_modelo"
        ] == 1
    )

    resultado[
        "eh_top3"
    ] = (
        resultado[
            "rank_modelo"
        ] <= 3
    )

    return resultado


# ============================================================
# PIPELINE DE INFERÊNCIA
# ============================================================

def executar_inferencia(
    df,
    modelo=None,
    metadata=None,
):
    """
    Executa o fluxo completo de inferência:

    dados
      -> validação
      -> score
      -> ranking por corrida
    """

    resultado = prever_scores(
        df=df,
        modelo=modelo,
        metadata=metadata,
    )

    if (
        "race_key"
        in resultado.columns
        and
        "full_name"
        in resultado.columns
    ):
        resultado = ranquear_por_corrida(
            resultado
        )

    return resultado


# ============================================================
# LEITURA DE ARQUIVO
# ============================================================

def carregar_dados_entrada(
    input_path,
):
    """
    Carrega arquivo CSV ou Parquet para inferência.
    """

    input_path = Path(
        input_path
    )

    if not input_path.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {input_path}"
        )

    suffix = (
        input_path
        .suffix
        .lower()
    )

    if suffix == ".csv":
        return pd.read_csv(
            input_path
        )

    if suffix == ".parquet":
        return pd.read_parquet(
            input_path
        )

    raise ValueError(
        "Formato não suportado. "
        "Utilize CSV ou Parquet."
    )


# ============================================================
# SALVAR RESULTADO
# ============================================================

def salvar_resultado(
    df,
    output_path,
):
    """
    Salva o resultado da inferência em CSV.
    """

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        output_path,
        index=False,
        encoding="utf-8",
    )

    return output_path


# ============================================================
# CLI
# ============================================================

def main():
    """
    Permite executar inferência em modo batch pelo terminal.

    Exemplo:

    python ml/inference/predict.py \
        --input arquivo.csv \
        --output resultado.csv
    """

    parser = argparse.ArgumentParser(
        description=(
            "Pipeline de inferência "
            "do modelo de ML de Interlagos."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help=(
            "Arquivo CSV ou Parquet "
            "com os dados de entrada."
        ),
    )

    parser.add_argument(
        "--output",
        required=True,
        help=(
            "Caminho do CSV de saída."
        ),
    )

    args = parser.parse_args()

    modelo, metadata = carregar_artefatos()

    df = carregar_dados_entrada(
        args.input
    )

    resultado = executar_inferencia(
        df=df,
        modelo=modelo,
        metadata=metadata,
    )

    output_path = salvar_resultado(
        resultado,
        args.output,
    )

    print(
        "Inferência concluída com sucesso."
    )

    print(
        f"Registros processados: {len(resultado)}"
    )

    print(
        f"Resultado salvo em: {output_path}"
    )


if __name__ == "__main__":
    main()