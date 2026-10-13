import json
import os
import secrets
from decimal import Decimal

from flask import Flask

from .db import close_db, init_db
from .metrologia import arredondar


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=False)
    instance = os.environ.get("INSTANCE_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "instance"))
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-nao-usar-em-producao"),
        INSTANCE_DIR=instance,
        DATABASE=os.path.join(instance, "mvp.sqlite3"),
        UPLOAD_DIR=os.path.join(instance, "uploads"),
        CERT_DIR=os.path.join(instance, "certificados"),
        SENHA_DEMO=os.environ.get("SENHA_DEMO", "senha123"),
        MAX_CONTENT_LENGTH=6 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if config:
        app.config.update(config)
        if "DATABASE" in config and "INSTANCE_DIR" in config:
            app.config.setdefault("UPLOAD_DIR", os.path.join(config["INSTANCE_DIR"], "uploads"))
    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    init_db(app)
    app.teardown_appcontext(close_db)

    @app.template_filter("fmt")
    def fmt(valor, casas=4):
        return str(arredondar(Decimal(valor), casas)).replace(".", ",")

    @app.template_filter("data_br")
    def data_br(iso):
        return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}" if iso and len(iso) >= 10 else (iso or "")

    @app.template_filter("lista")
    def lista(texto):
        return json.loads(texto)

    @app.context_processor
    def globais():
        from flask import session
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        return {"csrf_token": session["csrf"]}

    from .views import bp
    app.register_blueprint(bp)
    return app
