import functools
import os
import secrets

from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template,
                   request, send_file, session, url_for, Response)
from werkzeug.security import check_password_hash

from . import amostras, servicos
from .db import get_db
from .ingestao import IngestaoInvalida, limpar_texto

bp = Blueprint("web", __name__)


@bp.before_app_request
def carregar_usuario():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = get_db().execute("SELECT * FROM usuarios WHERE id=? AND ativo=1", (uid,)).fetchone()
    if request.method == "POST":
        token = request.form.get("csrf")
        if not token or not secrets.compare_digest(token, session.get("csrf", "")):
            abort(400, "Token CSRF inválido.")


def requer_papel(*papeis):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            if g.user is None:
                return redirect(url_for("web.login"))
            if papeis and g.user["papel"] not in papeis:
                abort(403)
            return fn(*a, **kw)
        return wrapper
    return deco


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        db = get_db()
        login_ = limpar_texto(request.form.get("login"))
        u = db.execute("SELECT * FROM usuarios WHERE login=? AND ativo=1", (login_,)).fetchone()
        if u and check_password_hash(u["senha_hash"], request.form.get("senha", "")):
            session.clear()
            session["uid"] = u["id"]
            session["csrf"] = secrets.token_hex(16)
            servicos.auditar(db, None, u["id"], "LOGIN_OK", login_)
            return redirect(url_for("web.lista"))
        servicos.auditar(db, None, u["id"] if u else None, "LOGIN_FALHA", login_)
        flash("Usuário ou senha inválidos.", "erro")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("web.login"))


@bp.route("/")
@requer_papel()
def lista():
    db = get_db()
    filtros, params = [], []
    f = {k: limpar_texto(request.args.get(k)) for k in ("instrumento", "numero", "status", "de", "ate")}
    if f["instrumento"]:
        filtros.append("c.instrumento LIKE ?"); params.append(f"%{f['instrumento']}%")
    if f["numero"]:
        filtros.append("ce.numero LIKE ?"); params.append(f"%{f['numero']}%")
    if f["status"]:
        filtros.append("c.status = ?"); params.append(f["status"])
    if f["de"]:
        filtros.append("c.data_medicao >= ?"); params.append(f["de"])
    if f["ate"]:
        filtros.append("c.data_medicao <= ?"); params.append(f["ate"])
    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    linhas = db.execute(
        "SELECT c.*, ce.numero AS numero, u.nome AS executor FROM calibracoes c "
        "JOIN usuarios u ON u.id=c.executor_id LEFT JOIN certificados ce ON ce.calibracao_id=c.id "
        f"{where} ORDER BY c.id DESC LIMIT 200", params).fetchall()
    return render_template("lista.html", linhas=linhas, f=f)


@bp.route("/calibracoes/nova", methods=["GET", "POST"])
@requer_papel(*servicos.PAPEIS_UPLOAD)
def nova():
    db = get_db()
    padroes = db.execute("SELECT * FROM padroes ORDER BY codigo").fetchall()
    erros = []
    if request.method == "POST":
        arq = request.files.get("planilha")
        if not arq or not arq.filename:
            erros = [{"codigo": "ARQ", "mensagem": "Selecione uma planilha .xlsx."}]
        else:
            try:
                cal_id = servicos.importar_planilha(db, g.user, request.form.get("padrao_id", type=int),
                                                    arq.filename, arq.read(), current_app.config["UPLOAD_DIR"])
                flash("Planilha processada. Calibração aguardando análise.", "ok")
                return redirect(url_for("web.detalhe", cal_id=cal_id))
            except IngestaoInvalida as e:
                erros = e.erros
            except servicos.RegraDeNegocio as e:
                erros = [{"codigo": "REGRA", "mensagem": str(e)}]
    return render_template("nova.html", padroes=padroes, erros=erros), (422 if erros else 200)


@bp.route("/calibracoes/<int:cal_id>")
@requer_papel()
def detalhe(cal_id):
    db = get_db()
    cal = db.execute("SELECT c.*, p.codigo AS padrao_codigo, p.denominacao AS padrao_nome, u.nome AS executor "
                     "FROM calibracoes c JOIN padroes p ON p.id=c.padrao_id JOIN usuarios u ON u.id=c.executor_id "
                     "WHERE c.id=?", (cal_id,)).fetchone()
    if cal is None:
        abort(404)
    pontos = db.execute("SELECT * FROM pontos WHERE calibracao_id=? ORDER BY ordem", (cal_id,)).fetchall()
    cert, integro = servicos.verificar_integridade(db, cal_id, current_app.config["CERT_DIR"])
    trilha = db.execute("SELECT a.*, u.nome AS usuario FROM auditoria a LEFT JOIN usuarios u ON u.id=a.usuario_id "
                        "WHERE a.calibracao_id=? ORDER BY a.id", (cal_id,)).fetchall()
    return render_template("detalhe.html", cal=cal, pontos=pontos, cert=cert, integro=integro, trilha=trilha)


@bp.route("/api/calibracoes/<int:cal_id>")
@requer_papel()
def api_calibracao(cal_id):
    db = get_db()
    cal = db.execute("SELECT * FROM calibracoes WHERE id=?", (cal_id,)).fetchone()
    if cal is None:
        abort(404)
    pontos = [dict(p) for p in db.execute("SELECT * FROM pontos WHERE calibracao_id=? ORDER BY ordem", (cal_id,))]
    return jsonify({"calibracao": dict(cal), "pontos": pontos})


@bp.route("/calibracoes/<int:cal_id>/finalizar", methods=["POST"])
@requer_papel()
def finalizar(cal_id):
    try:
        numero = servicos.finalizar(get_db(), g.user, cal_id, current_app.config["CERT_DIR"])
        flash(f"Certificado {numero} finalizado.", "ok")
    except servicos.RegraDeNegocio as e:
        flash(str(e), "erro")
        return redirect(url_for("web.detalhe", cal_id=cal_id)), 303
    return redirect(url_for("web.detalhe", cal_id=cal_id))


@bp.route("/calibracoes/<int:cal_id>/devolver", methods=["POST"])
@requer_papel()
def devolver(cal_id):
    try:
        servicos.devolver(get_db(), g.user, cal_id, request.form.get("justificativa"))
        flash("Calibração devolvida para correção.", "ok")
    except servicos.RegraDeNegocio as e:
        flash(str(e), "erro")
    return redirect(url_for("web.detalhe", cal_id=cal_id))


@bp.route("/calibracoes/<int:cal_id>/certificado.pdf")
@requer_papel()
def certificado_pdf(cal_id):
    db = get_db()
    cert, integro = servicos.verificar_integridade(db, cal_id, current_app.config["CERT_DIR"])
    if cert is None:
        abort(404)
    if not integro:
        abort(409, "Hash do PDF diverge do registro; arquivo não entregue.")
    servicos.auditar(db, cal_id, g.user["id"], "CERTIFICADO_BAIXADO", cert["numero"])
    return send_file(os.path.join(current_app.config["CERT_DIR"], cert["arquivo"]), mimetype="application/pdf")


@bp.route("/modelo.xlsx")
@requer_papel()
def modelo():
    return Response(amostras.gerar_xlsx(), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=modelo_calibracao.xlsx"})


@bp.route("/padroes", methods=["GET", "POST"])
@requer_papel()
def padroes():
    db = get_db()
    if request.method == "POST":
        if g.user["papel"] != "administrador":
            abort(403)
        campos = {k: limpar_texto(request.form.get(k)) for k in
                  ("codigo", "denominacao", "fabricante", "numero_serie", "certificado", "ultima", "proxima")}
        if not all(campos[k] for k in ("codigo", "denominacao", "numero_serie", "certificado", "ultima", "proxima")):
            flash("Preencha todos os campos obrigatórios.", "erro")
        elif campos["proxima"] <= campos["ultima"]:
            flash("A data da próxima calibração deve ser posterior à última.", "erro")
        else:
            try:
                db.execute("INSERT INTO padroes(codigo,denominacao,fabricante,numero_serie,certificado_rastreabilidade,"
                           "data_ultima_calibracao,data_proxima_calibracao) VALUES(?,?,?,?,?,?,?)",
                           (campos["codigo"], campos["denominacao"], campos["fabricante"], campos["numero_serie"],
                            campos["certificado"], campos["ultima"], campos["proxima"]))
                servicos.auditar(db, None, g.user["id"], "PADRAO_CADASTRADO", campos["codigo"])
                flash("Padrão cadastrado.", "ok")
            except Exception:
                flash("Código de padrão já cadastrado.", "erro")
        return redirect(url_for("web.padroes"))
    return render_template("padroes.html", padroes=db.execute("SELECT * FROM padroes ORDER BY codigo").fetchall())
