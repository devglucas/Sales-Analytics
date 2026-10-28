import pandas as pd
import pytest

from src.growth import ponte_clientes, preco_volume_mix


def _fato(linhas):
    df = pd.DataFrame(linhas, columns=["ano", "cliente_id", "categoria", "sku", "caixas", "preco_tabela", "desconto"])
    return df.assign(tipo="VENDA", receita_bruta=df["caixas"] * df["preco_tabela"],
                     receita_liquida=df["caixas"] * df["preco_tabela"] * (1 - df["desconto"]))


def test_pvm_soma_dos_efeitos_igual_a_variacao():
    fato = _fato([
        (2024, "C1", "Cerveja", "A", 100, 10.0, 0.05), (2024, "C1", "Cerveja", "B", 100, 20.0, 0.05),
        (2025, "C1", "Cerveja", "A", 80, 11.0, 0.10), (2025, "C1", "Cerveja", "B", 140, 21.0, 0.05),
        (2025, "C2", "Cerveja", "C", 10, 50.0, 0.0),                       # lançamento
        (2024, "C2", "Água", "D", 50, 2.0, 0.0),                           # descontinuado
    ])
    pvm = preco_volume_mix(fato).set_index("categoria")
    efeitos = ["volume", "mix", "preco_tabela", "preco_desconto", "lancamentos", "descontinuados"]
    for categoria in pvm.index:
        assert pvm.loc[categoria, efeitos].sum() == pytest.approx(pvm.loc[categoria, "variacao"], abs=0.01)
    cerveja = pvm.loc["Cerveja"]
    assert cerveja["mix"] > 0                      # o volume migrou para o SKU mais caro (B)
    assert cerveja["preco_desconto"] < 0           # o desconto do A subiu de 5% para 10%
    assert cerveja["lancamentos"] == 500.0
    assert pvm.loc["Água", "descontinuados"] == -100.0


def test_ponte_de_clientes():
    fato = _fato([
        (2024, "C1", "X", "A", 10, 10.0, 0.0), (2025, "C1", "X", "A", 12, 10.0, 0.0),   # base comum
        (2024, "C2", "X", "A", 5, 10.0, 0.0),                                           # perdido
        (2025, "C3", "X", "A", 3, 10.0, 0.0),                                           # novo
    ])
    ponte = ponte_clientes(fato).set_index("etapa")["valor"]
    assert ponte.tolist() == [150.0, -50.0, 20.0, 30.0, 150.0]
    assert ponte.iloc[0] + ponte.iloc[1:4].sum() == ponte.iloc[4]
