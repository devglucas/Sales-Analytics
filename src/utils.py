"""Funções genéricas: logger, texto, números, rejeição e formatação."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd


def configurar_logger(nome: str = "pipeline") -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)-10s | %(message)s",
                        datefmt="%H:%M:%S")
    return logging.getLogger(nome)


def chave_texto(serie: pd.Series) -> pd.Series:
    """Forma canônica para comparar nomes: minúsculo, sem acento, sem espaços extras."""
    return (
        serie.astype("string").str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii")
        .astype("string").str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    )


def parse_numero(serie: pd.Series) -> pd.Series:
    """'R$ 1.234,56', '1234.56' e 1234 (número) -> float. Vírgula = formato brasileiro."""
    texto = serie.astype("string").str.replace(r"(?i)r\$", "", regex=True).str.replace(r"\s", "", regex=True)
    brasileiro = texto.str.contains(",", regex=False, na=False)
    texto = texto.mask(brasileiro, texto.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(texto.replace("", pd.NA), errors="coerce").astype("float64")


def separar_rejeitados(df: pd.DataFrame, invalido: pd.Series, motivo: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    invalido = invalido.fillna(False).astype(bool)
    return df.loc[~invalido], df.loc[invalido].assign(motivo_rejeicao=motivo)


def formatar_br(valor, casas: int = 2) -> str:
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return ""
    if isinstance(valor, (bool, np.bool_)):
        return "sim" if valor else "não"
    if isinstance(valor, (int, np.integer)):
        return f"{valor:,}".replace(",", ".")
    if isinstance(valor, (float, np.floating)):
        return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if isinstance(valor, pd.Timestamp):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def df_para_markdown(df: pd.DataFrame, casas: int = 2) -> str:
    cabecalho = "| " + " | ".join(map(str, df.columns)) + " |"
    separador = "|" + "|".join("---" for _ in df.columns) + "|"
    linhas = ["| " + " | ".join("" if pd.isna(v) else formatar_br(v, casas) for v in linha) + " |"
              for linha in df.itertuples(index=False)]
    return "\n".join([cabecalho, separador, *linhas])
