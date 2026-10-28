"""Exportação dos resultados para data/processed e output/reports."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import PROCESSED_DIR, REPORTS_DIR, ROOT_DIR
from src.utils import configurar_logger

log = configurar_logger("load")


def salvar_csv(df: pd.DataFrame, caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(caminho, index=False, encoding="utf-8")


def exportar_dados(res: dict) -> None:
    arquivos = {
        "fato_vendas.csv": res["fato"].assign(mes=res["fato"]["mes"].astype(str)),
        "metas_vendedor_mes.csv": res["desempenho"]["metas_x_realizado_mensal"].assign(
            mes=lambda d: d["mes"].astype(str)),
        "rfm_clientes.csv": res["clientes"]["rfm_clientes"],
        "rejeitados.csv": res["rejeitados"],
    }
    for nome, df in arquivos.items():
        salvar_csv(df, PROCESSED_DIR / nome)
    log.info("%d arquivos salvos em %s", len(arquivos), PROCESSED_DIR.relative_to(ROOT_DIR))


def exportar_relatorios(tabelas: dict[str, pd.DataFrame]) -> None:
    for nome, df in tabelas.items():
        salvar_csv(df, REPORTS_DIR / f"{nome}.csv")
    log.info("%d relatórios CSV salvos em %s", len(tabelas), REPORTS_DIR.relative_to(ROOT_DIR))
