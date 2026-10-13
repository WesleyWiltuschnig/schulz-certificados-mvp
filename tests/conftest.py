import io
import pytest

from app import create_app
from app.amostras import gerar_xlsx


@pytest.fixture()
def app(tmp_path):
    return create_app({"DATABASE": str(tmp_path / "t.db"), "INSTANCE_DIR": str(tmp_path),
                       "UPLOAD_DIR": str(tmp_path / "up"), "CERT_DIR": str(tmp_path / "cert"),
                       "TESTING": True, "SECRET_KEY": "teste"})


class Cliente:
    def __init__(self, app):
        self.c = app.test_client()

    def token(self):
        with self.c.session_transaction() as s:
            return s.setdefault("csrf", "tok-teste")

    def entrar(self, login, senha="senha123"):
        self.token()
        return self.c.post("/login", data={"login": login, "senha": senha, "csrf": self.token()})

    def post(self, url, data=None, **kw):
        d = dict(data or {})
        d["csrf"] = self.token()
        return self.c.post(url, data=d, **kw)

    def enviar(self, conteudo, padrao_id=1, nome="calibracao.xlsx"):
        return self.post("/calibracoes/nova", data={"padrao_id": padrao_id, "planilha": (io.BytesIO(conteudo), nome)},
                         content_type="multipart/form-data")

    def get(self, url, **kw):
        return self.c.get(url, **kw)


@pytest.fixture()
def login(app):
    def _login(usuario):
        cli = Cliente(app)
        cli.entrar(usuario)
        return cli
    return _login


@pytest.fixture()
def xlsx():
    return gerar_xlsx
