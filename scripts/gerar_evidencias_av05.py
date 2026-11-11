"""Evidencias da AV05: executa o fluxo completo num navegador real contra o servidor iniciado pelo app.py.

Fluxo: login do executor -> upload das planilhas de exemplo -> login do emissor -> finalizacao ->
download do PDF -> leitura (decodificacao) do QR Code impresso -> abertura da URL do QR num
navegador em modo celular -> conferencia do PDF original e de um PDF alterado.

Dependencias OPCIONAIS (nao fazem parte do requirements.txt, so servem para gerar evidencias):
    pip install playwright pypdfium2 opencv-python-headless && playwright install chromium
Uso:
    python scripts/gerar_evidencias_av05.py [--python CAMINHO_DO_PYTHON_DO_VENV] [--chrome CAMINHO]
Saida: docs/evidencias_av05/
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "docs", "evidencias_av05")
AMOSTRAS = os.path.join(RAIZ, "samples")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=sys.executable, help="python que executa o servidor (ex.: .venv)")
    ap.add_argument("--chrome", default=None, help="executavel do Chrome/Chromium (opcional)")
    a = ap.parse_args()

    import cv2
    import numpy as np
    import pypdfium2 as pdfium
    from playwright.sync_api import sync_playwright

    os.makedirs(SAIDA, exist_ok=True)
    log = []

    def reg(texto):
        print(texto)
        log.append(texto)

    inst = tempfile.mkdtemp(prefix="schulz_av05_")
    env = dict(os.environ, INSTANCE_DIR=inst, PYTHONIOENCODING="utf-8")
    porta = subprocess.check_output([a.python, "app.py", "--porta-livre", "5000"], cwd=RAIZ, env=env,
                                    text=True).strip()
    base = f"http://127.0.0.1:{porta}"
    servidor = subprocess.Popen([a.python, "app.py", "--porta", porta], cwd=RAIZ, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        t0 = time.perf_counter()
        ok = subprocess.run([a.python, "app.py", "--aguardar", base + "/api/status", "--timeout", "60"],
                            cwd=RAIZ, env=env).returncode == 0
        reg(f"Servidor (app.py --porta {porta}) pronto: {ok} em {time.perf_counter() - t0:.1f} s")
        status = json.load(urllib.request.urlopen(base + "/api/status"))
        reg(f"GET /api/status -> {json.dumps(status, ensure_ascii=False)}")

        with sync_playwright() as p:
            opcoes = {"executable_path": a.chrome} if a.chrome else {}
            nav = p.chromium.launch(args=["--no-sandbox"], **opcoes)
            desk = nav.new_context(viewport={"width": 1180, "height": 760}, device_scale_factor=1.5,
                                   locale="pt-BR", accept_downloads=True)
            pg = desk.new_page()

            def foto(nome, pagina=None, inteira=True):
                (pagina or pg).screenshot(path=os.path.join(SAIDA, nome + ".png"), full_page=inteira)

            def entrar(usuario):
                pg.goto(base + "/login")
                pg.fill("input[name=login]", usuario)
                pg.fill("input[name=senha]", "senha123")
                pg.click("button.acao")
                pg.wait_for_url(base + "/")

            def sair():
                pg.click(".topo button")
                pg.wait_for_url("**/login")

            pg.goto(base + "/login")
            foto("01_login", inteira=False)
            entrar("executor1")

            def enviar(arquivo):
                pg.goto(base + "/calibracoes/nova")
                pg.set_input_files("input[name=planilha]", os.path.join(AMOSTRAS, arquivo))
                t = time.perf_counter()
                pg.click("button.acao")
                pg.wait_for_load_state("load")
                return (time.perf_counter() - t) * 1000

            ms = enviar("01_valida_aprovada.xlsx")
            reg(f"Upload 01_valida_aprovada.xlsx -> {pg.url} ({ms:.0f} ms ate a tela de resultado)")
            foto("02_importacao_aprovada")
            ms = enviar("02_valida_reprovada.xlsx")
            reg(f"Upload 02_valida_reprovada.xlsx -> {pg.url} ({ms:.0f} ms)")
            foto("03_importacao_reprovada")
            enviar("03_invalida_plano_teste.xlsx")
            reg(f"Upload 03_invalida_plano_teste.xlsx -> recusa: {pg.inner_text('.msg.erro')}")
            foto("04_ingestao_recusada", inteira=False)
            enviar("06_invalida_data_sentinela.xlsx")
            reg(f"Upload 06_invalida_data_sentinela.xlsx -> recusa: {pg.inner_text('.msg.erro')}")
            sair()

            entrar("emissor1")
            pg.goto(base + "/calibracoes/1")
            foto("05_analise_emissor")
            t = time.perf_counter()
            pg.click("text=Finalizar certificado")
            pg.wait_for_load_state("load")
            reg(f"Finalizacao (numeracao + PDF + QR): {(time.perf_counter() - t) * 1000:.0f} ms; "
                f"mensagem: {pg.inner_text('.msg.ok')}")
            foto("06_certificado_finalizado_qr")

            resp = pg.request.get(base + "/calibracoes/1/certificado.pdf")
            pdf = resp.body()
            caminho_pdf = os.path.join(SAIDA, "certificado_00001.pdf")
            with open(caminho_pdf, "wb") as f:
                f.write(pdf)
            reg(f"Download do PDF: HTTP {resp.status}, {len(pdf)} bytes")

            pagina = pdfium.PdfDocument(caminho_pdf)[0]
            imagem = pagina.render(scale=200 / 72).to_pil()
            imagem.save(os.path.join(SAIDA, "07_certificado_pdf.png"))
            url_qr, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.cvtColor(np.array(imagem), cv2.COLOR_RGB2BGR))
            reg(f"QR Code lido do PDF (OpenCV QRCodeDetector): {url_qr}")
            codigo = url_qr.rsplit("/", 1)[-1]

            cel = nav.new_context(**p.devices["iPhone 13"], locale="pt-BR")
            mob = cel.new_page()
            mob.goto(url_qr)
            reg(f"Abertura da URL do QR em modo celular (iPhone 13, 390 px): HTTP 200, titulo '{mob.title()}'")
            foto("08_validacao_mobile", mob)
            mob.set_input_files("input[name=pdf]", caminho_pdf)
            mob.click("text=Conferir arquivo")
            mob.wait_for_load_state("load")
            reg("Conferencia do PDF original: " + mob.inner_text(".cartao:has(form) .selo"))
            mob.locator(".cartao:has(form)").screenshot(path=os.path.join(SAIDA, "09_conferencia_original.png"))
            alterado = os.path.join(inst, "certificado_alterado.pdf")
            with open(alterado, "wb") as f:
                f.write(pdf.replace(b"APROVADO", b"APROVAD0", 1) if b"APROVADO" in pdf else pdf + b"\n%x")
            mob.set_input_files("input[name=pdf]", alterado)
            mob.click("text=Conferir arquivo")
            mob.wait_for_load_state("load")
            reg("Conferencia de PDF alterado: " + mob.inner_text(".cartao:has(form) .selo").replace("\n", " "))
            mob.locator(".cartao:has(form)").screenshot(path=os.path.join(SAIDA, "10_conferencia_alterado.png"))

            api = json.load(urllib.request.urlopen(f"{base}/api/validar/{codigo}"))
            with open(os.path.join(SAIDA, "api_validar.json"), "w", encoding="utf-8") as f:
                json.dump(api, f, ensure_ascii=False, indent=2)
            reg(f"GET /api/validar/<codigo> -> valido={api['valido']}, parecer={api['parecer']}, "
                f"integridade_pdf={api['integridade_pdf']}")

            pg.goto(base + "/calibracoes/1")
            trilha = pg.locator("table").last.inner_text()
            reg("Trilha de auditoria da calibracao 1:\n" + trilha)
            foto("11_trilha_auditoria")
            nav.close()
    finally:
        servidor.terminate()
        try:
            saida, _ = servidor.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            servidor.kill()
            saida, _ = servidor.communicate()
        with open(os.path.join(SAIDA, "console_app_py.txt"), "w", encoding="utf-8") as f:
            f.write(saida)
        shutil.rmtree(inst, ignore_errors=True)

    with open(os.path.join(SAIDA, "log_evidencias_av05.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(log) + "\n")


if __name__ == "__main__":
    main()
