from decimal import Decimal as D

import pytest

from app import metrologia as m


def test_media_de_duas_leituras():
    assert m.media([D("5.0010"), D("5.0006")]) == D("5.0008")


def test_desvio_padrao_amostral_duas_leituras():
    # |a-b| / raiz(2)
    assert m.arredondar(m.desvio_padrao_amostral([D("5.0010"), D("5.0006")]), 7) == D("0.0002828")


def test_desvio_padrao_leituras_iguais_e_zero():
    assert m.desvio_padrao_amostral([D("1.5"), D("1.5")]) == 0


def test_desvio_padrao_exige_duas_leituras():
    with pytest.raises(ValueError):
        m.desvio_padrao_amostral([D("1")])


def test_erro_sistematico_positivo_e_negativo():
    assert m.erro_sistematico(D("5.0008"), D("5")) == D("0.0008")
    assert m.erro_sistematico(D("4.9990"), D("5")) == D("-0.0010")


def test_precisao_de_sete_casas_preservada():
    r = m.calcular_ponto(D("6.075"), [D("6.0787295"), D("6.0787295")], D("0.01"))
    assert r["erro"] == D("0.0037295")
    assert m.texto_decimal(r["media"]) == "6.0787295"


def test_sem_erro_de_ponto_flutuante():
    r = m.calcular_ponto(D("0.3"), [D("0.1"), D("0.5")], D("0.001"))
    assert r["erro"] == D("0.0")


def test_limite_exato_esta_dentro():
    assert m.classificar(D("0.002"), D("0.002")) == m.DENTRO
    assert m.classificar(D("-0.002"), D("0.002")) == m.DENTRO


def test_acima_do_limite_esta_fora():
    assert m.classificar(D("0.0020001"), D("0.002")) == m.FORA
    assert m.classificar(D("-0.0021"), D("0.002")) == m.FORA


def test_parecer_aprovado_somente_se_todos_dentro():
    assert m.parecer_final([m.DENTRO, m.DENTRO]) == m.APROVADO
    assert m.parecer_final([m.DENTRO, m.FORA, m.DENTRO]) == m.REPROVADO


def test_parecer_sem_pontos_levanta_erro():
    with pytest.raises(ValueError):
        m.parecer_final([])


def test_arredondamento_apenas_na_apresentacao():
    assert m.arredondar(D("0.00005"), 4) == D("0.0001")
    assert m.arredondar(D("0.00004999"), 4) == D("0.0000")
