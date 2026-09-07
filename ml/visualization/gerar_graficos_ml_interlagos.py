"""
Geração dos gráficos da Etapa 3 — ML Interlagos.

Lê os resultados já persistidos no MinIO e gera gráficos PNG para uso no relatório/Word.

Entradas esperadas no MinIO:
- s3://f1-data-lake/ml/results/tuned_model_comparison.csv
- s3://f1-data-lake/ml/results/final_test_predictions.csv
- s3://f1-data-lake/ml/results/feature_importance.csv
- s3://f1-data-lake/ml/results/winners_vs_non_winners.csv

Saídas:
ml/visualization/outputs/
"""

from pathlib import Path
import os
import sys

import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import boto3


# ============================================================
# CONFIGURAÇÃO
# ============================================================

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "ml" / "visualization" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")

BUCKET = os.getenv("MINIO_BUCKET", "f1-data-lake")
VISUALIZATION_PREFIX = "ml/visualization"

RESULTS = {
    "model_comparison": f"s3://{BUCKET}/ml/results/tuned_model_comparison.csv",
    "final_predictions": f"s3://{BUCKET}/ml/results/final_test_predictions.csv",
    "feature_importance": f"s3://{BUCKET}/ml/results/feature_importance.csv",
    "winners": f"s3://{BUCKET}/ml/results/winners_vs_non_winners.csv",
}


# ============================================================
# DUCKDB / MINIO
# ============================================================

def create_connection():
    con = duckdb.connect()

    con.execute("INSTALL httpfs;")
    con.execute("LOAD httpfs;")

    con.execute(
        f"""
        SET s3_endpoint='{MINIO_ENDPOINT}';
        SET s3_access_key_id='{MINIO_ACCESS_KEY}';
        SET s3_secret_access_key='{MINIO_SECRET_KEY}';
        SET s3_use_ssl=false;
        SET s3_url_style='path';
        """
    )

    return con


def read_csv_from_minio(con, path):
    print(f"Lendo: {path}")

    try:
        df = con.execute(
            f"""
            SELECT *
            FROM read_csv_auto(
                '{path}',
                header=true,
                ignore_errors=false
            )
            """
        ).df()
    except Exception as exc:
        raise RuntimeError(
            f"Não foi possível ler o arquivo do MinIO:\n{path}\n\nErro: {exc}"
        ) from exc

    print(f"  -> {len(df)} linhas | {len(df.columns)} colunas")
    return df


# ============================================================
# UTILITÁRIOS
# ============================================================

def normalize_columns(df):
    """Normaliza apenas nomes de colunas para facilitar compatibilidade."""
    df = df.copy()
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]
    return df


def find_column(df, candidates, required=True):
    """Encontra uma coluna entre possíveis nomes/aliases."""
    columns = set(df.columns)

    for candidate in candidates:
        if candidate.lower() in columns:
            return candidate.lower()

    if required:
        raise ValueError(
            f"Nenhuma das colunas esperadas foi encontrada.\n"
            f"Esperadas: {candidates}\n"
            f"Disponíveis: {list(df.columns)}"
        )

    return None


def test_minio_connection(minio_client):
    """Testa autenticacao e acesso ao bucket antes de gerar os graficos."""
    try:
        minio_client.list_objects_v2(
            Bucket=BUCKET,
            Prefix=VISUALIZATION_PREFIX + "/",
            MaxKeys=1,
        )
        print(f"Conexao com MinIO validada: bucket '{BUCKET}'")
    except Exception as exc:
        raise RuntimeError(
            "Falha na conexao/autenticacao com o MinIO. "
            "Verifique endpoint, access key, secret key e bucket.\n"
            f"Erro: {exc}"
        ) from exc


def create_minio_client():
    """
    Cria o cliente S3 apontando para o MinIO.
    Usa as mesmas credenciais definidas acima.
    """
    return boto3.client(
        "s3",
        endpoint_url=f"http://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name="us-east-1",
    )


def save_figure(filename, minio_client):
    """
    Gera o PNG localmente apenas como etapa intermediária e
    imediatamente envia o arquivo para o MinIO.

    Destino:
    s3://<bucket>/ml/visualization/<filename>
    """
    path = OUTPUT_DIR / filename

    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()

    minio_key = f"{VISUALIZATION_PREFIX}/{filename}"

    try:
        minio_client.upload_file(
            str(path),
            BUCKET,
            minio_key,
            ExtraArgs={"ContentType": "image/png"},
        )

        print(f"Gráfico enviado ao MinIO: s3://{BUCKET}/{minio_key}")

    except Exception as exc:
        raise RuntimeError(
            f"Não foi possível enviar o gráfico para o MinIO: "
            f"s3://{BUCKET}/{minio_key}\n{exc}"
        ) from exc


def configure_plot():
    plt.rcParams.update(
        {
            "figure.figsize": (10, 6),
            "font.size": 11,
            "axes.titlesize": 15,
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
        }
    )


# ============================================================
# GRÁFICO 1 — COMPARAÇÃO DOS MODELOS
# ============================================================

def plot_model_comparison(df, minio_client):
    df = normalize_columns(df)

    model_col = find_column(
        df,
        ["modelo", "model", "classifier", "algoritmo"],
    )

    metric_candidates = {
        "F1": ["f1", "f1_score", "f1score"],
        "Recall": ["recall", "recall_score"],
        "Precision": ["precision", "precision_score"],
        "ROC-AUC": ["roc_auc", "roc_auc_score", "auc"],
    }

    available = {}
    for label, candidates in metric_candidates.items():
        col = find_column(df, candidates, required=False)
        if col:
            available[label] = col

    if not available:
        raise ValueError(
            "Nenhuma métrica encontrada em tuned_model_comparison.csv."
        )

    plot_df = df[[model_col] + list(available.values())].copy()

    rename_map = {model_col: "Modelo"}
    for label, col in available.items():
        rename_map[col] = label

    plot_df = plot_df.rename(columns=rename_map)

    for col in available:
        plot_df[col] = pd.to_numeric(plot_df[col], errors="coerce")

    plot_df = plot_df.dropna(subset=["Modelo"])

    ax = plot_df.set_index("Modelo").plot(
        kind="bar",
        figsize=(11, 6),
        width=0.78,
    )

    ax.set_title(
        "Comparação dos modelos após otimização",
        fontweight="bold",
    )
    ax.set_xlabel("Modelo")
    ax.set_ylabel("Métrica")
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(title="Métrica", loc="lower right")

    plt.xticks(rotation=0)
    save_figure("01_comparacao_modelos.png", minio_client)


# ============================================================
# PREPARAÇÃO DAS PREDIÇÕES FINAIS
# ============================================================

def prepare_final_predictions(df):
    df = normalize_columns(df)

    print("\nColunas encontradas em final_test_predictions.csv:")
    print(list(df.columns))

    y_true_col = find_column(
        df,
        [
            "y_true",
            "true",
            "target",
            "vitoria",
            "real",
            "actual",
        ],
    )

    prob_col = find_column(
        df,
        [
            "probabilidade_vitoria",
            "prob_vitoria",
            "probability",
            "probability_vitoria",
            "proba",
            "prob",
            "y_prob",
            "prob_1",
            "score",
        ],
    )

    pred_col = find_column(
        df,
        [
            "y_pred",
            "pred",
            "prediction",
            "vitoria_predita",
            "predicao",
            "predicted",
        ],
        required=False,
    )

    df[y_true_col] = (
        df[y_true_col]
        .astype(str)
        .str.lower()
        .map(
            {
                "true": 1,
                "false": 0,
                "1": 1,
                "0": 0,
                "yes": 1,
                "no": 0,
            }
        )
    )

    # Caso a coluna tenha vindo como numérica e o map acima não tenha resolvido.
    if df[y_true_col].isna().any():
        original = pd.to_numeric(
            df[y_true_col],
            errors="coerce",
        )
        df[y_true_col] = original

    df[prob_col] = pd.to_numeric(df[prob_col], errors="coerce")

    if pred_col:
        df[pred_col] = pd.to_numeric(df[pred_col], errors="coerce")

    df = df.dropna(subset=[y_true_col, prob_col]).copy()

    df[y_true_col] = df[y_true_col].astype(int)

    return df, y_true_col, prob_col, pred_col


# ============================================================
# GRÁFICO 2 — MATRIZ DE CONFUSÃO
# ============================================================

def plot_confusion_matrix(df, y_true_col, prob_col, pred_col, minio_client):
    y_true = df[y_true_col].astype(int)

    if pred_col:
        y_pred = df[pred_col].astype(int)
    else:
        # Reproduz exatamente o threshold padrão usado na avaliação:
        # vitória quando probabilidade >= 0.5.
        y_pred = (df[prob_col] >= 0.5).astype(int)

    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    tp = int(((y_true == 1) & (y_pred == 1)).sum())

    matrix = [[tn, fp], [fn, tp]]

    fig, ax = plt.subplots(figsize=(7, 6))

    image = ax.imshow(matrix)

    ax.set_title(
        "Matriz de confusão — conjunto de teste",
        fontweight="bold",
    )

    ax.set_xlabel("Classe prevista")
    ax.set_ylabel("Classe real")

    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Não vitória", "Vitória"])

    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Não vitória", "Vitória"])

    for i in range(2):
        for j in range(2):
            ax.text(
                j,
                i,
                str(matrix[i][j]),
                ha="center",
                va="center",
                fontsize=18,
                fontweight="bold",
            )

    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    save_figure("02_matriz_confusao.png", minio_client)


# ============================================================
# GRÁFICO 3 — CURVA ROC
# ============================================================

def plot_roc_curve(df, y_true_col, prob_col, minio_client):
    from sklearn.metrics import roc_curve, roc_auc_score

    y_true = df[y_true_col].astype(int)
    y_prob = df[prob_col].astype(float)

    fpr, tpr, _ = roc_curve(y_true, y_prob)
    auc = roc_auc_score(y_true, y_prob)

    fig, ax = plt.subplots(figsize=(8, 6))

    ax.plot(
        fpr,
        tpr,
        linewidth=2.5,
        label=f"Random Forest — ROC-AUC = {auc:.3f}",
    )

    ax.plot(
        [0, 1],
        [0, 1],
        linestyle="--",
        linewidth=1.5,
        label="Classificador aleatório",
    )

    ax.set_title(
        "Curva ROC — conjunto de teste",
        fontweight="bold",
    )
    ax.set_xlabel("Taxa de falsos positivos")
    ax.set_ylabel("Taxa de verdadeiros positivos")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.05)
    ax.grid(alpha=0.25)
    ax.legend(loc="lower right")

    save_figure("03_curva_roc.png", minio_client)


# ============================================================
# GRÁFICO 4 — IMPORTÂNCIA DAS FEATURES
# ============================================================

def plot_feature_importance(df, minio_client):
    df = normalize_columns(df)

    feature_col = find_column(
        df,
        ["feature", "variavel", "variable", "nome_feature"],
    )

    importance_col = find_column(
        df,
        [
            "importance",
            "importancia",
            "feature_importance",
            "importance_mean",
        ],
    )

    plot_df = df[[feature_col, importance_col]].copy()

    plot_df[importance_col] = pd.to_numeric(
        plot_df[importance_col],
        errors="coerce",
    )

    plot_df = (
        plot_df
        .dropna()
        .sort_values(importance_col, ascending=True)
    )

    fig_height = max(7, len(plot_df) * 0.35)

    fig, ax = plt.subplots(figsize=(11, fig_height))

    ax.barh(
        plot_df[feature_col],
        plot_df[importance_col],
    )

    ax.set_title(
        "Importância das variáveis — Random Forest",
        fontweight="bold",
    )
    ax.set_xlabel("Importância relativa")
    ax.set_ylabel("Variável")
    ax.grid(axis="x", alpha=0.25)

    for y, value in enumerate(plot_df[importance_col]):
        ax.text(
            value,
            y,
            f" {value:.1%}",
            va="center",
            fontsize=9,
        )

    save_figure("04_importancia_features.png", minio_client)


# ============================================================
# GRÁFICO 5 — RITMO: VENCEDORES VS NÃO VENCEDORES
# ============================================================

def plot_pace_winners(df, minio_client):
    df = normalize_columns(df)

    group_col = find_column(
        df,
        ["grupo", "classe", "target_group", "vitoria", "winner"],
    )

    pace_col = find_column(
        df,
        ["ritmo_representativo_pct"],
    )

    plot_df = df[[group_col, pace_col]].copy()

    plot_df[pace_col] = pd.to_numeric(
        plot_df[pace_col],
        errors="coerce",
    )

    plot_df = plot_df.dropna(subset=[pace_col])

    # Caso o arquivo use True/False para representar vitória.
    def normalize_group(value):
        value = str(value).strip().lower()

        if value in {"true", "1", "winner", "vencedor", "vitória", "vitoria"}:
            return "Vencedores"

        if value in {"false", "0", "non-winner", "não vencedor", "nao vencedor"}:
            return "Não vencedores"

        return str(value)

    plot_df["grupo_visual"] = plot_df[group_col].apply(normalize_group)

    summary = (
        plot_df
        .groupby("grupo_visual")[pace_col]
        .median()
        .sort_values()
    )

    fig, ax = plt.subplots(figsize=(8, 6))

    ax.bar(
        summary.index,
        summary.values,
    )

    ax.axhline(
        0,
        linestyle="--",
        linewidth=1.2,
    )

    ax.set_title(
        "Ritmo representativo — vencedores vs. não vencedores",
        fontweight="bold",
    )
    ax.set_xlabel("Grupo")
    ax.set_ylabel("Ritmo representativo (%)")
    ax.grid(axis="y", alpha=0.25)

    for i, value in enumerate(summary.values):
        ax.text(
            i,
            value,
            f" {value:.2f}%",
            ha="center",
            va="bottom" if value >= 0 else "top",
            fontweight="bold",
        )

    save_figure("05_ritmo_vencedores_vs_nao_vencedores.png", minio_client)


# ============================================================
# GRÁFICO 6 — GRID: VENCEDORES VS NÃO VENCEDORES
# ============================================================

def plot_grid_winners(df, minio_client):
    df = normalize_columns(df)

    group_col = find_column(
        df,
        ["grupo", "classe", "target_group", "vitoria", "winner"],
    )

    grid_col = find_column(
        df,
        ["grid"],
    )

    plot_df = df[[group_col, grid_col]].copy()

    plot_df[grid_col] = pd.to_numeric(
        plot_df[grid_col],
        errors="coerce",
    )

    plot_df = plot_df.dropna(subset=[grid_col])

    def normalize_group(value):
        value = str(value).strip().lower()

        if value in {"true", "1", "winner", "vencedor", "vitória", "vitoria"}:
            return "Vencedores"

        if value in {"false", "0", "non-winner", "não vencedor", "nao vencedor"}:
            return "Não vencedores"

        return str(value)

    plot_df["grupo_visual"] = plot_df[group_col].apply(normalize_group)

    summary = (
        plot_df
        .groupby("grupo_visual")[grid_col]
        .mean()
    )

    fig, ax = plt.subplots(figsize=(8, 6))

    ax.bar(
        summary.index,
        summary.values,
    )

    ax.set_title(
        "Posição no grid — vencedores vs. não vencedores",
        fontweight="bold",
    )
    ax.set_xlabel("Grupo")
    ax.set_ylabel("Posição média no grid")
    ax.invert_yaxis()
    ax.grid(axis="y", alpha=0.25)

    for i, value in enumerate(summary.values):
        ax.text(
            i,
            value,
            f" {value:.1f}",
            ha="center",
            va="bottom",
            fontweight="bold",
        )

    save_figure("06_grid_vencedores_vs_nao_vencedores.png", minio_client)


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)
    print("GERAÇÃO DOS GRÁFICOS — ETAPA 3 / ML INTERLAGOS")
    print("=" * 70)

    configure_plot()

    minio_client = create_minio_client()
    test_minio_connection(minio_client)

    con = create_connection()

    try:
        # --------------------------------------------------------
        # 1. Comparação dos modelos
        # --------------------------------------------------------
        try:
            df_models = read_csv_from_minio(
                con,
                RESULTS["model_comparison"],
            )
            plot_model_comparison(df_models, minio_client)
        except Exception as exc:
            print(f"\n[AVISO] Gráfico 1 não foi gerado: {exc}")

        # --------------------------------------------------------
        # 2 e 3. Avaliação final
        # --------------------------------------------------------
        try:
            df_predictions = read_csv_from_minio(
                con,
                RESULTS["final_predictions"],
            )

            (
                df_predictions,
                y_true_col,
                prob_col,
                pred_col,
            ) = prepare_final_predictions(df_predictions)

            print(
                f"\nColuna target: {y_true_col}"
                f"\nColuna probabilidade: {prob_col}"
                f"\nColuna previsão: {pred_col}"
            )

            plot_confusion_matrix(
                df_predictions,
                y_true_col,
                prob_col,
                pred_col,
                minio_client,
            )

            plot_roc_curve(
                df_predictions,
                y_true_col,
                prob_col,
                minio_client,
            )

        except Exception as exc:
            print(f"\n[AVISO] Gráficos 2/3 não foram gerados: {exc}")

        # --------------------------------------------------------
        # 4. Importância das features
        # --------------------------------------------------------
        try:
            df_importance = read_csv_from_minio(
                con,
                RESULTS["feature_importance"],
            )
            plot_feature_importance(df_importance, minio_client)

        except Exception as exc:
            print(
                f"\n[AVISO] Gráfico 4 não foi gerado: {exc}"
            )

        # --------------------------------------------------------
        # 5 e 6. Vencedores vs não vencedores
        # --------------------------------------------------------
        try:
            df_winners = read_csv_from_minio(
                con,
                RESULTS["winners"],
            )

            plot_pace_winners(df_winners, minio_client)
            plot_grid_winners(df_winners, minio_client)

        except Exception as exc:
            print(
                f"\n[AVISO] Gráficos 5/6 não foram gerados: {exc}"
            )

    finally:
        con.close()

    print("\n" + "=" * 70)
    print("PROCESSO CONCLUÍDO")
    print("=" * 70)
    print("\nOs gráficos foram exportados para o MinIO em:")
    print(f"s3://{BUCKET}/{VISUALIZATION_PREFIX}/")
    print(f"\nCópias locais intermediárias: {OUTPUT_DIR}")

    generated = sorted(OUTPUT_DIR.glob("*.png"))

    if generated:
        print("\nArquivos gerados:")
        for file in generated:
            print(f"  - {file.name}")
    else:
        print("\nNenhum gráfico foi gerado. Verifique os arquivos de entrada.")


if __name__ == "__main__":
    main()
