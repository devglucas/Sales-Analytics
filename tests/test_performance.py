import pandas as pd

from src.performance import metas_x_realizado, positivacao


def _fato(linhas):
    df = pd.DataFrame(linhas, columns=["vendedor_id", "cliente_id", "data", "receita_liquida"])
    df["data"] = pd.to_datetime(df["data"])
    return df.assign(mes=df["data"].dt.to_period("M"), ano=df["data"].dt.year, tipo="VENDA")


def test_comissao_por_faixa_e_atingimento_acumulado():
    metas = pd.DataFrame({"vendedor_id": ["V01"] * 3, "mes": pd.period_range("2025-01", periods=3, freq="M"),
                          "meta": [100.0, 100.0, 100.0]})
    fato = _fato([("V01", "C1", "2025-01-10", 79.0), ("V01", "C1", "2025-02-10", 100.0), ("V01", "C1", "2025-03-10", 130.0)])
    vendedores = pd.DataFrame({"vendedor_id": ["V01"], "nome": ["Ana"], "regional": ["Capital"]})
    r = metas_x_realizado(metas, fato, vendedores)
    assert r["faixa"].astype(str).tolist() == ["abaixo de 80%", "100% a 120%", "acima de 120%"]
    assert r["comissao"].tolist() == [0.0, 3.0, 5.2]                  # 0%, 3% e 4%
    assert round(r["atingimento_ytd"].iat[-1], 4) == round(309 / 300, 4)


def test_positivacao_transfere_carteira_para_o_substituto():
    fato = _fato([
        ("V07", "C1", "2025-01-10", 1), ("V07", "C2", "2025-01-12", 1),
        ("V17", "C1", "2025-03-05", 1),                                    # C1 passa a comprar com o V17
    ])
    r = positivacao(fato).set_index(["vendedor_id", "mes"])
    assert r.loc[("V07", pd.Period("2025-02")), "positivacao"] == 0.0     # carteira ativa, ninguém comprou
    assert r.loc[("V17", pd.Period("2025-03")), "positivados"] == 1
    assert r.loc[("V17", pd.Period("2025-04")), "carteira_ativa"] == 1    # C1 segue na carteira do V17
