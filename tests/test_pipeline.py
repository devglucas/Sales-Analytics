"""Testes de ponta a ponta sobre os dados de data/raw (sem gravar arquivos)."""

import pytest

from main import executar_pipeline


@pytest.fixture(scope="module")
def resultado():
    return executar_pipeline(exportar=False)


def test_nenhuma_regra_critica_falha(resultado):
    assert resultado["validacoes"].query("severidade == 'critica'")["passou"].all()


def test_harmonizacao_preserva_as_vendas_do_layout_antigo(resultado):
    fato = resultado["fato"]
    assert set(fato["layout"]) == {"antigo", "novo"}
    assert fato["sku"].notna().all()                                  # nenhum SKU antigo perdido
    assert len(resultado["depara_inferido"]) == 2
    descontos = fato[fato["tipo"] == "VENDA"].groupby("layout")["desconto_pct"].mean()
    assert abs(descontos["antigo"] - descontos["novo"]) < 0.01        # mesma escala nos dois layouts


def test_reexportacao_nao_duplica_receita(resultado):
    fato = resultado["fato"]
    assert not fato.duplicated(subset=["nf", "sku", "tipo"]).any()


def test_metas_completas_e_comissoes(resultado):
    mensal = resultado["desempenho"]["metas_x_realizado_mensal"]
    assert mensal["meta"].notna().sum() == 16 * 12                    # 16 vendedores ativos por mês
    assert (mensal["comissao"] >= 0).all()


def test_identidades_de_crescimento(resultado):
    pvm = resultado["crescimento"]["preco_volume_mix"].set_index("categoria")
    assert pvm.loc["Total", "soma_dos_efeitos"] == pytest.approx(pvm.loc["Total", "variacao"], abs=0.05)
    assert pvm.loc["Total", "lancamentos"] > 0                         # SKUs lançados em 2025
