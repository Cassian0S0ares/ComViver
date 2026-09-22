import pytest
from django.contrib.auth.models import Group

from accounts.factories import UsuarioFactory
from accounts.models import Perfil

pytestmark = pytest.mark.django_db


class TestGrupos:
    def test_os_tres_grupos_existem(self):
        nomes = set(Group.objects.values_list("name", flat=True))
        assert {"Administrador", "Técnico", "Operacional"} <= nomes

    @pytest.mark.parametrize(
        "perfil,grupo",
        [
            (Perfil.ADMIN, "Administrador"),
            (Perfil.TECNICO, "Técnico"),
            (Perfil.OPERACIONAL, "Operacional"),
        ],
    )
    def test_usuario_entra_no_grupo_do_seu_perfil(self, perfil, grupo):
        usuario = UsuarioFactory(perfil=perfil)
        assert usuario.groups.filter(name=grupo).exists()

    def test_trocar_perfil_troca_de_grupo(self):
        usuario = UsuarioFactory(perfil=Perfil.OPERACIONAL)
        usuario.perfil = Perfil.TECNICO
        usuario.save()
        assert usuario.groups.filter(name="Técnico").exists()
        assert not usuario.groups.filter(name="Operacional").exists()

    def test_usuario_pertence_a_exatamente_um_grupo(self):
        usuario = UsuarioFactory(perfil=Perfil.ADMIN)
        assert usuario.groups.count() == 1
