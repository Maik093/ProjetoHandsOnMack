"""
Comparações — Gabriel Bortoleto × vencedores históricos de Interlagos

Este script deve ser executado a partir da RAIZ do projeto, por exemplo:

    python teste_stints.py

Estrutura esperada:

    f1-data-engineering/
    ├── ml/
    │   ├── dataset/
    │   │   └── dataset_ml_interlagos.parquet
    │   └── eda/
    └── teste_stints.py

Saídas:

    ml/eda/outputs/comparacoes_gabriel/
        01_gabriel_vs_vencedores_ritmo.png
        02_gabriel_vs_vencedores_grid.png
        03_gabriel_vs_vencedor_2025.png
        04_gabriel_vs_perfil_vencedor.png
        tabela_comparacoes_gabriel.csv

IMPORTANTE:
- A análise é descritiva/retrospectiva.
- Não cria um novo modelo preditivo.
- Não cria probabilidade de vitória.
- Não estabelece causalidade.
- Menor grid = melhor posição de largada.
- No ritmo, valores mais negativos representam ritmo mais favorável,
  conforme a metodologia da EDA.
- Pit stops, stints e compostos são apresentados como contexto.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# 1. CAMINHOS
# ============================================================

# O script está sendo executado na RAIZ do projeto.
ROOT = Path(__file__).resolve().parent

DATASET = ROOT / "ml" / "dataset" / "dataset_ml_interlagos.parquet"

OUTPUT_DIR = (
    ROOT
    / "ml"
    / "eda"
    / "outputs"
    / "comparacoes_gabriel"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. CONFIGURAÇÕES
# ============================================================

NOME_GABRIEL = "Bortoleto"

METRICAS = [
    "grid",
    "ritmo_representativo_pct",
    "duracao_mediana_pit_convencional",
    "qtd_pit_stops",
    "qtd_stints",
    "qtd_compostos_distintos",
    "voltas_stint_medio",
]

# Métricas usadas na visão consolidada.
# São variáveis quantitativas com interpretação mais direta.
METRICAS_PERFIL = [
    "grid",
    "ritmo_representativo_pct",
    "duracao_mediana_pit_convencional",
    "voltas_stint_medio",
]

LABELS = {
    "grid": "Grid",
    "ritmo_representativo_pct": "Ritmo representativo (%)",
    "duracao_mediana_pit_convencional": (
        "Mediana pit stop convencional (s)"
    ),
    "qtd_pit_stops": "Quantidade de pit stops",
    "qtd_stints": "Quantidade de stints",
    "qtd_compostos_distintos": "Compostos distintos",
    "voltas_stint_medio": "Voltas médias por stint",
}


# ============================================================
# 3. FUNÇÕES
# ============================================================

def salvar_figura(nome):
    """
    Salva a figura em PNG com boa resolução para utilização no Word.
    """
    caminho = OUTPUT_DIR / nome

    plt.tight_layout()
    plt.savefig(
        caminho,
        dpi=200,
        bbox_inches="tight",
    )
    plt.close()

    print(f"  [OK] {caminho}")


def validar_dataset(df):
    """
    Verifica se as colunas necessárias existem.
    """
    obrigatorias = {
        "season",
        "round",
        "full_name",
        "vitoria",
        *METRICAS,
    }

    faltantes = sorted(
        obrigatorias - set(df.columns)
    )

    if faltantes:
        raise ValueError(
            "\nColunas obrigatórias ausentes:\n"
            + "\n".join(
                f"  - {col}" for col in faltantes
            )
        )


def mostrar_registros_gabriel(gabriel):
    """
    Exibe no terminal os registros encontrados.
    """
    colunas = [
        "season",
        "round",
        "full_name",
        "grid",
        "vitoria",
        "ritmo_representativo_pct",
        "duracao_mediana_pit_convencional",
        "qtd_pit_stops",
        "qtd_stints",
        "qtd_compostos_distintos",
        "voltas_stint_medio",
    ]

    colunas = [
        c for c in colunas
        if c in gabriel.columns
    ]

    print("\nREGISTROS DE GABRIEL BORTOLETO")
    print("-" * 70)

    print(
        gabriel[colunas]
        .sort_values(["season", "round"])
        .to_string(index=False)
    )


def criar_boxplot_com_gabriel(
    vencedores,
    gabriel,
    metric,
    titulo,
    xlabel,
    arquivo,
):
    """
    Cria boxplot dos vencedores históricos e marca
    todas as observações de Gabriel.
    """

    vencedores_validos = (
        vencedores[metric]
        .dropna()
        .astype(float)
    )

    gabriel_validos = (
        gabriel[metric]
        .dropna()
        .astype(float)
    )

    if vencedores_validos.empty:
        print(
            f"  [AVISO] Sem dados para {metric}."
        )
        return

    if gabriel_validos.empty:
        print(
            f"  [AVISO] Gabriel sem dados para {metric}."
        )
        return

    fig, ax = plt.subplots(
        figsize=(10, 5.5)
    )

    ax.boxplot(
        vencedores_validos,
        vert=False,
        widths=0.45,
        patch_artist=False,
    )

    # Gabriel recebe uma marca em cada observação.
    y_base = 1.12

    for i, valor in enumerate(
        gabriel_validos
    ):
        ax.scatter(
            valor,
            y_base + (i * 0.06),
            marker="D",
            s=65,
            zorder=3,
            label=(
                "Gabriel Bortoleto"
                if i == 0
                else None
            ),
        )

    mediana = vencedores_validos.median()

    ax.axvline(
        mediana,
        linestyle="--",
        linewidth=1,
        label=(
            f"Mediana vencedores: "
            f"{mediana:.2f}"
        ),
    )

    ax.set_yticks(
        [1, y_base]
    )

    ax.set_yticklabels(
        ["Vencedores históricos", "Gabriel"]
    )

    ax.set_xlabel(xlabel)

    ax.set_title(titulo)

    q1 = vencedores_validos.quantile(0.25)
    q3 = vencedores_validos.quantile(0.75)

    ax.text(
        0.01,
        0.02,
        (
            f"Perfil dos vencedores: "
            f"P25={q1:.2f} | "
            f"Mediana={mediana:.2f} | "
            f"P75={q3:.2f}"
        ),
        transform=ax.transAxes,
        fontsize=9,
    )

    ax.legend(
        loc="best"
    )

    salvar_figura(arquivo)


# ============================================================
# 4. VERIFICAÇÃO DO DATASET
# ============================================================

print("=" * 70)
print(
    "COMPARAÇÕES — GABRIEL BORTOLETO × VENCEDORES"
)
print("=" * 70)

print("\nProjeto:")
print(ROOT)

print("\nDataset esperado:")
print(DATASET)

if not DATASET.exists():

    print("\nERRO: o dataset não foi encontrado.")

    print(
        "\nVerifique se o arquivo existe em:"
    )

    print(
        ROOT
        / "ml"
        / "dataset"
        / "dataset_ml_interlagos.parquet"
    )

    print(
        "\nSe o Parquet estiver em outro local,"
        " altere somente a variável DATASET"
        " no início deste script."
    )

    raise FileNotFoundError(
        f"\nDataset não encontrado:\n{DATASET}"
    )


# ============================================================
# 5. LEITURA
# ============================================================

print("\nLendo dataset...")

df = pd.read_parquet(DATASET)

validar_dataset(df)

df["vitoria"] = (
    df["vitoria"]
    .astype(bool)
)

print(
    f"\nTotal de registros: {len(df)}"
)

print(
    f"Total de vencedores: "
    f"{int(df['vitoria'].sum())}"
)


# ============================================================
# 6. SELEÇÃO DO GABRIEL E VENCEDORES
# ============================================================

gabriel = df[
    df["full_name"]
    .astype(str)
    .str.contains(
        NOME_GABRIEL,
        case=False,
        na=False,
    )
].copy()

if gabriel.empty:
    raise ValueError(
        "\nGabriel Bortoleto não foi encontrado."
        "\n\nValores disponíveis em full_name:"
        f"\n{sorted(df['full_name'].dropna().unique())}"
    )

vencedores = df[
    df["vitoria"]
].copy()

mostrar_registros_gabriel(
    gabriel
)


# ============================================================
# 7. GRÁFICO 1 — RITMO
# ============================================================

print("\n[1/4] Gerando comparação de ritmo...")

criar_boxplot_com_gabriel(
    vencedores=vencedores,
    gabriel=gabriel,
    metric="ritmo_representativo_pct",
    titulo=(
        "Gabriel Bortoleto × vencedores históricos — ritmo"
    ),
    xlabel=(
        "Ritmo representativo (%)"
    ),
    arquivo=(
        "01_gabriel_vs_vencedores_ritmo.png"
    ),
)


# ============================================================
# 8. GRÁFICO 2 — GRID
# ============================================================

print("\n[2/4] Gerando comparação de grid...")

criar_boxplot_com_gabriel(
    vencedores=vencedores,
    gabriel=gabriel,
    metric="grid",
    titulo=(
        "Gabriel Bortoleto × vencedores históricos — grid"
    ),
    xlabel=(
        "Posição de largada — grid"
    ),
    arquivo=(
        "02_gabriel_vs_vencedores_grid.png"
    ),
)


# ============================================================
# 9. GRÁFICO 3 — GABRIEL × VENCEDOR DA MESMA CORRIDA
# ============================================================

print(
    "\n[3/4] Gerando comparação com o vencedor da mesma corrida..."
)

comparacoes = []

for _, linha_gabriel in gabriel.iterrows():

    mesma_corrida = vencedores[
        (vencedores["season"] == linha_gabriel["season"])
        & (
            vencedores["round"]
            == linha_gabriel["round"]
        )
    ]

    if mesma_corrida.empty:
        continue

    vencedor = mesma_corrida.iloc[0]

    for metric in METRICAS:

        valor_gabriel = linha_gabriel[
            metric
        ]

        valor_vencedor = vencedor[
            metric
        ]

        if pd.isna(
            valor_gabriel
        ) or pd.isna(
            valor_vencedor
        ):
            continue

        comparacoes.append(
            {
                "season": int(
                    linha_gabriel["season"]
                ),
                "round": int(
                    linha_gabriel["round"]
                ),
                "gabriel": linha_gabriel[
                    "full_name"
                ],
                "vencedor": vencedor[
                    "full_name"
                ],
                "metrica": metric,
                "gabriel_valor": float(
                    valor_gabriel
                ),
                "vencedor_valor": float(
                    valor_vencedor
                ),
            }
        )


comparacoes_df = pd.DataFrame(
    comparacoes
)

if comparacoes_df.empty:

    print(
        "  [AVISO] Não foi possível "
        "encontrar uma corrida de Gabriel "
        "com vencedor correspondente."
    )

else:

    caminho_tabela = (
        OUTPUT_DIR
        / "tabela_comparacoes_gabriel.csv"
    )

    comparacoes_df.to_csv(
        caminho_tabela,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"  [OK] {caminho_tabela}"
    )

    # --------------------------------------------------------
    # Criar uma figura para cada corrida de Gabriel
    # --------------------------------------------------------

    for (
        season,
        round_,
    ), grupo in comparacoes_df.groupby(
        ["season", "round"]
    ):

        # Para a visão gráfica consolidada,
        # utilizamos somente métricas com
        # interpretação direta de comparação.
        grupo = grupo[
            grupo["metrica"].isin(
                METRICAS_PERFIL
            )
        ].copy()

        if grupo.empty:
            continue

        # ----------------------------------------------------
        # Normalização apenas para visualização.
        #
        # Não é score de modelo.
        #
        # 100 representa o menor valor observado
        # na comparação daquela corrida.
        # ----------------------------------------------------

        valores = pd.concat(
            [
                grupo["gabriel_valor"],
                grupo["vencedor_valor"],
            ]
        )

        minimo = valores.min()
        maximo = valores.max()

        if maximo == minimo:

            grupo[
                "gabriel_visual"
            ] = 100

            grupo[
                "vencedor_visual"
            ] = 100

        else:

            grupo[
                "gabriel_visual"
            ] = (
                1
                - (
                    (
                        grupo[
                            "gabriel_valor"
                        ]
                        - minimo
                    )
                    / (
                        maximo
                        - minimo
                    )
                )
            ) * 100

            grupo[
                "vencedor_visual"
            ] = (
                1
                - (
                    (
                        grupo[
                            "vencedor_valor"
                        ]
                        - minimo
                    )
                    / (
                        maximo
                        - minimo
                    )
                )
            ) * 100

        x = np.arange(
            len(grupo)
        )

        largura = 0.36

        fig, ax = plt.subplots(
            figsize=(11, 6)
        )

        ax.bar(
            x - largura / 2,
            grupo[
                "gabriel_visual"
            ],
            largura,
            label="Gabriel Bortoleto",
        )

        ax.bar(
            x + largura / 2,
            grupo[
                "vencedor_visual"
            ],
            largura,
            label=(
                str(
                    grupo[
                        "vencedor"
                    ].iloc[0]
                )
            ),
        )

        ax.set_xticks(x)

        ax.set_xticklabels(
            [
                LABELS[m]
                for m in grupo[
                    "metrica"
                ]
            ],
            rotation=25,
            ha="right",
        )

        ax.set_ylabel(
            "Escala relativa para comparação visual"
        )

        ax.set_title(
            (
                f"Gabriel Bortoleto × vencedor — "
                f"Interlagos {season}"
            )
        )

        ax.legend()

        nome = (
            f"03_gabriel_vs_vencedor_"
            f"{season}.png"
        )

        salvar_figura(nome)


# ============================================================
# 10. GRÁFICO 4 — PERFIL HISTÓRICO
# ============================================================

print(
    "\n[4/4] Gerando perfil consolidado..."
)

perfil = []

for metric in METRICAS_PERFIL:

    base = (
        vencedores[metric]
        .dropna()
        .astype(float)
    )

    if base.empty:
        continue

    for _, linha in gabriel.iterrows():

        valor = linha[metric]

        if pd.isna(valor):
            continue

        # Para grid, ritmo, pit duration e
        # voltas_stint_medio, menor valor é
        # tratado como mais favorável para
        # esta comparação visual.
        #
        # Isso NÃO representa uma conclusão
        # causal nem um score do modelo.

        percentil = (
            (base >= float(valor)).mean()
            * 100
        )

        perfil.append(
            {
                "season": int(
                    linha["season"]
                ),
                "metrica": metric,
                "valor_gabriel": float(
                    valor
                ),
                "percentual_vencedores_igual_ou_superior":
                    percentil,
            }
        )


perfil_df = pd.DataFrame(
    perfil
)

if perfil_df.empty:

    print(
        "  [AVISO] Não foi possível "
        "gerar o perfil consolidado."
    )

else:

    fig, ax = plt.subplots(
        figsize=(11, 6)
    )

    x = np.arange(
        len(perfil_df)
    )

    ax.bar(
        x,
        perfil_df[
            "percentual_vencedores_igual_ou_superior"
        ],
    )

    labels = [
        (
            f"{int(row.season)}\n"
            f"{LABELS[row.metrica]}"
        )
        for row in perfil_df.itertuples()
    ]

    ax.set_xticks(x)

    ax.set_xticklabels(
        labels,
        rotation=35,
        ha="right",
    )

    ax.axhline(
        50,
        linestyle="--",
        linewidth=1,
        label=(
            "Referência central — 50%"
        ),
    )

    ax.set_ylim(
        0,
        100,
    )

    ax.set_ylabel(
        "Percentual de vencedores com valor igual ou superior"
    )

    ax.set_title(
        (
            "Gabriel Bortoleto × perfil "
            "histórico dos vencedores"
        )
    )

    ax.legend()

    salvar_figura(
        "04_gabriel_vs_perfil_vencedor.png"
    )


# ============================================================
# 11. RESUMO NUMÉRICO
# ============================================================

print(
    "\n" + "=" * 70
)

print(
    "RESUMO — GABRIEL × PERFIL DOS VENCEDORES"
)

print(
    "=" * 70
)

for metric in METRICAS_PERFIL:

    base = (
        vencedores[metric]
        .dropna()
    )

    gab = (
        gabriel[metric]
        .dropna()
    )

    if base.empty or gab.empty:
        continue

    print(
        f"\n{LABELS[metric]}"
    )

    print(
        f"  Vencedores — P25: "
        f"{base.quantile(.25):.3f}"
    )

    print(
        f"  Vencedores — Mediana: "
        f"{base.median():.3f}"
    )

    print(
        f"  Vencedores — P75: "
        f"{base.quantile(.75):.3f}"
    )

    print(
        f"  Gabriel — média: "
        f"{gab.mean():.3f}"
    )

    print(
        f"  Gabriel — mediana: "
        f"{gab.median():.3f}"
    )


# ============================================================
# 12. FINAL
# ============================================================

print(
    "\n" + "=" * 70
)

print(
    "COMPARAÇÕES CONCLUÍDAS"
)

print(
    "=" * 70
)

print(
    f"\nArquivos disponíveis em:"
)

print(
    OUTPUT_DIR
)

print(
    "\nInterpretação:"
)

print(
    "  - A análise é histórica e descritiva."
)

print(
    "  - Não representa previsão de vitória."
)

print(
    "  - Não representa probabilidade de vitória."
)

print(
    "  - As diferenças não devem ser interpretadas como causalidade."
)

print(
    "  - Os gráficos servem para comparar Gabriel "
    "com o perfil observado entre vencedores."
)
