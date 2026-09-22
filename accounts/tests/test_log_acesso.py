import pytest
from django.urls import reverse

from accounts.models import AcaoFicha, LogAcessoFicha
from acolhidos.factories import AcolhidoFactory

pytestmark = pytest.mark.django_db


class TestLogAcessoFicha:
    def test_abrir_a_ficha_registra_a_leitura(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        client.get(reverse("acolhidos:detalhe", args=[acolhido.pk]))
        log = LogAcessoFicha.objects.get(acolhido=acolhido)
        assert log.usuario == usuario_tecnico
        assert log.acao == AcaoFicha.VIEW

    def test_cada_abertura_gera_um_registro(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        client.get(reverse("acolhidos:detalhe", args=[acolhido.pk]))
        client.get(reverse("acolhidos:detalhe", args=[acolhido.pk]))
        assert LogAcessoFicha.objects.filter(acolhido=acolhido).count() == 2

    def test_operacional_tambem_e_registrado(self, client, usuario_operacional):
        """Mesmo vendo menos, o acesso do Operacional precisa ficar registrado."""
        acolhido = AcolhidoFactory()
        client.force_login(usuario_operacional)
        client.get(reverse("acolhidos:detalhe", args=[acolhido.pk]))
        assert LogAcessoFicha.objects.filter(
            acolhido=acolhido, usuario=usuario_operacional
        ).exists()

    def test_log_sobrevive_a_exclusao_do_usuario(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        client.get(reverse("acolhidos:detalhe", args=[acolhido.pk]))
        usuario_tecnico.delete()
        log = LogAcessoFicha.objects.get(acolhido=acolhido)
        assert log.usuario is None
        assert log.usuario_descricao != ""
