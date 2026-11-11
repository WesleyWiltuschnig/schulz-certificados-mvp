"""Rastreabilidade por QR Code (AV04/AV05): codigo de validacao, URL publica e desenho do QR.

O QR Code impresso no certificado aponta para /validar/<codigo>. O codigo e aleatorio
(nao sequencial), de modo que a URL nao pode ser deduzida a partir do numero do certificado.
Usa apenas o reportlab, que ja e dependencia do projeto (sem biblioteca extra).
"""
import re
import secrets

from reportlab.graphics import renderSVG
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing

FORMATO_CODIGO = re.compile(r"^[A-Za-z0-9_-]{8,40}$")


def gerar_codigo():
    """Codigo de validacao com 96 bits de aleatoriedade (16 caracteres URL-safe)."""
    return secrets.token_urlsafe(12)


def codigo_valido(codigo):
    return bool(codigo) and bool(FORMATO_CODIGO.match(codigo))


def url_validacao(url_base, codigo):
    return f"{url_base.rstrip('/')}/validar/{codigo}"


def desenho_qr(conteudo, lado=90):
    """Drawing do reportlab (flowable) com o QR Code; `lado` em pontos tipograficos."""
    widget = QrCodeWidget(conteudo, barLevel="M")
    x1, y1, x2, y2 = widget.getBounds()
    largura, altura = x2 - x1, y2 - y1
    desenho = Drawing(lado, lado, transform=[lado / largura, 0, 0, lado / altura, 0, 0])
    desenho.add(widget)
    return desenho


def svg_qr(conteudo, lado=160):
    """QR Code em SVG para exibir na tela de detalhe."""
    svg = renderSVG.drawToString(desenho_qr(conteudo, lado))
    return svg[svg.find("<svg"):]
