import pytest
from django.core import mail
from django.core.management import CommandError, call_command
from django.test import override_settings

from accounts.models import Usuario
from acolhidos.models import Acolhido
from doacoes.models import Doacao
from escalas.models import Alocacao
from estoque.models import LoteEstoque
from voluntarios.models import Voluntario

pytestmark = pytest.mark.django_db


def test_exige_confirmacao():
    with pytest.raises(CommandError):
        call_command("popular_exemplo")


@override_settings(DEBUG=True)
def test_apaga_tudo_menos_usuarios_e_cria_exemplos(usuario_admin, usuario_tecnico, usuario_operacional):
    Voluntario.objects.create(nome="Apagar")
    usuarios = set(Usuario.objects.values_list("pk", flat=True))
    call_command("popular_exemplo", apagar_tudo=True)
    assert set(Usuario.objects.values_list("pk", flat=True)) == usuarios
    assert not Voluntario.objects.filter(nome="Apagar").exists()
    assert Acolhido.objects.count() >= 9
    assert Doacao.objects.count() > 100
    assert LoteEstoque.objects.filter(saldo__gt=0).exists()
    assert Alocacao.objects.filter(usuario=usuario_admin).exists()
    assert mail.outbox == []
    call_command("popular_exemplo", apagar_tudo=True)  # repetivel
    assert set(Usuario.objects.values_list("pk", flat=True)) == usuarios
