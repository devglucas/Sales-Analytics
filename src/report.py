"""Tabelas do relatório e relatório em Markdown (output/relatorio.md)."""

from __future__ import annotations

import pandas as pd

from src.config import ANO_ANALISE, ANO_BASE, OUTPUT_DIR
from src.utils import configurar_logger, df_para_markdown, formatar_br

log = configurar_logger("report")


def _mi(valor: float) -> str:
    return f"R$ {formatar_br(valor / 1e6)} mi"


def indicadores(res: dict) -> pd.DataFrame:
    fato = res["fato"][res["fato"]["tipo"] != "BONIFICACAO"]
    por_ano = fato.groupby("ano").agg(receita=("receita_liquida", "sum"), caixas=("caixas", "sum"),
                                      notas=("nf", "nunique"), clientes=("cliente_id", "nunique"))
    base, atual = por_ano.loc[ANO_BASE], por_ano.loc[ANO_ANALISE]
    mensal = res["desempenho"]["metas_x_realizado_mensal"]
    ponte = res["crescimento"]["ponte_clientes"]
    bonificado = res["fato"].loc[res["fato"]["ano"] == ANO_ANALISE]
    linhas = [
        (f"Receita líquida {ANO_BASE}", _mi(base["receita"])),
        (f"Receita líquida {ANO_ANALISE}", f"{_mi(atual['receita'])} ({formatar_br((atual['receita'] / base['receita'] - 1) * 100, 1)}%)"),
        (f"Caixas vendidas {ANO_ANALISE}", f"{formatar_br(int(atual['caixas']))} ({formatar_br((atual['caixas'] / base['caixas'] - 1) * 100, 1)}%)"),
        ("Crescimento like-for-like (base comum de clientes)", f"{formatar_br(float(ponte['like_for_like_pct'].dropna().iat[0]), 1)}%"),
        (f"Ticket médio por nota {ANO_ANALISE}", f"R$ {formatar_br(atual['receita'] / atual['notas'])}"),
        (f"Clientes com compra em {ANO_ANALISE}", formatar_br(int(atual["clientes"]))),
        (f"Meta {ANO_ANALISE}", _mi(mensal["meta"].sum())),
        ("Atingimento da meta", f"{formatar_br(mensal['realizado'].sum() / mensal['meta'].sum() * 100, 1)}%"),
        ("Comissões apuradas", f"R$ {formatar_br(mensal['comissao'].sum())}"),
        ("Caixas bonificadas", formatar_br(int(bonificado["caixas_bonificadas"].sum()))),
        ("Clientes que fazem 80% da receita", f"{formatar_br(res['clientes']['pareto_resumo']['pct_clientes_para_80pct_receita'], 1)}%"),
    ]
    return pd.DataFrame(linhas, columns=["Indicador", "Valor"])


def tabelas_relatorio(res: dict) -> dict[str, pd.DataFrame]:
    desemp, cresc, cli = res["desempenho"], res["crescimento"], res["clientes"]
    positivacao = desemp["positivacao"].pivot_table(index="vendedor_id", columns=desemp["positivacao"]["mes"].dt.month,
                                                    values="positivacao").round(3).rename_axis(columns="mes").reset_index()
    metas = desemp["metas_x_realizado_mensal"].assign(mes=lambda d: d["mes"].astype(str))
    return {
        "indicadores": indicadores(res),
        "resumo_vendedores": desemp["resumo_vendedores"],
        "metas_x_realizado_mensal": metas,
        "metas_regionais_x_realizado": desemp["metas_regionais_x_realizado"],
        "atingimento_regional_categoria": desemp["atingimento_regional_categoria"],
        "positivacao_vendedor_mes": positivacao,
        "produtividade_dia_util": desemp["produtividade_dia_util"],
        **{nome: cresc[nome] for nome in ["yoy_mensal", "yoy_categoria", "yoy_regional", "yoy_segmento", "mix_canal",
                                          "ponte_clientes", "preco_volume_mix"]},
        "rfm_segmentos": cli["rfm_segmentos"],
        "clientes_em_risco": cli["rfm_clientes"].query("segmento_rfm == 'Em risco'").sort_values("valor", ascending=False),
        "coortes_retencao": cli["coortes_retencao"],
        "curva_retencao": cli["curva_retencao"],
        "pareto_clientes": cli["pareto_clientes"],
        "controle_metas": res["controle_metas"],
        "validacoes": res["validacoes"],
    }


def gerar_relatorio(res: dict, tabelas: dict) -> None:
    vendedores = tabelas["resumo_vendedores"][["vendedor_id", "nome", "regional", "meta", "realizado", "atingimento",
                                               "meses_meta_batida", "comissao", "desconto_medio", "ranking_regional"]]
    partes = [
        f"# Análise comercial {ANO_ANALISE}\n", "_Gerado automaticamente por `python main.py`._\n",
        "## 1. Indicadores\n", df_para_markdown(tabelas["indicadores"]) + "\n",
        "## 2. Metas x realizado\n", "![Atingimento](charts/02_atingimento_vendedores.png)\n",
        df_para_markdown(vendedores, casas=3) + "\n",
        "### Atingimento por regional x categoria\n", "![Matriz](charts/07_matriz_regional_categoria.png)\n",
        df_para_markdown(tabelas["atingimento_regional_categoria"], casas=3) + "\n",
        "### Positivação da carteira (vendedor x mês)\n", df_para_markdown(tabelas["positivacao_vendedor_mes"], casas=3) + "\n",
        f"## 3. Crescimento {ANO_ANALISE} x {ANO_BASE}\n", "![YoY](charts/01_receita_mensal_yoy.png)\n",
        df_para_markdown(tabelas["yoy_mensal"]) + "\n",
        df_para_markdown(tabelas["yoy_categoria"]) + "\n", df_para_markdown(tabelas["yoy_segmento"]) + "\n",
        "### Ponte de receita por clientes\n", "![Ponte](charts/03_ponte_clientes.png)\n",
        df_para_markdown(tabelas["ponte_clientes"]) + "\n",
        "### Preço, volume e mix\n", "![PVM](charts/04_preco_volume_mix.png)\n",
        df_para_markdown(tabelas["preco_volume_mix"]) + "\n",
        "### Mix por canal (% da receita)\n", df_para_markdown(tabelas["mix_canal"], casas=1) + "\n",
        "## 4. Clientes\n", "![RFM](charts/05_rfm_segmentos.png)\n", df_para_markdown(tabelas["rfm_segmentos"]) + "\n",
        "### Clientes em risco (ligar hoje)\n", df_para_markdown(tabelas["clientes_em_risco"]) + "\n",
        "### Retenção por coorte\n", "![Coortes](charts/06_coortes_retencao.png)\n",
        df_para_markdown(tabelas["curva_retencao"], casas=3) + "\n",
        "### Concentração da receita\n", "![Pareto](charts/08_pareto_clientes.png)\n",
        "## 5. Controles e validações\n", df_para_markdown(tabelas["controle_metas"]) + "\n",
        df_para_markdown(tabelas["validacoes"]) + "\n",
    ]
    caminho = OUTPUT_DIR / "relatorio.md"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("\n".join(partes), encoding="utf-8")
    log.info("relatório salvo em output/%s", caminho.name)
