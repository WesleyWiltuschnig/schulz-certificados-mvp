"""Teste de fumaca contra servidor real (HTTP). Uso: python scripts/smoke_http.py http://127.0.0.1:5055"""
import http.cookiejar
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.amostras import gerar_xlsx  # noqa: E402

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000"


class SemRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def sessao():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), SemRedirect)


def req(op, url, dados=None, cabecalhos=None):
    r = urllib.request.Request(base + url, data=dados, headers=cabecalhos or {})
    try:
        resp = op.open(r)
    except urllib.error.HTTPError as e:
        resp = e
    return resp.status if hasattr(resp, "status") else resp.code, resp.headers, resp.read()


def csrf(op, url):
    _, _, corpo = req(op, url)
    return re.search(r'name="csrf" value="([0-9a-f]+)"', corpo.decode()).group(1)


def entrar(login):
    op = sessao()
    tok = csrf(op, "/login")
    st, h, _ = req(op, "/login", urllib.parse.urlencode({"login": login, "senha": "senha123", "csrf": tok}).encode())
    return op, st


def multipart(tok, padrao, nome, conteudo):
    b = uuid.uuid4().hex
    partes = [f'--{b}\r\nContent-Disposition: form-data; name="csrf"\r\n\r\n{tok}\r\n'.encode(),
              f'--{b}\r\nContent-Disposition: form-data; name="padrao_id"\r\n\r\n{padrao}\r\n'.encode(),
              f'--{b}\r\nContent-Disposition: form-data; name="planilha"; filename="{nome}"\r\n'
              "Content-Type: application/octet-stream\r\n\r\n".encode(), conteudo, f"\r\n--{b}--\r\n".encode()]
    return b"".join(partes), {"Content-Type": f"multipart/form-data; boundary={b}"}


def verificar(desc, ok, detalhe=""):
    print(("OK    " if ok else "FALHA ") + desc + (f" [{detalhe}]" if detalhe else ""))
    return ok


res = []
st, _, _ = req(sessao(), "/")
res.append(verificar("GET / sem login redireciona", st == 302, st))
ex, st = entrar("executor1")
res.append(verificar("login do executor", st == 302, st))
corpo, cab = multipart(csrf(ex, "/calibracoes/nova"), 1, "valida.xlsx", gerar_xlsx())
st, h, _ = req(ex, "/calibracoes/nova", corpo, cab)
res.append(verificar("upload de planilha valida", st == 302, h.get("Location")))
cal = h.get("Location")
st, _, html = req(ex, cal)
res.append(verificar("detalhe mostra APROVADO e AGUARDANDO_ANALISE", b"APROVADO" in html and b"AGUARDANDO_ANALISE" in html))
corpo, cab = multipart(csrf(ex, "/calibracoes/nova"), 1, "teste.xlsx", gerar_xlsx(meta={"Plano de medição": "X_TESTE"}))
st, _, html = req(ex, "/calibracoes/nova", corpo, cab)
res.append(verificar("planilha _TESTE recusada (422)", st == 422 and b"RN10" in html, st))
em, _ = entrar("emissor1")
st, _, _ = req(em, cal + "/finalizar", urllib.parse.urlencode({"csrf": csrf(em, cal)}).encode())
res.append(verificar("emissor finaliza (303 redireciona)", st in (302, 303), st))
st, h, pdf = req(em, cal + "/certificado.pdf")
res.append(verificar("download do PDF", st == 200 and pdf[:4] == b"%PDF", f"{st} {len(pdf)} bytes"))
st, _, _ = req(sessao(), cal + "/certificado.pdf")
res.append(verificar("PDF sem login negado", st == 302, st))
st, _, _ = req(ex, cal, urllib.parse.urlencode({"x": 1}).encode())
res.append(verificar("POST sem CSRF rejeitado", st in (400, 405), st))
print(f"\n{sum(res)}/{len(res)} verificacoes passaram")
sys.exit(0 if all(res) else 1)
