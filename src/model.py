"""
Modelo analítico: fato de vendas enriquecida + calendário.

Regras de receita:
- VENDA soma, DEVOLUCAO subtrai (sinal -1) e BONIFICACAO não gera receita,
  mas o volume bonificado é guardado à parte (custo comercial)
- receita bruta = quantidade x preço de TABELA vigente na data da venda
- receita líquida = quantidade x preço praticado (após desconto)
- desconto real = 1 - preço praticado / preço de tabela
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import DATA_CORTE, FERIADOS
from src.utils import configurar_logger

log = configurar_logger("model")

SINAL = {"VENDA": 1, "DEVOLUCAO": -1, "BONIFICACAO": 0}


def preco_de_tabela(itens: pd.DataFrame, tabela: pd.DataFrame) -> pd.Series:
    """Preço de lista vigente para cada linha (o último reajuste até a data da venda)."""
    consulta = itens[["data", "sku"]].reset_index().sort_values("data")
    precos = tabela[["sku", "vigente_desde", "preco_lista"]].sort_values("vigente_desde")
    cruzado = pd.merge_asof(consulta, precos, left_on="data", right_on="vigente_desde", by="sku", direction="backward")
    return cruzado.set_index("index")["preco_lista"].reindex(itens.index)


def calendario(inicio: pd.Timestamp, fim: pd.Timestamp = DATA_CORTE) -> pd.DataFrame:
    dias = pd.DataFrame({"data": pd.date_range(inicio, fim, freq="D")})
    dias["dia_util"] = np.is_busday(dias["data"].values.astype("datetime64[D]"),
                                    holidays=FERIADOS.values.astype("datetime64[D]"))
    return (dias.groupby(dias["data"].dt.to_period("M"))
            .agg(dias_corridos=("data", "size"), dias_uteis=("dia_util", "sum"))
            .rename_axis("mes").reset_index())


def montar_fato_vendas(itens: pd.DataFrame, cadastros: dict) -> pd.DataFrame:
    fato = (
        itens
        .merge(cadastros["produtos"][["sku", "nome", "embalagem", "categoria", "lancamento"]], on="sku", how="left",
               validate="many_to_one")
        .merge(cadastros["clientes"][["cliente_id", "segmento", "cidade", "regional", "data_cadastro"]],
               on="cliente_id", how="left", validate="many_to_one")
    )
    fato["preco_tabela"] = preco_de_tabela(fato, cadastros["tabela_precos"])
    sinal = fato["tipo"].map(SINAL)
    fato = fato.assign(
        sinal=sinal,
        caixas=fato["quantidade"] * sinal,
        caixas_bonificadas=fato["quantidade"].where(fato["tipo"] == "BONIFICACAO", 0),
        receita_bruta=(fato["quantidade"] * fato["preco_tabela"] * sinal).round(2),
        receita_liquida=(fato["quantidade"] * fato["preco_liquido"].astype("float64") * sinal).round(2),
        desconto_real=(1 - fato["preco_liquido"].astype("float64") / fato["preco_tabela"]).where(fato["tipo"] == "VENDA"),
        ano=fato["data"].dt.year,
        mes=fato["data"].dt.to_period("M"),
        trimestre=fato["data"].dt.quarter,
    )
    log.info("fato_vendas: %d linhas | receita líquida R$ %.2f mi | %d clientes | %d SKUs", len(fato),
             fato["receita_liquida"].sum() / 1e6, fato["cliente_id"].nunique(), fato["sku"].nunique())
    return fato
