import hashlib
import json
import sqlite3
import time

import pytest

from app.amostras import PONTOS_REPROVADO, gerar_xlsx
from app.pdfgen import detectar_marcadores


def banco(app):
    con = sqlite3.connect(app.config["DATABASE"])
    con.row_factory = sqlite3.Row
    return con


def test_rotas_exigem_autenticacao(app):
    c = app.test_client()
    assert c.get("/").status_code == 302
    assert c.get("/calibracoes/1").status_code == 302


def test_login_invalido_e_registrado(app, login):
    cli = login("executor1")
    assert cli.get("/").status_code == 200
    from tests.conftest import Cliente
    ruim = Cliente(app)
    ruim.entrar("executor1", "errada")
    assert ruim.get("/").status_code == 302
    acoes = [r["acao"] for r in banco(app).execute("SELECT acao FROM auditoria")]
    assert "LOGIN_OK" in acoes and "LOGIN_FALHA" in acoes


def test_csrf_obrigatorio(app):
    c = app.test_client()
    assert c.post("/login", data={"login": "executor1", "senha": "senha123"}).status_code == 400


def test_upload_valido_calcula_e_aguarda_analise(app, login, xlsx):
    ex = login("executor1")
    r = ex.enviar(xlsx())
    assert r.status_code == 302
    pg = ex.get(r.headers["Location"]).get_data(as_text=True)
    assert "AGUARDANDO_ANALISE" in pg and "APROVADO" in pg and "DENTRO_DA_TOLERANCIA" in pg
    p = banco(app).execute("SELECT * FROM pontos WHERE ordem=1").fetchone()
    assert p["media"] == "5.0008" and p["erro"] == "0.0008"
    assert json.loads(p["leituras"]) == ["5.001", "5.0006"]


def test_upload_reprovado(app, login, xlsx):
    ex = login("executor1")
    ex.enviar(xlsx(pontos=PONTOS_REPROVADO))
    cal = banco(app).execute("SELECT parecer FROM calibracoes").fetchone()
    assert cal["parecer"] == "REPROVADO"
    classes = [r[0] for r in banco(app).execute("SELECT classificacao FROM pontos ORDER BY ordem")]
    assert classes == ["DENTRO_DA_TOLERANCIA", "DENTRO_DA_TOLERANCIA", "FORA_DA_TOLERANCIA", "DENTRO_DA_TOLERANCIA"]


def test_sufixo_teste_recusado_e_registrado(app, login, xlsx):
    ex = login("executor1")
    r = ex.enviar(xlsx(meta={"Plano de medição": "703.1208_TESTE"}))
    assert r.status_code == 422 and "RN10" in r.get_data(as_text=True)
    con = banco(app)
    assert con.execute("SELECT COUNT(*) FROM calibracoes").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM rejeicoes").fetchone()[0] == 1


def test_padrao_divergente_recusado(app, login, xlsx):
    r = login("executor1").enviar(xlsx(), padrao_id=2)
    assert r.status_code == 422 and "RN03" in r.get_data(as_text=True)


def test_extensao_invalida_recusada(app, login, xlsx):
    r = login("executor1").enviar(xlsx(), nome="calibracao.xls")
    assert r.status_code == 422


def test_arquivo_duplicado_recusado(app, login, xlsx):
    ex = login("executor1")
    arq = xlsx()
    assert ex.enviar(arq).status_code == 302
    r = ex.enviar(arq)
    assert r.status_code == 422 and "DUP" in r.get_data(as_text=True)


def test_desvio_informado_divergente_gera_aviso(app, login, xlsx):
    ex = login("executor1")
    ex.enviar(xlsx(coluna_desvio=[0.0008, 0.0014, 0.0002, 0.9999]))
    avisos = json.loads(banco(app).execute("SELECT avisos FROM calibracoes").fetchone()[0])
    assert any("P4" in a and "diverge" in a for a in avisos)
    assert len(avisos) == 1


def test_padrao_vencido_gera_aviso(app, login, xlsx):
    ex = login("executor1")
    # padrao 500011 vence em 2026-08-31: medicao em 13/08 nao gera aviso; em 15/09 gera
    ex.enviar(xlsx(meta={"Padrão do relatório": "500011"}), padrao_id=2)
    ex.enviar(xlsx(meta={"Padrão do relatório": "500011", "Data da medição": "15/09/2026"}), padrao_id=2)
    linhas = [json.loads(r[0]) for r in banco(app).execute("SELECT avisos FROM calibracoes ORDER BY id")]
    assert not any("RN04" in a for a in linhas[0])
    assert any("RN04" in a for a in linhas[1])


def test_executor_nao_finaliza_por_perfil(app, login, xlsx):
    ex = login("executor1")
    ex.enviar(xlsx())
    assert ex.post("/calibracoes/1/finalizar").status_code == 303
    assert banco(app).execute("SELECT status FROM calibracoes").fetchone()[0] == "AGUARDANDO_ANALISE"


def test_segregacao_de_funcoes_mesmo_usuario(app, login, xlsx):
    em = login("emissor1")
    em.enviar(xlsx())
    r = em.post("/calibracoes/1/finalizar", follow_redirects=True)
    assert "RN09" in r.get_data(as_text=True)
    assert banco(app).execute("SELECT COUNT(*) FROM certificados").fetchone()[0] == 0


def test_finalizacao_gera_numero_pdf_e_imutabilidade(app, login, xlsx):
    login("executor1").enviar(xlsx())
    em = login("emissor1")
    r = em.post("/calibracoes/1/finalizar", follow_redirects=True)
    assert "Certificado 00001/" in r.get_data(as_text=True)
    con = banco(app)
    cert = con.execute("SELECT * FROM certificados").fetchone()
    assert cert["numero"].startswith("00001/")
    pdf = em.get("/calibracoes/1/certificado.pdf")
    assert pdf.status_code == 200 and pdf.data[:4] == b"%PDF"
    assert hashlib.sha256(pdf.data).hexdigest() == cert["pdf_sha256"]
    assert em.post("/calibracoes/1/finalizar").status_code == 303
    for sql in ("UPDATE certificados SET numero='X'", "DELETE FROM certificados",
                "UPDATE calibracoes SET parecer='REPROVADO'", "DELETE FROM calibracoes",
                "UPDATE pontos SET erro='0'", "DELETE FROM pontos"):
        with pytest.raises(sqlite3.DatabaseError):
            con.execute(sql)


def test_pdf_sem_marcadores_de_preenchimento(app, login, xlsx):
    from pypdf import PdfReader
    login("executor1").enviar(xlsx())
    em = login("emissor1")
    em.post("/calibracoes/1/finalizar")
    pdf = em.get("/calibracoes/1/certificado.pdf").data
    import io
    texto = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
    assert detectar_marcadores(texto) == []
    assert "APROVADO" in texto and "Parecer final" in texto


def test_marcador_xx_bloqueia_emissao(app, login, xlsx):
    login("executor1").enviar(xlsx(meta={"Denominação": "Micrômetro XX"}))
    em = login("emissor1")
    r = em.post("/calibracoes/1/finalizar", follow_redirects=True)
    assert "RN06" in r.get_data(as_text=True)
    con = banco(app)
    assert con.execute("SELECT COUNT(*) FROM certificados").fetchone()[0] == 0
    assert con.execute("SELECT ultimo FROM contador_certificados").fetchall() == []
    import pathlib
    assert not list(pathlib.Path(app.config["CERT_DIR"]).glob("*.pdf"))


def test_detector_de_marcadores():
    assert detectar_marcadores("fator k igual a XX e veff YY") == ["XX", "YY"]
    assert detectar_marcadores("Nome {{campo}}") == ["{{ }}"]
    assert detectar_marcadores("Instrumento MP-0042 k = 2,00") == []


def test_numeracao_sequencial_unica(app, login, xlsx):
    ex, em = login("executor1"), login("emissor1")
    for i in range(3):
        ex.enviar(xlsx(pontos=[("P1", 1.0, [1.0 + i / 1000, 1.0], 0.1)]))
        em.post(f"/calibracoes/{i + 1}/finalizar")
    nums = [r[0] for r in banco(app).execute("SELECT numero FROM certificados ORDER BY id")]
    assert [n.split("/")[0] for n in nums] == ["00001", "00002", "00003"]


def test_devolucao_exige_justificativa(app, login, xlsx):
    login("executor1").enviar(xlsx())
    em = login("emissor1")
    r = em.post("/calibracoes/1/devolver", data={"justificativa": " "}, follow_redirects=True)
    assert "Justificativa obrigatória" in r.get_data(as_text=True)
    em.post("/calibracoes/1/devolver", data={"justificativa": "Conferir leitura P3"})
    row = banco(app).execute("SELECT status, justificativa_devolucao FROM calibracoes").fetchone()
    assert row["status"] == "DEVOLVIDO" and row["justificativa_devolucao"] == "Conferir leitura P3"
    assert em.post("/calibracoes/1/finalizar").status_code == 303


def test_auditor_somente_consulta(app, login, xlsx):
    login("executor1").enviar(xlsx())
    au = login("auditor1")
    assert au.get("/calibracoes/1").status_code == 200
    assert au.get("/calibracoes/nova").status_code == 403
    assert au.post("/calibracoes/1/finalizar").status_code == 303


def test_cadastro_de_padroes_somente_admin(app, login):
    dados = {"codigo": "600001", "denominacao": "Padrao teste", "numero_serie": "S1", "certificado": "C1",
             "ultima": "2026-01-01", "proxima": "2027-01-01"}
    assert login("executor1").post("/padroes", data=dados).status_code == 403
    login("admin").post("/padroes", data=dados)
    assert banco(app).execute("SELECT COUNT(*) FROM padroes WHERE codigo='600001'").fetchone()[0] == 1
    ruim = dict(dados, codigo="600002", proxima="2025-01-01")
    login("admin").post("/padroes", data=ruim)
    assert banco(app).execute("SELECT COUNT(*) FROM padroes WHERE codigo='600002'").fetchone()[0] == 0


def test_pesquisa_por_instrumento_status_e_numero(app, login, xlsx):
    ex, em = login("executor1"), login("emissor1")
    ex.enviar(xlsx())
    ex.enviar(xlsx(meta={"Instrumento": "PQ-7"}))
    em.post("/calibracoes/1/finalizar")
    html = em.get("/?instrumento=PQ").get_data(as_text=True)
    assert "PQ-7" in html and "MP-0042" not in html
    assert "MP-0042" in em.get("/?status=FINALIZADO").get_data(as_text=True)
    assert "PQ-7" not in em.get("/?status=FINALIZADO").get_data(as_text=True)
    assert "MP-0042" in em.get("/?numero=00001").get_data(as_text=True)


def test_download_exige_autenticacao_e_valida_hash(app, login, xlsx):
    login("executor1").enviar(xlsx())
    em = login("emissor1")
    em.post("/calibracoes/1/finalizar")
    assert app.test_client().get("/calibracoes/1/certificado.pdf").status_code == 302
    import pathlib
    pdf = next(pathlib.Path(app.config["CERT_DIR"]).glob("*.pdf"))
    pdf.write_bytes(pdf.read_bytes() + b"x")
    assert em.get("/calibracoes/1/certificado.pdf").status_code == 409


def test_tempo_de_processamento_abaixo_de_dez_segundos(app, login, xlsx):
    ex, em = login("executor1"), login("emissor1")
    t0 = time.perf_counter()
    ex.enviar(xlsx())
    em.post("/calibracoes/1/finalizar")
    assert time.perf_counter() - t0 < 10
