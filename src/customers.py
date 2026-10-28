"""
Análise de clientes.

RFM (últimos 12 meses até a data de corte)
    R = dias desde a última compra · F = número de notas · M = receita líquida
    F e M viram nota de 1 a 5 por quintis (pd.qcut sobre o rank, para empates não
    quebrarem as faixas). R usa faixas de negócio (até 7, 15, 30, 60 dias e acima):
    as recências se concentram em poucos dias e quintis criariam diferenças
    artificiais. O par (R, F) define o segmento.

Coortes de retenção
    Coorte = mês da primeira compra. Só entram clientes CADASTRADOS a partir de
    jan/2024: um cliente antigo cuja primeira compra nos dados é jan/2024 não é
    novo, apenas o histórico começa ali (censura à esquerda).

Pareto/ABC
    Concentração da receita: quantos clientes fazem 80% do faturamento.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import ANO_ANALISE, ANO_BASE, DATA_CORTE, FAIXAS_RECENCIA_DIAS, JANELA_RFM_MESES
from src.utils import configurar_logger

log = configurar_logger("customers")

SEGMENTOS_RFM = ["Campeões", "Leais", "Promissores", "Precisam de atenção", "Em risco", "Hibernando", "Perdidos"]


def _nota_quintil(valores: pd.Series, maior_e_melhor: bool = True) -> pd.Series:
    rotulos = [1, 2, 3, 4, 5] if maior_e_melhor else [5, 4, 3, 2, 1]
    return pd.qcut(valores.rank(method="first"), q=5, labels=rotulos).astype(int)


def rfm(fato: pd.DataFrame, clientes: pd.DataFrame) -> pd.DataFrame:
    inicio = DATA_CORTE - pd.DateOffset(months=JANELA_RFM_MESES) + pd.Timedelta(days=1)
    janela = fato[(fato["data"] >= inicio) & (fato["data"] <= DATA_CORTE) & (fato["tipo"] != "BONIFICACAO")]
    vendas = janela[janela["tipo"] == "VENDA"]
    base = pd.DataFrame({
        "recencia_dias": (DATA_CORTE - vendas.groupby("cliente_id")["data"].max()).dt.days,
        "frequencia": vendas.groupby("cliente_id")["nf"].nunique(),
        "valor": janela.groupby("cliente_id")["receita_liquida"].sum(),
    }).dropna()
    base = base[base["valor"] > 0]
    base["R"] = pd.cut(base["recencia_dias"], bins=FAIXAS_RECENCIA_DIAS, labels=[5, 4, 3, 2, 1]).astype(int)
    base["F"] = _nota_quintil(base["frequencia"])
    base["M"] = _nota_quintil(base["valor"])
    r, f = base["R"], base["F"]
    base["segmento_rfm"] = np.select(
        [(r >= 4) & (f >= 4), (r >= 3) & (f >= 3), (r >= 4), (r == 3), (r <= 2) & (f >= 3), (r == 2)],
        SEGMENTOS_RFM[:-1], default="Perdidos")
    return base.join(clientes.set_index("cliente_id")[["segmento", "regional", "vendedor_id"]]).reset_index()


def resumo_rfm(tabela: pd.DataFrame) -> pd.DataFrame:
    resumo = tabela.groupby("segmento_rfm").agg(
        clientes=("cliente_id", "count"), receita=("valor", "sum"), recencia_media=("recencia_dias", "mean"),
        frequencia_media=("frequencia", "mean"), ticket_anual_medio=("valor", "mean"))
    resumo["pct_clientes"] = resumo["clientes"] / resumo["clientes"].sum() * 100
    resumo["pct_receita"] = resumo["receita"] / resumo["receita"].sum() * 100
    return resumo.reindex(SEGMENTOS_RFM).dropna(how="all").round(2).reset_index()


def coortes(fato: pd.DataFrame, clientes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    novos = clientes.loc[clientes["data_cadastro"] >= pd.Timestamp(f"{ANO_BASE}-01-01"), "cliente_id"]
    vendas = fato[(fato["tipo"] == "VENDA") & fato["cliente_id"].isin(novos)]
    atividade = vendas[["cliente_id", "mes"]].drop_duplicates()
    atividade["coorte"] = atividade.groupby("cliente_id")["mes"].transform("min")
    atividade["mes_relativo"] = (atividade["mes"] - atividade["coorte"]).apply(lambda d: d.n)

    ativos = atividade.pivot_table(index="coorte", columns="mes_relativo", values="cliente_id", aggfunc="nunique")
    # Célula vazia tem dois significados: "ninguém voltou" (0%) ou "ainda não deu tempo de
    # observar" (NaN). Só os meses já decorridos desde a coorte viram 0.
    ultimo_mes = fato["mes"].max()
    decorridos = pd.Series([(ultimo_mes - c).n for c in ativos.index], index=ativos.index)
    observavel = pd.DataFrame({m: m <= decorridos for m in ativos.columns})
    ativos = ativos.fillna(0).where(observavel)
    tamanho = ativos[0]
    retencao = ativos.div(tamanho, axis=0).round(4)
    retencao.insert(0, "clientes", tamanho)

    # curva média ponderada pelo tamanho, usando só as coortes que já chegaram em cada mês
    curva = pd.DataFrame({"mes_relativo": ativos.columns,
                          "retencao_media": (ativos.sum() / ativos.notna().mul(tamanho, axis=0).sum()).round(4).values,
                          "coortes_observadas": ativos.notna().sum().values})
    retencao.index = retencao.index.astype(str)
    return retencao.rename_axis(index="coorte", columns=None).reset_index(), curva


def pareto_clientes(fato: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    receita = (fato[(fato["ano"] == ANO_ANALISE) & (fato["tipo"] != "BONIFICACAO")]
               .groupby("cliente_id")["receita_liquida"].sum().sort_values(ascending=False))
    receita = receita[receita > 0]
    tabela = pd.DataFrame({"receita": receita, "pct_acumulado": receita.cumsum() / receita.sum() * 100})
    tabela["pct_clientes"] = np.arange(1, len(tabela) + 1) / len(tabela) * 100
    tabela["classe_abc"] = pd.cut(tabela["pct_acumulado"], [0, 80, 95, 100.0001], labels=["A", "B", "C"])
    resumo = {"clientes": len(tabela),
              "pct_clientes_para_80pct_receita": round(float((tabela["pct_acumulado"] <= 80).mean() * 100), 1)}
    return tabela.round(2).reset_index(), resumo


def analisar_clientes(fato: pd.DataFrame, clientes: pd.DataFrame) -> dict:
    tabela_rfm = rfm(fato, clientes)
    retencao, curva = coortes(fato, clientes)
    pareto, resumo_pareto = pareto_clientes(fato)
    log.info("RFM: %d clientes | coortes: %d | %.1f%% dos clientes fazem 80%% da receita",
             len(tabela_rfm), len(retencao), resumo_pareto["pct_clientes_para_80pct_receita"])
    return {"rfm_clientes": tabela_rfm, "rfm_segmentos": resumo_rfm(tabela_rfm), "coortes_retencao": retencao,
            "curva_retencao": curva, "pareto_clientes": pareto, "pareto_resumo": resumo_pareto}
