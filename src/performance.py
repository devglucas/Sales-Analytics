"""
Desempenho comercial de 2025: metas x realizado, comissões e indicadores de vendedor.

- atingimento mensal e acumulado no ano (YTD, com cumsum por vendedor)
- comissão pela faixa de atingimento do mês (pd.cut)
- ranking e participação dentro da regional (groupby + rank / transform)
- metas da diretoria por regional x categoria x trimestre
- positivação: % da carteira ativa que comprou no mês
- produtividade (receita por dia útil) e desconto médio concedido
"""

from __future__ import annotations

import pandas as pd

from src.config import ANO_ANALISE, FAIXAS_COMISSAO, PERCENTUAIS_COMISSAO
from src.utils import configurar_logger

log = configurar_logger("perform")

ROTULOS_FAIXA = ["abaixo de 80%", "80% a 100%", "100% a 120%", "acima de 120%"]


def metas_x_realizado(metas: pd.DataFrame, fato: pd.DataFrame, vendedores: pd.DataFrame) -> pd.DataFrame:
    realizado = (fato[fato["ano"] == ANO_ANALISE].groupby(["vendedor_id", "mes"])["receita_liquida"].sum()
                 .rename("realizado").reset_index())
    df = metas.merge(realizado, on=["vendedor_id", "mes"], how="outer", indicator=True)
    sem_meta = df["_merge"] == "right_only"
    if sem_meta.any():
        log.warning("%d vendedor-mês com venda e sem meta", sem_meta.sum())
    df = df.drop(columns="_merge").fillna({"realizado": 0.0})

    df = df.sort_values(["vendedor_id", "mes"])
    df["atingimento"] = df["realizado"] / df["meta"]
    df["faixa"] = pd.cut(df["atingimento"], bins=FAIXAS_COMISSAO, labels=ROTULOS_FAIXA, right=False)
    df["comissao"] = (df["realizado"] * df["faixa"].map(dict(zip(ROTULOS_FAIXA, PERCENTUAIS_COMISSAO))).astype("float64")).round(2)
    acumulado = df.groupby("vendedor_id")[["meta", "realizado"]].cumsum()
    df["atingimento_ytd"] = acumulado["realizado"] / acumulado["meta"]
    return df.merge(vendedores[["vendedor_id", "nome", "regional"]], on="vendedor_id", how="left")


def resumo_vendedores(mensal: pd.DataFrame, fato: pd.DataFrame) -> pd.DataFrame:
    ano = fato[fato["ano"] == ANO_ANALISE]
    resumo = mensal.groupby(["vendedor_id", "nome", "regional"]).agg(
        meses_com_meta=("meta", "count"), meta=("meta", "sum"), realizado=("realizado", "sum"),
        meses_meta_batida=("atingimento", lambda a: (a >= 1).sum()), comissao=("comissao", "sum"),
    ).reset_index()
    resumo["atingimento"] = resumo["realizado"] / resumo["meta"]
    # dentro da regional: posição e fatia da receita
    resumo["ranking_regional"] = resumo.groupby("regional")["atingimento"].rank(ascending=False, method="min").astype(int)
    resumo["participacao_regional"] = resumo["realizado"] / resumo.groupby("regional")["realizado"].transform("sum")
    vendas = ano[ano["tipo"] == "VENDA"].groupby("vendedor_id")[["receita_bruta", "receita_liquida"]].sum()
    resumo["desconto_medio"] = resumo["vendedor_id"].map(1 - vendas["receita_liquida"] / vendas["receita_bruta"])
    resumo["comissao_sobre_receita"] = resumo["comissao"] / resumo["realizado"]
    return resumo.sort_values(["regional", "ranking_regional"]).round(4)


def metas_regionais(metas_reg: pd.DataFrame, fato: pd.DataFrame) -> pd.DataFrame:
    ano = fato[fato["ano"] == ANO_ANALISE]
    realizado = ano.groupby(["regional", "categoria", "trimestre"])["receita_liquida"].sum().rename("realizado")
    df = metas_reg.merge(realizado.reset_index(), on=["regional", "categoria", "trimestre"], how="left")
    df["realizado"] = df["realizado"].fillna(0.0)
    df["atingimento"] = df["realizado"] / df["meta"]
    return df


def matriz_regional_categoria(metas_reg_x_real: pd.DataFrame) -> pd.DataFrame:
    """Atingimento anual por regional (linhas) x categoria (colunas), com totais nas margens."""
    soma = metas_reg_x_real.pivot_table(index="regional", columns="categoria", values=["meta", "realizado"],
                                        aggfunc="sum", margins=True, margins_name="Total")
    return (soma["realizado"] / soma["meta"]).round(3).rename_axis(index=None, columns=None).reset_index(names="regional")


def positivacao(fato: pd.DataFrame) -> pd.DataFrame:
    """
    Positivação = clientes da carteira ATIVA que compraram no mês / carteira ativa.
    Carteira ativa do mês = clientes que compraram em algum dos últimos 4 meses (incluindo o atual),
    atribuídos ao vendedor da última venda: assim a carteira do vendedor desligado passa
    automaticamente para quem o substituiu.
    """
    vendas = fato[fato["tipo"] == "VENDA"]
    meses = pd.period_range(vendas["mes"].min(), vendas["mes"].max(), freq="M")
    por_mes = vendas.sort_values("data").groupby(["cliente_id", "mes"]).agg(vendedor_id=("vendedor_id", "last"))
    grade = por_mes.reindex(pd.MultiIndex.from_product([por_mes.index.levels[0], meses], names=["cliente_id", "mes"]))
    grade["comprou"] = grade["vendedor_id"].notna()
    por_cliente = grade.groupby(level="cliente_id")
    grade["ativo"] = por_cliente["comprou"].transform(lambda s: s.rolling(4, min_periods=1).max().astype(bool))
    grade["vendedor_id"] = por_cliente["vendedor_id"].ffill()
    carteira = grade[grade["ativo"]].reset_index()
    resultado = carteira.groupby(["vendedor_id", "mes"]).agg(carteira_ativa=("cliente_id", "count"),
                                                             positivados=("comprou", "sum")).reset_index()
    resultado["positivacao"] = (resultado["positivados"] / resultado["carteira_ativa"]).round(4)
    return resultado[resultado["mes"].dt.year == ANO_ANALISE]


def produtividade(mensal: pd.DataFrame, calendario: pd.DataFrame) -> pd.DataFrame:
    df = mensal.merge(calendario[["mes", "dias_uteis"]], on="mes", how="left")
    df["receita_por_dia_util"] = (df["realizado"] / df["dias_uteis"]).round(2)
    return df.pivot_table(index=["vendedor_id", "nome"], columns=df["mes"].dt.month, values="receita_por_dia_util") \
        .rename_axis(columns="mes").reset_index()


def analisar_desempenho(metas, metas_reg, fato, vendedores, calendario) -> dict[str, pd.DataFrame]:
    mensal = metas_x_realizado(metas, fato, vendedores)
    resumo = resumo_vendedores(mensal, fato)
    regionais = metas_regionais(metas_reg, fato)
    total = mensal[["meta", "realizado"]].sum()
    log.info("2025: meta R$ %.1f mi | realizado R$ %.1f mi (%.1f%%) | comissões R$ %.0f mil",
             total["meta"] / 1e6, total["realizado"] / 1e6, total["realizado"] / total["meta"] * 100,
             mensal["comissao"].sum() / 1e3)
    return {
        "metas_x_realizado_mensal": mensal,
        "resumo_vendedores": resumo,
        "metas_regionais_x_realizado": regionais,
        "atingimento_regional_categoria": matriz_regional_categoria(regionais),
        "positivacao": positivacao(fato),
        "produtividade_dia_util": produtividade(mensal, calendario),
    }
