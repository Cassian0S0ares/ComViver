import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from acolhidos.models import Acolhido, FichaAcolhimento, StatusAcolhido, VinculoFamiliar

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def ambiente_de_desenvolvimento(settings):
    """O comando so roda com DEBUG ligado; a suite roda com DEBUG desligado."""
    settings.DEBUG = True


class TestSeedDemo:
    def test_cria_acolhidos(self):
        call_command("seed_demo", verbosity=0)
        assert Acolhido.objects.count() >= 8

    def test_todo_acolhido_tem_ficha(self):
        call_command("seed_demo", verbosity=0)
        assert FichaAcolhimento.objects.count() == Acolhido.objects.count()

    def test_todo_acolhido_tem_ao_menos_um_responsavel(self):
        call_command("seed_demo", verbosity=0)
        for acolhido in Acolhido.objects.all():
            assert acolhido.vinculos.exists()

    def test_cria_irmaos_com_responsavel_compartilhado(self):
        """O caso que mais quebra sistema mal modelado precisa estar nos dados
        de demonstracao."""
        call_command("seed_demo", verbosity=0)
        compartilhados = list(VinculoFamiliar.objects.values_list("responsavel", flat=True))
        assert len(compartilhados) > len(set(compartilhados))

    def test_inclui_um_desligado(self):
        call_command("seed_demo", verbosity=0)
        assert Acolhido.objects.filter(status=StatusAcolhido.DESLIGADO).exists()

    def test_limpar_apaga_antes_de_recriar(self):
        call_command("seed_demo", verbosity=0)
        primeira_contagem = Acolhido.todos.count()
        call_command("seed_demo", "--limpar", verbosity=0)
        assert Acolhido.todos.count() == primeira_contagem

    def test_recusa_rodar_com_debug_desligado(self, settings):
        """O comando apaga dados. Sem essa trava, roda-lo por engano no banco
        da instituicao levaria junto a ficha de cada crianca."""
        settings.DEBUG = False
        with pytest.raises(CommandError) as erro:
            call_command("seed_demo", "--limpar", verbosity=0)
        assert "não deve rodar em produção" in str(erro.value)

    def test_forcar_permite_rodar_com_debug_desligado(self, settings):
        settings.DEBUG = False
        call_command("seed_demo", "--forcar", verbosity=0)
        assert Acolhido.objects.exists()
