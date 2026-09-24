"""Notificações disparadas pela inclusão de uma pessoa em um turno."""

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from escalas.emails import enviar_aviso_alocacao
from escalas.models import Alocacao

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Alocacao)
def avisar_nova_alocacao(sender, instance, created, raw=False, **kwargs):
    if not created or raw:
        return

    def enviar():
        try:
            enviar_aviso_alocacao(instance.pk)
        except Exception:
            logger.exception("Falha ao enviar aviso da alocação %s", instance.pk)

    transaction.on_commit(enviar, using=instance._state.db)
