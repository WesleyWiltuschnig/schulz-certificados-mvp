"""Executa um cenario real contra a aplicacao e grava evidencias em docs/evidencias/.

Saidas: log_cenario.txt, desempenho.txt, certificado_exemplo.pdf, paginas HTML e PNG (se wkhtmltoimage existir).
"""
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from app import create_app  # noqa: E402
from app.amostras import PONTOS_REPROVADO, gerar_xlsx  # noqa: E402
from tests.conftest import Cliente  # noqa: E402

SAIDA = os.path.join(RAIZ, "docs", "evidencias")
os.makedirs(SAIDA, exist_ok=True)
tmp = tempfile.mkdtemp()
app = create_app({"DATABASE": tmp + "/e.db", "INSTANCE_DIR": tmp, "UPLOAD_DIR": tmp + "/up",
                  "CERT_DIR": tmp + "/cert", "SECRET_KEY": "evidencias"})
css = open(os.path.join(RAIZ, "app", "static", "style.css"), encoding="utf-8").read()
log = []


def reg(passo, resultado):
    linha = f"{passo}: {resultado}"
    log.append(linha)
    print(linha)


def snapshot(nome, html):
    html = html.replace('<link rel="stylesheet" href="/static/style.css">', f"<style>{css}</style>")
    caminho = os.path.join(SAIDA, nome + ".html")
    open(caminho, "w", encoding="utf-8").write(html)
    if shutil.which("wkhtmltoimage"):
        subprocess.run(["wkhtmltoimage", "--quiet", "--width", "1150", caminho, os.path.join(SAIDA, nome + ".png")],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


ex, em, au = Cliente(app), Cliente(app), Cliente(app)
ex.entrar("executor1"); em.entrar("emissor1"); au.entrar("auditor1")
snapshot("01_lista_vazia", ex.get("/").get_data(as_text=True))

arq_aprovada = gerar_xlsx()
r = ex.enviar(arq_aprovada)
reg("Upload planilha valida (aprovada)", f"HTTP {r.status_code} -> {r.headers.get('Location')}")
snapshot("02_detalhe_aprovada", ex.get(r.headers["Location"]).get_data(as_text=True))

r = ex.enviar(gerar_xlsx(pontos=PONTOS_REPROVADO, meta={"Instrumento": "MP-0043"}))
reg("Upload planilha valida (reprovada)", f"HTTP {r.status_code} -> {r.headers.get('Location')}")
snapshot("03_detalhe_reprovada", ex.get(r.headers["Location"]).get_data(as_text=True))

r = ex.enviar(gerar_xlsx(meta={"Plano de medição": "703.1208_TESTE"}))
reg("Upload plano com sufixo TESTE", f"HTTP {r.status_code} (esperado 422)")
snapshot("04_recusa_teste", r.get_data(as_text=True))
r = ex.enviar(gerar_xlsx(meta={"Padrão do relatório": "500011"}))
reg("Upload com padrao divergente", f"HTTP {r.status_code} (esperado 422)")
r = ex.enviar(gerar_xlsx(n_leituras=1))
reg("Upload com um bloco de leituras", f"HTTP {r.status_code} (esperado 422)")
r = ex.enviar(arq_aprovada)
reg("Reenvio do mesmo arquivo", f"HTTP {r.status_code} (esperado 422)")

r = ex.post("/calibracoes/1/finalizar")
reg("Executor tenta finalizar", f"HTTP {r.status_code}; situacao permanece AGUARDANDO_ANALISE")
em.enviar(gerar_xlsx(meta={"Instrumento": "MP-0099"}))
r = em.post("/calibracoes/3/finalizar", follow_redirects=True)
reg("Emissor tenta finalizar o que ele mesmo elaborou", "bloqueado (RN09)" if "RN09" in r.get_data(as_text=True) else "FALHA")
r = em.post("/calibracoes/1/finalizar", follow_redirects=True)
reg("Emissor finaliza calibracao do executor", "certificado 00001 emitido" if "Certificado 00001/" in r.get_data(as_text=True) else "FALHA")
snapshot("05_detalhe_finalizado", em.get("/calibracoes/1").get_data(as_text=True))
r = em.post("/calibracoes/2/devolver", data={"justificativa": "Reconferir leituras do ponto P3"})
reg("Devolucao com justificativa", f"HTTP {r.status_code}")
pdf = em.get("/calibracoes/1/certificado.pdf")
reg("Download do PDF", f"HTTP {pdf.status_code}, {len(pdf.data)} bytes, inicio {pdf.data[:5]!r}")
open(os.path.join(SAIDA, "certificado_exemplo.pdf"), "wb").write(pdf.data)
reg("Download sem login", f"HTTP {app.test_client().get('/calibracoes/1/certificado.pdf').status_code} (esperado 302)")
snapshot("06_lista_final", au.get("/").get_data(as_text=True))
snapshot("07_lista_filtrada", au.get("/?status=FINALIZADO").get_data(as_text=True))

con = sqlite3.connect(app.config["DATABASE"])
try:
    con.execute("UPDATE certificados SET numero='00099/2026'")
    reg("UPDATE direto em certificado finalizado", "FALHA: permitido")
except sqlite3.DatabaseError as e:
    reg("UPDATE direto em certificado finalizado", f"bloqueado pelo banco ({e})")

reg("Rejeicoes registradas", con.execute("SELECT COUNT(*) FROM rejeicoes").fetchone()[0])
reg("Eventos de auditoria", con.execute("SELECT COUNT(*) FROM auditoria").fetchone()[0])
open(os.path.join(SAIDA, "log_cenario.txt"), "w", encoding="utf-8").write("\n".join(log) + "\n")

# Desempenho (dados sinteticos): importacao + finalizacao de N calibracoes
N = 50
app2 = create_app({"DATABASE": tmp + "/p.db", "INSTANCE_DIR": tmp, "UPLOAD_DIR": tmp + "/up2",
                   "CERT_DIR": tmp + "/cert2", "SECRET_KEY": "perf"})
ex2, em2 = Cliente(app2), Cliente(app2)
ex2.entrar("executor1"); em2.entrar("emissor1")
t_imp, t_fin = [], []
for i in range(N):
    pontos = [(f"P{k}", float(k), [k + 0.0001 * i, k + 0.0001], 0.5) for k in range(1, 15)]  # 14 parametros
    arq = gerar_xlsx(meta={"Instrumento": f"SINT-{i:04d}"}, pontos=pontos)
    t = time.perf_counter(); ex2.enviar(arq); t_imp.append(time.perf_counter() - t)
    t = time.perf_counter(); em2.post(f"/calibracoes/{i + 1}/finalizar"); t_fin.append(time.perf_counter() - t)
con2 = sqlite3.connect(app2.config["DATABASE"])
numeros = [r[0] for r in con2.execute("SELECT numero FROM certificados ORDER BY id")]
unicos = len(set(numeros)) == len(numeros) == N
txt = (f"Calibracoes sinteticas processadas: {N} (14 pontos cada)\n"
       f"Importacao+calculo: media {sum(t_imp)/N*1000:.0f} ms, maximo {max(t_imp)*1000:.0f} ms\n"
       f"Finalizacao+PDF: media {sum(t_fin)/N*1000:.0f} ms, maximo {max(t_fin)*1000:.0f} ms\n"
       f"Numeracao sequencial sem lacunas/duplicatas: {unicos} ({numeros[0]} a {numeros[-1]})\n"
       "Observacao: medicao em processo unico, SQLite local; nao representa a AWS.\n")
open(os.path.join(SAIDA, "desempenho.txt"), "w", encoding="utf-8").write(txt)
print(txt)
