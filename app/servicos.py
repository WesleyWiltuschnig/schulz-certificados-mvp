"""Servicos transacionais: importacao, finalizacao e devolucao de certificados."""
import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal

from . import metrologia as met
from .db import transacao
from .ingestao import IngestaoInvalida, ler_planilha, limpar_texto
from .pdfgen import detectar_marcadores, gerar_pdf, montar_documento, texto_plano
from .validacao import codigo_valido, gerar_codigo, url_validacao

PAPEIS_UPLOAD = {"executor", "emissor", "signatario"}
PAPEIS_FINALIZA = {"emissor", "signatario"}
TOLERANCIA_DESVIO = Decimal("0.0000001")
URL_BASE_PADRAO = "http://127.0.0.1:5000"


class RegraDeNegocio(Exception):
    """Violacao de regra de negocio (mensagem apresentavel ao usuario)."""


def agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def auditar(db, calibracao_id, usuario_id, acao, detalhe=None):
    db.execute("INSERT INTO auditoria(calibracao_id,usuario_id,acao,detalhe,criado_em) VALUES(?,?,?,?,?)",
               (calibracao_id, usuario_id, acao, detalhe, agora()))


def _rejeitar(db, usuario, nome, sha, erros):
    db.execute("INSERT INTO rejeicoes(usuario_id,arquivo,arquivo_sha256,motivos,criado_em) VALUES(?,?,?,?,?)",
               (usuario["id"], nome, sha, json.dumps(erros, ensure_ascii=False), agora()))
    auditar(db, None, usuario["id"], "INGESTAO_RECUSADA", "; ".join(e["codigo"] for e in erros))
    raise IngestaoInvalida(erros)


def importar_planilha(db, usuario, padrao_id, nome_arquivo, conteudo, upload_dir):
    """UC01 + calculo (UC02): valida, calcula e persiste em uma unica transacao."""
    if usuario["papel"] not in PAPEIS_UPLOAD:
        raise RegraDeNegocio("Perfil sem permissão para enviar planilhas.")
    sha = hashlib.sha256(conteudo).hexdigest()
    if not (nome_arquivo or "").lower().endswith(".xlsx"):
        _rejeitar(db, usuario, nome_arquivo, sha, [{"codigo": "ARQ", "mensagem": "Somente arquivos .xlsx são aceitos."}])
    padrao = db.execute("SELECT * FROM padroes WHERE id=?", (padrao_id,)).fetchone()
    if padrao is None:
        raise RegraDeNegocio("Padrão não cadastrado.")
    try:
        dados = ler_planilha(conteudo, padrao_esperado=padrao["codigo"])
    except IngestaoInvalida as e:
        _rejeitar(db, usuario, nome_arquivo, sha, e.erros)

    dup = db.execute("SELECT id FROM calibracoes WHERE arquivo_sha256=? AND padrao_id=? AND status<>'DEVOLVIDO'",
                     (sha, padrao["id"])).fetchone()
    if dup:
        _rejeitar(db, usuario, nome_arquivo, sha,
                  [{"codigo": "DUP", "mensagem": f"Arquivo já importado na calibração #{dup['id']}."}])

    avisos = list(dados["avisos"])
    if dados["data_medicao"] > padrao["data_proxima_calibracao"]:
        avisos.append(f"RN04: padrão {padrao['codigo']} com calibração vencida na data da medição "
                      f"(próxima calibração: {padrao['data_proxima_calibracao']}).")

    calculados = []
    for p in dados["pontos"]:
        r = met.calcular_ponto(p["referencia"], p["leituras"], p["lea"])
        if p["desvio_informado"] is not None and abs(p["desvio_informado"] - r["erro"]) > TOLERANCIA_DESVIO:
            avisos.append(f"Ponto '{p['nome']}': desvio informado ({p['desvio_informado']}) diverge do recalculado "
                          f"({met.texto_decimal(r['erro'])}); adotado o recalculado.")
        calculados.append((p, r))
    parecer = met.parecer_final([r["classificacao"] for _, r in calculados])

    with transacao(db):
        cur = db.execute(
            "INSERT INTO calibracoes(instrumento,denominacao,plano_medicao,data_medicao,temperatura,"
            "metrologista_relatorio,padrao_id,executor_id,arquivo_nome,arquivo_sha256,blocos,parecer,avisos,"
            "status,criado_em) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (dados["instrumento"], dados["denominacao"], dados["plano_medicao"], dados["data_medicao"],
             met.texto_decimal(dados["temperatura"]), dados["metrologista"], padrao["id"], usuario["id"],
             os.path.basename(nome_arquivo), sha, dados["blocos"], parecer,
             json.dumps(avisos, ensure_ascii=False), "AGUARDANDO_ANALISE", agora()))
        cal_id = cur.lastrowid
        for ordem, (p, r) in enumerate(calculados, start=1):
            db.execute(
                "INSERT INTO pontos(calibracao_id,ordem,nome,referencia,leituras,media,desvio_padrao,erro,"
                "erro_abs,lea,classificacao) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (cal_id, ordem, p["nome"], met.texto_decimal(p["referencia"]),
                 json.dumps([met.texto_decimal(v) for v in p["leituras"]]), met.texto_decimal(r["media"]),
                 met.texto_decimal(r["desvio_padrao"]), met.texto_decimal(r["erro"]),
                 met.texto_decimal(r["erro_abs"]), met.texto_decimal(p["lea"]), r["classificacao"]))
        os.makedirs(upload_dir, exist_ok=True)
        with open(os.path.join(upload_dir, f"{cal_id}.xlsx"), "wb") as f:
            f.write(conteudo)
        auditar(db, cal_id, usuario["id"], "CALIBRACAO_IMPORTADA", f"parecer={parecer}")
    return cal_id


def _contexto(db, cal_id, numero, emitido_em, finalizador_nome, codigo=None, url_qr=None):
    cal = db.execute("SELECT * FROM calibracoes WHERE id=?", (cal_id,)).fetchone()
    padrao = db.execute("SELECT * FROM padroes WHERE id=?", (cal["padrao_id"],)).fetchone()
    exe = db.execute("SELECT nome FROM usuarios WHERE id=?", (cal["executor_id"],)).fetchone()
    pontos = [{k: (Decimal(r[k]) if k in ("referencia", "media", "desvio_padrao", "erro", "erro_abs", "lea") else r[k])
               for k in r.keys()} for r in db.execute("SELECT * FROM pontos WHERE calibracao_id=? ORDER BY ordem", (cal_id,))]
    return {"cal": cal, "padrao": padrao, "pontos": pontos, "numero": numero, "emitido_em": emitido_em,
            "executor": exe["nome"], "finalizador": finalizador_nome, "codigo_validacao": codigo,
            "url_validacao": url_qr}


def finalizar(db, usuario, cal_id, cert_dir, url_base=None):
    """UC03: finaliza, numera, gera PDF com QR Code de validacao e torna o certificado imutavel.

    `url_base` e o endereco publico da aplicacao (ex.: http://192.168.0.10:5000 ou a URL do
    Elastic Beanstalk); o QR Code impresso aponta para <url_base>/validar/<codigo>.
    """
    if usuario["papel"] not in PAPEIS_FINALIZA:
        raise RegraDeNegocio("Perfil sem permissão para finalizar certificados.")
    caminho = None
    try:
        with transacao(db):
            cal = db.execute("SELECT * FROM calibracoes WHERE id=?", (cal_id,)).fetchone()
            if cal is None:
                raise RegraDeNegocio("Calibração não encontrada.")
            if cal["status"] != "AGUARDANDO_ANALISE":
                raise RegraDeNegocio(f"Calibração em situação {cal['status']}; não pode ser finalizada.")
            if cal["executor_id"] == usuario["id"]:
                raise RegraDeNegocio("RN09: quem elabora a calibração não pode finalizá-la.")
            if cal["parecer"] not in ("APROVADO", "REPROVADO"):
                raise RegraDeNegocio("RN05: parecer não definido.")
            ano = datetime.now(timezone.utc).year
            db.execute("INSERT OR IGNORE INTO contador_certificados(ano,ultimo) VALUES(?,0)", (ano,))
            db.execute("UPDATE contador_certificados SET ultimo=ultimo+1 WHERE ano=?", (ano,))
            n = db.execute("SELECT ultimo FROM contador_certificados WHERE ano=?", (ano,)).fetchone()[0]
            numero = f"{n:05d}/{ano}"
            emitido_em = agora()
            codigo = gerar_codigo()
            url_qr = url_validacao(url_base or URL_BASE_PADRAO, codigo)
            doc = montar_documento(_contexto(db, cal_id, numero, emitido_em, usuario["nome"], codigo, url_qr))
            marcadores = detectar_marcadores(texto_plano(doc))
            if marcadores:
                raise RegraDeNegocio("RN06: marcador de preenchimento não substituído: " + ", ".join(marcadores))
            pdf = gerar_pdf(doc)
            os.makedirs(cert_dir, exist_ok=True)
            nome = f"{numero.replace('/', '-')}_v1.pdf"
            caminho = os.path.join(cert_dir, nome)
            with open(caminho, "xb") as f:
                f.write(pdf)
            db.execute("INSERT INTO certificados(calibracao_id,versao,numero,arquivo,pdf_sha256,finalizado_por,"
                       "finalizado_em,codigo_validacao) VALUES(?,?,?,?,?,?,?,?)",
                       (cal_id, 1, numero, nome, hashlib.sha256(pdf).hexdigest(), usuario["id"], emitido_em,
                        codigo))
            db.execute("UPDATE calibracoes SET status='FINALIZADO' WHERE id=?", (cal_id,))
            auditar(db, cal_id, usuario["id"], "CERTIFICADO_FINALIZADO", numero)
    except BaseException:
        if caminho and os.path.exists(caminho):
            os.remove(caminho)
        raise
    return numero


def devolver(db, usuario, cal_id, justificativa):
    if usuario["papel"] not in PAPEIS_FINALIZA:
        raise RegraDeNegocio("Perfil sem permissão para devolver certificados.")
    justificativa = limpar_texto(justificativa)
    if not justificativa:
        raise RegraDeNegocio("Justificativa obrigatória para devolução.")
    with transacao(db):
        cal = db.execute("SELECT status FROM calibracoes WHERE id=?", (cal_id,)).fetchone()
        if cal is None or cal["status"] != "AGUARDANDO_ANALISE":
            raise RegraDeNegocio("Somente calibrações aguardando análise podem ser devolvidas.")
        db.execute("UPDATE calibracoes SET status='DEVOLVIDO', justificativa_devolucao=? WHERE id=?",
                   (justificativa, cal_id))
        auditar(db, cal_id, usuario["id"], "CALIBRACAO_DEVOLVIDA", justificativa)


def verificar_integridade(db, cal_id, cert_dir):
    """Recalcula o SHA-256 do PDF e compara com o registro (secao 8.5 da Atividade 2)."""
    c = db.execute("SELECT * FROM certificados WHERE calibracao_id=? ORDER BY versao DESC", (cal_id,)).fetchone()
    if c is None:
        return None, None
    return c, _pdf_integro(c, cert_dir)


def _pdf_integro(cert, cert_dir):
    caminho = os.path.join(cert_dir, cert["arquivo"])
    if not os.path.exists(caminho):
        return False
    with open(caminho, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest() == cert["pdf_sha256"]


def consultar_validacao(db, codigo, cert_dir):
    """Dados publicos exibidos ao ler o QR Code (sem login). Retorna None se o codigo nao existe.

    Expoe somente o necessario para o chao de fabrica conferir o instrumento: numero, versao,
    instrumento, datas, parecer e classificacao por ponto. Nao expoe usuarios internos alem do
    nome de quem finalizou, nem arquivos de origem.
    """
    if not codigo_valido(codigo):
        return None
    c = db.execute("SELECT ce.*, u.nome AS finalizador FROM certificados ce JOIN usuarios u ON u.id=ce.finalizado_por "
                   "WHERE ce.codigo_validacao=?", (codigo,)).fetchone()
    if c is None:
        return None
    cal = db.execute("SELECT c.*, p.codigo AS padrao_codigo, p.denominacao AS padrao_nome FROM calibracoes c "
                     "JOIN padroes p ON p.id=c.padrao_id WHERE c.id=?", (c["calibracao_id"],)).fetchone()
    pontos = db.execute("SELECT nome, erro, erro_abs, lea, classificacao FROM pontos WHERE calibracao_id=? "
                        "ORDER BY ordem", (c["calibracao_id"],)).fetchall()
    return {"certificado": c, "calibracao": cal, "pontos": pontos, "integro": _pdf_integro(c, cert_dir)}


def registrar_validacao(db, cal_id, origem):
    auditar(db, cal_id, None, "CERTIFICADO_VALIDADO", origem)


def conferir_arquivo(db, codigo, conteudo):
    """Compara o SHA-256 de um PDF enviado pelo usuario com o hash registrado na finalizacao."""
    c = db.execute("SELECT calibracao_id, pdf_sha256 FROM certificados WHERE codigo_validacao=?", (codigo,)).fetchone()
    if c is None:
        return None
    sha = hashlib.sha256(conteudo).hexdigest()
    confere = sha == c["pdf_sha256"]
    auditar(db, c["calibracao_id"], None, "PDF_CONFERIDO", "confere" if confere else "DIVERGENTE")
    return {"confere": confere, "sha256_enviado": sha, "sha256_registrado": c["pdf_sha256"]}
