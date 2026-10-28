import pandas as pd

from src.clean import harmonizar_layout_antigo, harmonizar_layout_novo, inferir_depara_por_preco, limpar_metas

TABELA = pd.DataFrame({
    "sku": ["1001", "1001", "1002"],
    "vigente_desde": pd.to_datetime(["2023-01-01", "2024-03-01", "2023-01-01"]),
    "preco_lista": [100.0, 105.0, 40.0],
})


def _antigo(linhas):
    return pd.DataFrame(linhas, columns=["data", "nf", "cod_vendedor", "cod_cliente", "sku", "qtd", "vlr_unit", "vlr_desc"],
                        dtype="string")


def test_layout_antigo_vira_esquema_harmonizado():
    df = _antigo([
        ("02/01/2024", "1", "v-03", "CLI-1", "CRV-011", "4", "100,00", "20,00"),    # venda com 5% de desconto
        ("03/01/2024", "2", "3", "CLI-1", "CRV-011", "-2", "100,00", "-10,00"),     # devolução
        ("04/01/2024", "3", "V03", "CLI-1", "CRV-011", "1", "0,00", "0,00"),        # bonificação
    ])
    depara = pd.DataFrame({"sku_antigo": ["CRV-011"], "sku_novo": ["1001"]})
    r = harmonizar_layout_antigo(df, depara, TABELA)
    assert r["vendedor_id"].tolist() == ["V03"] * 3
    assert r["tipo"].tolist() == ["VENDA", "DEVOLUCAO", "BONIFICACAO"]
    assert r["quantidade"].tolist() == [4, 2, 1]
    assert r["preco_liquido"].iat[0] == 95.0 and r["desconto_pct"].iat[0] == 0.05
    assert r["sku"].tolist() == ["1001"] * 3


def test_layout_novo_desconto_em_percentual():
    df = pd.DataFrame({"data_emissao": ["2024-07-01"], "numero_nf": ["9"], "produto_sku": ["1001"],
                       "tipo_operacao": ["venda"], "quantidade": ["3"], "preco_unitario": ["99.75"],
                       "desconto_pct": ["5.0"]}, dtype="string")
    r = harmonizar_layout_novo(df)
    assert r["tipo"].iat[0] == "VENDA" and r["desconto_pct"].iat[0] == 0.05 and r["preco_liquido"].iat[0] == 99.75


def test_depara_inferido_pelo_preco_de_tabela():
    antigo = pd.DataFrame({"sku_antigo": ["CRV-099"] * 3, "data": pd.to_datetime(["2024-01-10", "2024-02-10", "2024-04-10"]),
                           "preco_bruto": [100.0, 100.0, 105.0]})   # bate com o 1001 antes e depois do reajuste
    assert inferir_depara_por_preco(antigo, TABELA, {"1001", "1002"}).to_dict() == {"CRV-099": "1001"}


def test_metas_largas_viram_longas_e_conferem_com_o_total():
    meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    planilha = pd.DataFrame([
        {"Vendedor": "JOAO SILVA", "Regional": "Capital", **{m: "R$ 1.000,00" for m in meses}},
        {"Vendedor": "Ana Lima", "Regional": "Capital", **{m: (500 if i >= 6 else None) for i, m in enumerate(meses)}},
        {"Vendedor": "TOTAL", "Regional": None, **{m: (1500 if i >= 6 else 1000) for i, m in enumerate(meses)}},
    ])
    regionais = pd.DataFrame({"regional": ["Capital"], "categoria": ["Cerveja"], "T1": [10], "T2": [20], "T3": [30], "T4": [40]})
    vendedores = pd.DataFrame({"vendedor_id": ["V01", "V02"], "nome": ["João Silva", "Ana Lima"]})
    longas, reg_longas, controle = limpar_metas({"vendedores": planilha, "regionais": regionais}, vendedores, 2025)
    assert len(longas) == 12 + 6                                  # Ana só tem meta a partir de julho
    assert set(longas["vendedor_id"]) == {"V01", "V02"}           # nome com/sem acento e CAIXA ALTA
    assert controle["diferenca"].abs().max() == 0
    assert reg_longas["trimestre"].tolist() == [1, 2, 3, 4]
