"""Ponto de entrada da aplicacao (AV05) - API backend + interface web do MVP Schulz.

Uso normal (feito pelo iniciar_aplicacao_schulz.bat):
    python app.py                     servidor em http://127.0.0.1:5000
    python app.py --rede              aceita conexoes da rede local; o QR Code dos certificados
                                      passa a apontar para o IP da maquina (validacao pelo celular)
    python app.py --abrir-navegador   abre o navegador padrao quando o servidor estiver pronto

Utilitarios usados pelo script .bat:
    python app.py --porta-livre 5000              imprime a primeira porta livre a partir de 5000
    python app.py --aguardar URL --timeout 90     espera a URL responder (codigo de saida 0 = pronto)

Observacao: o pacote ``app/`` (codigo da aplicacao) convive com este arquivo. Ao executar
``python app.py``, o comando ``from app import create_app`` importa o PACOTE ``app/``, porque o
Python da preferencia a um diretorio de pacote sobre um modulo de mesmo nome.
"""
import argparse
import os
import secrets
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

VERSAO_MINIMA = (3, 10)
RAIZ = os.path.dirname(os.path.abspath(__file__))


def porta_ocupada(porta, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        if s.connect_ex((host, porta)) == 0:
            return True
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", porta))
        except OSError:
            return True
    return False


def porta_livre(inicio):
    for porta in range(inicio, inicio + 50):
        if not porta_ocupada(porta):
            return porta
    raise SystemExit("Nenhuma porta livre encontrada entre %d e %d." % (inicio, inicio + 49))


def ip_rede_local():
    """IP da interface usada para sair da maquina (nenhum pacote e enviado)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def aguardar(url, timeout):
    limite = time.time() + timeout
    while time.time() < limite:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def chave_secreta(instance_dir):
    """SECRET_KEY do ambiente ou gerada uma vez e guardada em instance/.secret_key."""
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    os.makedirs(instance_dir, exist_ok=True)
    caminho = os.path.join(instance_dir, ".secret_key")
    if not os.path.exists(caminho):
        with open(caminho, "w", encoding="ascii") as f:
            f.write(secrets.token_hex(32))
    with open(caminho, encoding="ascii") as f:
        return f.read().strip()


def main(argv=None):
    p = argparse.ArgumentParser(description="MVP Schulz - certificados de calibracao (AV05)")
    p.add_argument("--porta", type=int, default=int(os.environ.get("PORTA", "5000")))
    p.add_argument("--rede", action="store_true", help="escuta em 0.0.0.0 e usa o IP da rede no QR Code")
    p.add_argument("--abrir-navegador", action="store_true")
    p.add_argument("--porta-livre", type=int, metavar="INICIO")
    p.add_argument("--aguardar", metavar="URL")
    p.add_argument("--timeout", type=float, default=90)
    p.add_argument("--pausar-em-erro", action="store_true",
                   help="mantem a janela aberta se o servidor falhar (usado pelo .bat)")
    a = p.parse_args(argv)

    if sys.version_info < VERSAO_MINIMA:
        raise SystemExit("Python %d.%d ou superior e necessario (encontrado %s)."
                         % (VERSAO_MINIMA + (sys.version.split()[0],)))
    if a.porta_livre is not None:
        print(porta_livre(a.porta_livre))
        return 0
    if a.aguardar:
        return 0 if aguardar(a.aguardar, a.timeout) else 1

    instance = os.environ.get("INSTANCE_DIR", os.path.join(RAIZ, "instance"))
    os.environ.setdefault("INSTANCE_DIR", instance)
    os.environ["SECRET_KEY"] = chave_secreta(instance)
    host = "0.0.0.0" if a.rede else "127.0.0.1"
    url_local = "http://127.0.0.1:%d/" % a.porta
    config = {}
    if a.rede:
        config["URL_PUBLICA"] = "http://%s:%d" % (ip_rede_local(), a.porta)
    elif os.environ.get("URL_PUBLICA"):
        config["URL_PUBLICA"] = os.environ["URL_PUBLICA"]

    sys.path.insert(0, RAIZ)
    from app import create_app  # pacote app/ (ver docstring)

    aplicacao = create_app(config)
    print("=" * 64)
    print(" MVP Schulz - Certificados de Calibracao (API backend + interface web)")
    print(" Interface:  %s" % url_local)
    print(" API:        %sapi/status" % url_local)
    if a.rede:
        print(" Rede local: %s/  (QR Code aponta para este endereco)" % config["URL_PUBLICA"])
    print(" Banco:      %s" % aplicacao.config["DATABASE"])
    print(" Para encerrar: feche esta janela ou pressione Ctrl+C.")
    print("=" * 64, flush=True)

    if a.abrir_navegador:
        def abrir():
            if aguardar(url_local + "api/status", a.timeout):
                webbrowser.open(url_local)
        threading.Thread(target=abrir, daemon=True).start()

    aplicacao.run(host=host, port=a.porta, debug=False, use_reloader=False, threaded=True)
    return 0


def executar():
    pausar = "--pausar-em-erro" in sys.argv
    try:
        return main()
    except KeyboardInterrupt:
        return 0
    except BaseException as e:  # mostra o erro antes de a janela do .bat fechar
        if pausar:
            import traceback
            if not isinstance(e, SystemExit) or e.code not in (0, None):
                traceback.print_exc()
                input("\nO servidor foi encerrado com erro. Pressione Enter para fechar esta janela...")
        raise


if __name__ == "__main__":
    sys.exit(executar())
