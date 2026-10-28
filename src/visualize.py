"""
Visualizações da análise comercial. Cada gráfico responde a uma pergunta de negócio;
paleta categórica com ordem fixa, escala sequencial azul e divergente azul-vermelho
com meio cinza (atingimento acima/abaixo de 100%).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from src.config import ANO_ANALISE, ANO_BASE, CHARTS_DIR, ROOT_DIR  # noqa: E402
from src.utils import configurar_logger, formatar_br  # noqa: E402

log = configurar_logger("visualize")

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
CINZA, CINZA_ESCURO = "#b5b3ab", "#52514e"
TINTA, TINTA_2, TINTA_3 = "#0b0b0b", "#52514e", "#898781"
GRADE, EIXO, SUPERFICIE = "#e1e0d9", "#c3c2b7", "#fcfcfb"
POSITIVO, NEGATIVO = "#2a78d6", "#e34948"
RAMPA_AZUL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
DIVERGENTE = ["#c03636", "#e66767", "#f2b3b3", "#f0efec", "#9ec5f4", "#3987e5", "#184f95"]
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

plt.rcParams.update({
    "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE, "savefig.facecolor": SUPERFICIE,
    "axes.edgecolor": EIXO, "axes.labelcolor": TINTA_2, "axes.titlecolor": TINTA,
    "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlepad": 24,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRADE, "grid.linewidth": 0.6,
    "xtick.color": TINTA_3, "ytick.color": TINTA_3, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "text.color": TINTA, "legend.frameon": False, "legend.fontsize": 9, "font.family": "sans-serif",
})


def _mi(v, _=None) -> str:
    return f"R$ {v / 1e6:,.1f} mi".replace(".", ",")


def _subtitulo(ax, texto: str) -> None:
    ax.text(0, 1.02, texto.replace("$", r"\$"), transform=ax.transAxes, fontsize=9, color=TINTA_2, va="bottom")


def _salvar(fig, nome: str) -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / nome, dpi=150)
    plt.close(fig)


def _waterfall(ax, rotulos: list[str], valores: list[float], total_inicial: bool = True) -> None:
    """Barras flutuantes: início e fim cheios, etapas intermediárias partindo do acumulado."""
    acumulado, bases, alturas, cores = 0.0, [], [], []
    for i, valor in enumerate(valores):
        extremidade = total_inicial and i in (0, len(valores) - 1)
        if extremidade:
            bases.append(0.0)
            alturas.append(valor)
            cores.append(CINZA_ESCURO)
            acumulado = valor
        else:
            bases.append(acumulado if valor >= 0 else acumulado + valor)
            alturas.append(abs(valor))
            cores.append(POSITIVO if valor >= 0 else NEGATIVO)
            acumulado += valor
    barras = ax.bar(rotulos, alturas, bottom=bases, color=cores, width=0.6, zorder=2)
    for i, (barra, valor) in enumerate(zip(barras, valores)):
        extremidade = total_inicial and i in (0, len(valores) - 1)
        sinal = "" if extremidade else ("+" if valor >= 0 else "−")
        ax.text(barra.get_x() + barra.get_width() / 2, barra.get_y() + barra.get_height(),
                (sinal + _mi(abs(valor))).replace("$", r"\$"), ha="center", va="bottom", fontsize=8.5, color=TINTA_2)
    ax.yaxis.set_major_formatter(FuncFormatter(_mi))


# --------------------------------------------------------------------------- #
def grafico_yoy(yoy: pd.DataFrame) -> None:
    x = np.arange(12)
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.bar(x - 0.2, yoy[f"receita_{ANO_BASE}"], width=0.38, color=CINZA, label=str(ANO_BASE), zorder=2)
    ax.bar(x + 0.2, yoy[f"receita_{ANO_ANALISE}"], width=0.38, color=SERIES[0], label=str(ANO_ANALISE), zorder=2)
    for xi, (valor, var) in enumerate(zip(yoy[f"receita_{ANO_ANALISE}"], yoy["var_receita_pct"])):
        ax.text(xi + 0.2, valor, f"{var:+.0f}%", ha="center", va="bottom", fontsize=8, color=TINTA_2)
    ax.set_xticks(x, MESES)
    ax.yaxis.set_major_formatter(FuncFormatter(_mi))
    ax.set_title(f"Receita líquida mensal: {ANO_ANALISE} x {ANO_BASE}")
    _subtitulo(ax, "Rótulo: variação sobre o mesmo mês do ano anterior")
    ax.legend(loc="upper left", ncol=2)
    _salvar(fig, "01_receita_mensal_yoy.png")


def grafico_atingimento(resumo: pd.DataFrame) -> None:
    dados = resumo.sort_values("atingimento")
    fig, ax = plt.subplots(figsize=(9, 6))
    cores = [POSITIVO if a >= 1 else NEGATIVO for a in dados["atingimento"]]
    rotulos = [f"{n} ({v})" for n, v in zip(dados["nome"], dados["vendedor_id"])]
    barras = ax.barh(rotulos, dados["atingimento"] * 100, color=cores, height=0.65, zorder=2)
    for barra, (ating, comissao) in zip(barras, zip(dados["atingimento"], dados["comissao"])):
        ax.text(barra.get_width(), barra.get_y() + barra.get_height() / 2,
                f"  {ating * 100:.0f}% · comissão R$ {formatar_br(comissao / 1000, 0)} mil".replace("$", r"\$"),
                va="center", fontsize=8, color=TINTA_2)
    ax.axvline(100, color=TINTA_2, linewidth=1, linestyle="--")
    ax.set_xlim(0, dados["atingimento"].max() * 100 * 1.35)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_title(f"Atingimento da meta anual por vendedor ({ANO_ANALISE})")
    _subtitulo(ax, "Azul: bateu a meta · vermelho: abaixo · V07 e V17 têm meta de 6 meses (troca de vendedor)")
    _salvar(fig, "02_atingimento_vendedores.png")


def grafico_ponte(ponte: pd.DataFrame) -> None:
    rotulos = [e.replace("Variação na base comum", "Base comum\n(like-for-like)").replace("Clientes ", "Clientes\n")
               for e in ponte["etapa"]]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    _waterfall(ax, rotulos, ponte["valor"].tolist())
    ax.set_title(f"Ponte de receita {ANO_BASE} → {ANO_ANALISE} por clientes")
    n = ponte.set_index("etapa")["clientes"]
    _subtitulo(ax, f"{int(n.iloc[1])} clientes perdidos · {int(n.iloc[2])} na base comum · {int(n.iloc[3])} novos")
    _salvar(fig, "03_ponte_clientes.png")


def grafico_pvm(pvm: pd.DataFrame) -> None:
    total = pvm.set_index("categoria").loc["Total"]
    etapas = [(f"Receita\n{ANO_BASE}", total["receita_base"]), ("Volume", total["volume"]), ("Mix", total["mix"]),
              ("Reajuste\nde tabela", total["preco_tabela"]), ("Desconto", total["preco_desconto"]),
              ("Lançamentos", total["lancamentos"])]
    if abs(total["descontinuados"]) > 0.5:
        etapas.append(("Descontinuados", total["descontinuados"]))
    etapas.append((f"Receita\n{ANO_ANALISE}", total["receita_atual"]))
    fig, ax = plt.subplots(figsize=(10, 4.6))
    _waterfall(ax, [e for e, _ in etapas], [v for _, v in etapas])
    ax.set_ylim(total["receita_base"] * 0.85, total["receita_atual"] * 1.06)
    ax.set_title("De onde veio o crescimento: preço, volume e mix")
    _subtitulo(ax, "Eixo começa em 85% da receita do ano-base para mostrar as etapas")
    _salvar(fig, "04_preco_volume_mix.png")


def grafico_rfm(segmentos: pd.DataFrame) -> None:
    dados = segmentos.iloc[::-1]
    y = np.arange(len(dados))
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.barh(y + 0.19, dados["pct_receita"], height=0.36, color=SERIES[0], label="% da receita", zorder=2)
    ax.barh(y - 0.19, dados["pct_clientes"], height=0.36, color=SERIES[1], label="% dos clientes", zorder=2)
    ax.set_yticks(y, dados["segmento_rfm"])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_title("Segmentos RFM: participação em clientes e em receita")
    _subtitulo(ax, "Últimos 12 meses até 31/12")
    ax.legend(loc="lower right")
    _salvar(fig, "05_rfm_segmentos.png")


def grafico_coortes(retencao: pd.DataFrame) -> None:
    matriz = retencao.set_index("coorte").drop(columns="clientes").loc[:, :12]  # matriz completa fica no CSV
    fig, ax = plt.subplots(figsize=(11, 6.5))
    mapa = LinearSegmentedColormap.from_list("azul", RAMPA_AZUL)
    mapa.set_bad(SUPERFICIE)
    ax.imshow(np.ma.masked_invalid(matriz.to_numpy(dtype=float)), aspect="auto", cmap=mapa, vmin=0.4, vmax=1.0)
    for (i, j), valor in np.ndenumerate(matriz.to_numpy(dtype=float)):
        if not np.isnan(valor):
            ax.text(j, i, f"{valor * 100:.0f}", ha="center", va="center", fontsize=6.5,
                    color="white" if valor >= 0.75 else TINTA_2)
    ax.set_xticks(range(matriz.shape[1]), [str(c) for c in matriz.columns])
    ax.set_yticks(range(len(matriz)), [f"{c} (n={int(n)})" for c, n in zip(matriz.index, retencao["clientes"])])
    ax.set_xlabel("Meses desde a primeira compra")
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("Retenção por coorte de clientes novos (% que comprou no mês)")
    _subtitulo(ax, f"Só clientes cadastrados a partir de jan/{ANO_BASE} · primeiros 12 meses de cada coorte")
    _salvar(fig, "06_coortes_retencao.png")


def grafico_matriz_regional(matriz: pd.DataFrame) -> None:
    tabela = matriz.set_index("regional")
    fig, ax = plt.subplots(figsize=(9, 4.2))
    norma = TwoSlopeNorm(vmin=0.8, vcenter=1.0, vmax=1.2)
    ax.imshow(tabela.to_numpy(dtype=float), aspect="auto", cmap=LinearSegmentedColormap.from_list("div", DIVERGENTE),
              norm=norma)
    for (i, j), valor in np.ndenumerate(tabela.to_numpy(dtype=float)):
        ax.text(j, i, f"{valor * 100:.0f}%", ha="center", va="center", fontsize=9,
                color="white" if abs(valor - 1) > 0.12 else TINTA, fontweight="bold" if tabela.index[i] == "Total" else None)
    ax.set_xticks(range(tabela.shape[1]), tabela.columns)
    ax.set_yticks(range(len(tabela)), tabela.index)
    ax.tick_params(length=0)
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("Atingimento da meta anual: regional x categoria")
    _subtitulo(ax, "Azul: acima de 100% · vermelho: abaixo · cinza: perto da meta")
    _salvar(fig, "07_matriz_regional_categoria.png")


def grafico_pareto(pareto: pd.DataFrame, resumo: dict) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.plot(pareto["pct_clientes"], pareto["pct_acumulado"], color=SERIES[0], linewidth=2)
    corte = resumo["pct_clientes_para_80pct_receita"]
    ax.axhline(80, color=CINZA, linewidth=1, linestyle="--")
    ax.axvline(corte, color=CINZA, linewidth=1, linestyle="--")
    ax.annotate(f"{formatar_br(corte, 1)}% dos clientes\nfazem 80% da receita", (corte, 80), xytext=(12, -40),
                textcoords="offset points", fontsize=9, color=TINTA_2)
    for eixo in (ax.xaxis, ax.yaxis):
        eixo.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_xlabel("% dos clientes (do maior para o menor)")
    ax.set_ylim(0, 102)
    ax.set_xlim(0, 100)
    ax.set_title(f"Concentração da receita por cliente ({ANO_ANALISE})")
    _salvar(fig, "08_pareto_clientes.png")


def gerar_graficos(res: dict) -> None:
    cresc, cli, desemp = res["crescimento"], res["clientes"], res["desempenho"]
    grafico_yoy(cresc["yoy_mensal"])
    grafico_atingimento(desemp["resumo_vendedores"])
    grafico_ponte(cresc["ponte_clientes"])
    grafico_pvm(cresc["preco_volume_mix"])
    grafico_rfm(cli["rfm_segmentos"])
    grafico_coortes(cli["coortes_retencao"])
    grafico_matriz_regional(desemp["atingimento_regional_categoria"])
    grafico_pareto(cli["pareto_clientes"], cli["pareto_resumo"])
    log.info("8 gráficos salvos em %s", CHARTS_DIR.relative_to(ROOT_DIR))
