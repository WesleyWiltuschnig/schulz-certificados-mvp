"""AV05 - Modulo de Emissao e Rastreabilidade: QR Code de validacao mobile e API de status."""
import io
import os
import pathlib
import sqlite3
import subprocess
import sys

from pypdf import PdfReader

from app import create_app
from app.validacao import codigo_valido, desenho_qr, gerar_codigo, svg_qr, url_validacao
from tests.conftest import Cliente

RAIZ = pathlib.Path(__file__).resolve().parents[1]


def banco(app):
    con = sqlite3.connect(app.config["DATABASE"])
    con.row_factory = sqlite3.Row
    return con


def emitir(app, login, xlsx, **meta):
    login("executor1").enviar(xlsx(meta=meta or None))
    em = login("emissor1")
    em.post("/calibracoes/1/finalizar")
    cert = banco(app).execute("SELECT * FROM certificados").fetchone()
    return em, cert


def texto_pdf(dados):
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(dados)).pages)


def test_codigo_de_validacao_aleatorio_e_formato():
    codigos = {gerar_codigo() for _ in range(200)}
    assert len(codigos) == 200
    assert all(codigo_valido(c) and len(c) == 16 for c in codigos)
    assert not codigo_valido("../etc/passwd") and not codigo_valido("abc") and not codigo_valido("")
    assert url_validacao("http://10.0.0.5:5000/", "abcDEF123_-xyz00") == "http://10.0.0.5:5000/validar/abcDEF123_-xyz00"


def test_qr_gera_desenho_e_svg():
    assert desenho_qr("http://exemplo/validar/x", lado=80).width == 80
    svg = svg_qr("http://exemplo/validar/x", lado=120)
    assert svg.startswith("<svg") and "</svg>" in svg


def test_finalizacao_grava_codigo_e_imprime_qr_no_pdf(app, login, xlsx):
    em, cert = emitir(app, login, xlsx)
    assert codigo_valido(cert["codigo_validacao"])
    texto = texto_pdf(em.get("/calibracoes/1/certificado.pdf").data)
    assert f"Código de validação: {cert['codigo_validacao']}" in texto
    assert f"/validar/{cert['codigo_validacao']}" in texto
    assert "Validação mobile" in texto


def test_qr_usa_url_publica_configurada(tmp_path, xlsx):
    app = create_app({"DATABASE": str(tmp_path / "t.db"), "INSTANCE_DIR": str(tmp_path),
                      "UPLOAD_DIR": str(tmp_path / "up"), "CERT_DIR": str(tmp_path / "cert"),
                      "TESTING": True, "SECRET_KEY": "t", "URL_PUBLICA": "http://192.168.0.50:5000"})
    ex, em = Cliente(app), Cliente(app)
    ex.entrar("executor1"); em.entrar("emissor1")
    ex.enviar(xlsx())
    em.post("/calibracoes/1/finalizar")
    texto = texto_pdf(em.get("/calibracoes/1/certificado.pdf").data)
    assert "http://192.168.0.50:5000/validar/" in texto


def test_detalhe_mostra_qr_e_link(app, login, xlsx):
    em, cert = emitir(app, login, xlsx)
    html = em.get("/calibracoes/1").get_data(as_text=True)
    assert "<svg" in html and f"/validar/{cert['codigo_validacao']}" in html


def test_validacao_publica_sem_login(app, login, xlsx):
    _, cert = emitir(app, login, xlsx)
    anonimo = app.test_client()
    r = anonimo.get(f"/validar/{cert['codigo_validacao']}")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert cert["numero"] in html and "APROVADO" in html and "MP-0042" in html
    assert "Confere com o hash registrado" in html
    assert "SHA-256 da planilha" not in html  # nao expoe dados internos de origem
    acoes = [a["acao"] for a in banco(app).execute("SELECT acao FROM auditoria WHERE calibracao_id=1")]
    assert "CERTIFICADO_VALIDADO" in acoes


def test_codigo_inexistente_ou_invalido(app):
    c = app.test_client()
    assert c.get("/validar/CodigoQueNaoExiste01").status_code == 404
    assert c.get("/validar/x").status_code == 404
    assert c.get("/api/validar/CodigoQueNaoExiste01").get_json() == {
        "valido": False, "motivo": "codigo de validacao nao encontrado"}


def test_formulario_manual_redireciona(app, login, xlsx):
    _, cert = emitir(app, login, xlsx)
    c = app.test_client()
    assert c.get("/validar").status_code == 200
    r = c.get(f"/validar?codigo={cert['codigo_validacao']}")
    assert r.status_code == 302 and r.headers["Location"].endswith(f"/validar/{cert['codigo_validacao']}")


def test_conferir_pdf_original_e_alterado(app, login, xlsx):
    em, cert = emitir(app, login, xlsx)
    original = em.get("/calibracoes/1/certificado.pdf").data
    anonimo = Cliente(app)
    url = f"/validar/{cert['codigo_validacao']}/conferir"
    anonimo.get(f"/validar/{cert['codigo_validacao']}")
    ok = anonimo.post(url, data={"pdf": (io.BytesIO(original), "cert.pdf")}, content_type="multipart/form-data")
    assert "idêntico ao certificado emitido" in ok.get_data(as_text=True)
    ruim = anonimo.post(url, data={"pdf": (io.BytesIO(original + b"%"), "cert.pdf")},
                        content_type="multipart/form-data")
    assert "NÃO é idêntico" in ruim.get_data(as_text=True)
    detalhes = [a["detalhe"] for a in banco(app).execute("SELECT detalhe FROM auditoria WHERE acao='PDF_CONFERIDO'")]
    assert detalhes == ["confere", "DIVERGENTE"]


def test_validacao_aponta_pdf_adulterado_no_servidor(app, login, xlsx):
    _, cert = emitir(app, login, xlsx)
    pdf = next(pathlib.Path(app.config["CERT_DIR"]).glob("*.pdf"))
    pdf.write_bytes(pdf.read_bytes() + b"x")
    html = app.test_client().get(f"/validar/{cert['codigo_validacao']}").get_data(as_text=True)
    assert "ATENÇÃO" in html and "DIVERGENTE" in html
    assert app.test_client().get(f"/api/validar/{cert['codigo_validacao']}").get_json()["valido"] is False


def test_api_validar_json(app, login, xlsx):
    _, cert = emitir(app, login, xlsx)
    j = app.test_client().get(f"/api/validar/{cert['codigo_validacao']}").get_json()
    assert j["valido"] is True and j["numero"] == cert["numero"] and j["parecer"] == "APROVADO"
    assert j["integridade_pdf"] == "confere" and len(j["pontos"]) == 4
    assert {p["classificacao"] for p in j["pontos"]} == {"DENTRO_DA_TOLERANCIA"}


def test_api_status_publica(app):
    j = app.test_client().get("/api/status").get_json()
    assert j == {"status": "ok", "projeto": "Schulz Certificados MVP", "versao": "AV05"}


def test_migracao_de_banco_sem_coluna_de_validacao(tmp_path):
    caminho = tmp_path / "antigo.db"
    con = sqlite3.connect(caminho)
    con.execute("CREATE TABLE certificados(id INTEGER PRIMARY KEY, calibracao_id INTEGER NOT NULL, versao INTEGER "
                "NOT NULL DEFAULT 1, numero TEXT UNIQUE NOT NULL, arquivo TEXT NOT NULL, pdf_sha256 TEXT NOT NULL, "
                "finalizado_por INTEGER NOT NULL, finalizado_em TEXT NOT NULL)")
    con.execute("INSERT INTO certificados VALUES(1,1,1,'00001/2026','a.pdf','x',2,'2026-10-26')")
    con.commit(); con.close()
    create_app({"DATABASE": str(caminho), "INSTANCE_DIR": str(tmp_path), "SECRET_KEY": "t"})
    con = sqlite3.connect(caminho)
    colunas = {r[1] for r in con.execute("PRAGMA table_info(certificados)")}
    assert "codigo_validacao" in colunas
    assert con.execute("SELECT numero FROM certificados").fetchone()[0] == "00001/2026"


def test_app_py_utilitarios_do_bat():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(RAIZ / "app.py"), "--porta-livre", "5000"],
                       capture_output=True, text=True, env=env, cwd=RAIZ, timeout=30)
    assert r.returncode == 0 and int(r.stdout.strip()) >= 5000
    r = subprocess.run([sys.executable, str(RAIZ / "app.py"), "--aguardar", "http://127.0.0.1:9/api/status",
                        "--timeout", "1"], capture_output=True, text=True, env=env, cwd=RAIZ, timeout=30)
    assert r.returncode == 1
