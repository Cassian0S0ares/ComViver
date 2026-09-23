"""Mensagens enviadas para a equipe do ComViver."""

from email.mime.image import MIMEImage

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.mail import EmailMultiAlternatives
from django.template import loader

LOGO = "img/lar-padre-jose-gumercindo.png"
LOGO_CID = "logo-comviver"


def anexar_logo(mensagem):
    """Incorpora a logo ao e-mail sem depender de uma URL pública."""
    caminho = finders.find(LOGO)
    if not caminho:
        return
    with open(caminho, "rb") as arquivo:
        logo = MIMEImage(arquivo.read(), "png")
    logo.add_header("Content-ID", f"<{LOGO_CID}>")
    logo.add_header("Content-Disposition", "inline", filename="logo.png")
    mensagem.mixed_subtype = "related"
    mensagem.attach(logo)


def enviar_boas_vindas(usuario, senha_provisoria, login_url):
    """Envia as credenciais temporárias somente ao endereço do novo usuário."""
    contexto = {
        "usuario": usuario,
        "senha_provisoria": senha_provisoria,
        "login_url": login_url,
        "logo_cid": LOGO_CID,
    }
    assunto = "".join(
        loader.render_to_string("accounts/email/boas_vindas_assunto.txt", contexto).splitlines()
    )
    mensagem = EmailMultiAlternatives(
        assunto,
        loader.render_to_string("accounts/email/boas_vindas.txt", contexto),
        settings.DEFAULT_FROM_EMAIL,
        [usuario.email],
    )
    mensagem.attach_alternative(
        loader.render_to_string("accounts/email/boas_vindas.html", contexto), "text/html"
    )
    anexar_logo(mensagem)
    if mensagem.send() != 1:
        raise OSError("O servidor de e-mail não confirmou o envio.")