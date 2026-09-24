"""Avisos de novas pessoas escaladas em atividades."""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import loader

from accounts.emails import LOGO_CID, anexar_logo
from escalas.models import Alocacao


def enviar_aviso_alocacao(alocacao_id):
    """Envia o aviso com a equipe completa depois de confirmar a transação."""
    alocacao = (
        Alocacao.objects.select_related("usuario", "voluntario", "turno__atividade")
        .filter(pk=alocacao_id)
        .first()
    )
    if alocacao is None:
        return
    pessoa = alocacao.usuario or alocacao.voluntario
    if not pessoa.email:
        return
    turno = alocacao.turno
    equipe = turno.alocacoes.select_related("usuario", "voluntario").order_by("criado_em", "pk")
    responsaveis = [item.nome_responsavel for item in equipe]
    contexto = {
        "pessoa": pessoa,
        "turno": turno,
        "responsaveis": responsaveis,
        "logo_cid": LOGO_CID,
    }
    assunto = "".join(
        loader.render_to_string("escalas/email/nova_alocacao_assunto.txt", contexto).splitlines()
    )
    mensagem = EmailMultiAlternatives(
        assunto,
        loader.render_to_string("escalas/email/nova_alocacao.txt", contexto),
        settings.DEFAULT_FROM_EMAIL,
        [pessoa.email],
    )
    mensagem.attach_alternative(
        loader.render_to_string("escalas/email/nova_alocacao.html", contexto), "text/html"
    )
    anexar_logo(mensagem)
    if mensagem.send() != 1:
        raise OSError("O servidor de e-mail não confirmou o envio.")
