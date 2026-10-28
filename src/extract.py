"""
Extração: lê todas as fontes como texto, sem converter tipos.

As vendas estão em um arquivo por mês. Cada arquivo é lido conforme o seu
layout, detectado pelo cabeçalho: o ERP antigo exportava com ';' e o novo com ','.
"""

from __future__ import annotations

import pandas as pd

from src.config import RAW_DIR, VENDAS_DIR
from src.utils import configurar_logger

log = configurar_logger("extract")


def detectar_layout(caminho) -> str:
    cabecalho = caminho.open(encoding="utf-8").readline()
    return "antigo" if ";" in cabecalho else "novo"


def ler_vendas() -> dict[str, pd.DataFrame]:
    """Concatena os arquivos mensais por layout, guardando o arquivo e a linha de origem."""
    blocos = {"antigo": [], "novo": []}
    for caminho in sorted(VENDAS_DIR.glob("vendas_*.csv")):
        layout = detectar_layout(caminho)
        df = pd.read_csv(caminho, sep=";" if layout == "antigo" else ",", dtype="string")
        blocos[layout].append(df.assign(arquivo=caminho.name, linha_origem=df.index + 2))
    vendas = {layout: pd.concat(dfs, ignore_index=True) for layout, dfs in blocos.items()}
    log.info("%d arquivos de vendas: layout antigo %d linhas | layout novo %d linhas",
             sum(len(b) for b in blocos.values()), len(vendas["antigo"]), len(vendas["novo"]))
    return vendas


def ler_metas() -> dict[str, pd.DataFrame]:
    """Planilha de metas: o cabeçalho da aba de vendedores está na 3ª linha (há um título acima)."""
    caminho = RAW_DIR / "metas_2025.xlsx"
    return {
        "vendedores": pd.read_excel(caminho, sheet_name="Metas Vendedores", header=2, dtype=object),
        "regionais": pd.read_excel(caminho, sheet_name="Metas Regionais", dtype=object),
    }


def extrair_dados() -> dict:
    dados = {
        "vendas": ler_vendas(),
        "metas": ler_metas(),
        "clientes": pd.read_json(RAW_DIR / "clientes.json", dtype=False),
        "vendedores": pd.read_csv(RAW_DIR / "vendedores.csv", dtype="string"),
        "produtos": pd.read_csv(RAW_DIR / "produtos.csv", dtype="string"),
        "tabela_precos": pd.read_csv(RAW_DIR / "tabela_precos.csv", dtype="string"),
        "depara_sku": pd.read_csv(RAW_DIR / "depara_sku.csv", dtype="string"),
    }
    for nome in ["clientes", "vendedores", "produtos", "tabela_precos", "depara_sku"]:
        log.info("%-14s %5d linhas", nome, len(dados[nome]))
    return dados
