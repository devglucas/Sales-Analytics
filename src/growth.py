"""
Crescimento 2025 x 2024.

- variação ano a ano (YoY) por mês e por dimensão, com contribuição para o crescimento
- ponte de receita por clientes: perdidos, base comum (like-for-like) e novos
- decomposição preço-volume-mix por categoria, com o efeito preço separado em
  reajuste de tabela e variação de desconto

Decomposição (por categoria, no nível de SKU, sobre os SKUs vendidos nos dois anos):
    volume = (Q1 - Q0) x P0 médio do mix do ano-base
    mix    = Q1 x Σ (s1_i - s0_i) x P0_i        (s = participação do SKU no volume)
    preço  = Σ Q1_i x (P1_i - P0_i)
           = Σ Q1_i x (T1_i - T0_i) x (1 - d0_i)   -> tabela (reajustes)
           + Σ Q1_i x T1_i x (d0_i - d1_i)         -> desconto (negativo se o desconto subiu)
    + receita de SKUs lançados - receita de SKUs descontinuados
A soma dos efeitos reproduz exatamente a variação da receita (identidade verificada na validação).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import ANO_ANALISE, ANO_BASE
from src.utils import configurar_logger

log = configurar_logger("growth")


def _com_receita(fato: pd.DataFrame) -> pd.DataFrame:
    return fato[fato["tipo"] != "BONIFICACAO"]


def yoy_mensal(fato: pd.DataFrame) -> pd.DataFrame:
    tabela = _com_receita(fato).pivot_table(index=fato["data"].dt.month, columns="ano",
                                            values=["receita_liquida", "caixas"], aggfunc="sum")
    resultado = pd.DataFrame({
        "mes": tabela.index,
        f"receita_{ANO_BASE}": tabela[("receita_liquida", ANO_BASE)].values,
        f"receita_{ANO_ANALISE}": tabela[("receita_liquida", ANO_ANALISE)].values,
        f"caixas_{ANO_BASE}": tabela[("caixas", ANO_BASE)].values,
        f"caixas_{ANO_ANALISE}": tabela[("caixas", ANO_ANALISE)].values,
    })
    resultado["var_receita_pct"] = (resultado[f"receita_{ANO_ANALISE}"] / resultado[f"receita_{ANO_BASE}"] - 1) * 100
    resultado["var_caixas_pct"] = (resultado[f"caixas_{ANO_ANALISE}"] / resultado[f"caixas_{ANO_BASE}"] - 1) * 100
    return resultado.round(2)


def yoy_por(fato: pd.DataFrame, dimensao: str) -> pd.DataFrame:
    tabela = (_com_receita(fato).groupby([dimensao, "ano"])["receita_liquida"].sum()
              .unstack("ano").reindex(columns=[ANO_BASE, ANO_ANALISE]).fillna(0))
    tabela.columns = [f"receita_{c}" for c in tabela.columns]
    variacao = tabela.iloc[:, 1] - tabela.iloc[:, 0]
    tabela["variacao"] = variacao
    tabela["var_pct"] = (tabela.iloc[:, 1] / tabela.iloc[:, 0].replace(0, np.nan) - 1) * 100
    tabela["contribuicao_pct"] = variacao / variacao.sum() * 100   # quanto do crescimento total veio daqui
    return tabela.sort_values("variacao", ascending=False).round(2).reset_index()


def ponte_clientes(fato: pd.DataFrame) -> pd.DataFrame:
    """Receita 2024 -> 2025 explicada por clientes perdidos, base comum e novos."""
    por_cliente = _com_receita(fato).groupby(["cliente_id", "ano"])["receita_liquida"].sum().unstack("ano").fillna(0)
    base, atual = por_cliente[ANO_BASE], por_cliente[ANO_ANALISE]
    comum = (base > 0) & (atual > 0)
    etapas = [
        (f"Receita {ANO_BASE}", base.sum(), por_cliente.index[base > 0].size),
        ("Clientes perdidos", -base[(base > 0) & (atual <= 0)].sum(), ((base > 0) & (atual <= 0)).sum()),
        ("Variação na base comum", (atual[comum] - base[comum]).sum(), comum.sum()),
        ("Clientes novos", atual[(base <= 0) & (atual > 0)].sum(), ((base <= 0) & (atual > 0)).sum()),
        (f"Receita {ANO_ANALISE}", atual.sum(), por_cliente.index[atual > 0].size),
    ]
    ponte = pd.DataFrame(etapas, columns=["etapa", "valor", "clientes"])
    ponte["like_for_like_pct"] = np.nan
    ponte.loc[2, "like_for_like_pct"] = round((atual[comum].sum() / base[comum].sum() - 1) * 100, 2)
    return ponte.round(2)


def preco_volume_mix(fato: pd.DataFrame) -> pd.DataFrame:
    vendas = _com_receita(fato)
    sku = (vendas.groupby(["categoria", "sku", "ano"])[["caixas", "receita_liquida", "receita_bruta"]].sum()
           .unstack("ano").fillna(0))
    q0, q1 = sku[("caixas", ANO_BASE)], sku[("caixas", ANO_ANALISE)]
    r0, r1 = sku[("receita_liquida", ANO_BASE)], sku[("receita_liquida", ANO_ANALISE)]
    b0, b1 = sku[("receita_bruta", ANO_BASE)], sku[("receita_bruta", ANO_ANALISE)]
    nos_dois = (q0 > 0) & (q1 > 0)

    p0, p1 = r0 / q0.where(nos_dois), r1 / q1.where(nos_dois)          # preço líquido médio
    t0, t1 = b0 / q0.where(nos_dois), b1 / q1.where(nos_dois)          # preço de tabela médio
    d0, d1 = 1 - p0 / t0, 1 - p1 / t1                                  # desconto médio
    categoria = sku.index.get_level_values("categoria")
    qt0 = q0.where(nos_dois).groupby(categoria).transform("sum")
    qt1 = q1.where(nos_dois).groupby(categoria).transform("sum")
    s0, s1 = q0 / qt0, q1 / qt1

    efeitos = pd.DataFrame({
        "receita_base": r0, "receita_atual": r1,
        "volume": (qt1 - qt0) * s0 * p0,
        "mix": qt1 * (s1 - s0) * p0,
        "preco_tabela": q1 * (t1 - t0) * (1 - d0),
        "preco_desconto": q1 * t1 * (d0 - d1),
        "lancamentos": r1.where(q0 <= 0, 0.0),
        "descontinuados": -r0.where(q1 <= 0, 0.0),
    }).fillna(0.0)
    por_categoria = efeitos.groupby(level="categoria").sum()
    por_categoria.loc["Total"] = por_categoria.sum()
    por_categoria["variacao"] = por_categoria["receita_atual"] - por_categoria["receita_base"]
    por_categoria["soma_dos_efeitos"] = por_categoria[["volume", "mix", "preco_tabela", "preco_desconto",
                                                       "lancamentos", "descontinuados"]].sum(axis=1)
    total = por_categoria.loc["Total"]
    log.info("PVM: variação R$ %.2f mi = volume %.2f + mix %.2f + tabela %.2f + desconto %.2f + lançamentos %.2f",
             total["variacao"] / 1e6, total["volume"] / 1e6, total["mix"] / 1e6, total["preco_tabela"] / 1e6,
             total["preco_desconto"] / 1e6, total["lancamentos"] / 1e6)
    return por_categoria.round(2).reset_index()


def analisar_crescimento(fato: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "yoy_mensal": yoy_mensal(fato),
        "yoy_categoria": yoy_por(fato, "categoria"),
        "yoy_regional": yoy_por(fato, "regional"),
        "yoy_segmento": yoy_por(fato, "segmento"),
        "mix_canal": _com_receita(fato[fato["canal"] != "nao_registrado"]).pivot_table(
            index="mes", columns="canal", values="receita_liquida", aggfunc="sum", fill_value=0)
            .pipe(lambda t: t.div(t.sum(axis=1), axis=0).mul(100).round(1))
            .rename_axis(columns=None).reset_index().assign(mes=lambda d: d["mes"].astype(str)),
        "ponte_clientes": ponte_clientes(fato),
        "preco_volume_mix": preco_volume_mix(fato),
    }
