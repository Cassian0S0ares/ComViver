from datetime import date, timedelta

import pytest

from voluntarios.factories import FuncaoFactory, VoluntarioFactory
from voluntarios.models import StatusVoluntario, Voluntario

pytestmark = pytest.mark.django_db


class TestVoluntario:
    def test_idade_calculada_do_nascimento(self):
        voluntario = VoluntarioFactory(
            nascimento=date.today() - timedelta(days=365 * 40 + 10)
        )
        assert voluntario.idade == 40

    def test_status_inicial_e_ativo(self):
        assert VoluntarioFactory().status == StatusVoluntario.ATIVO

    def test_str_mostra_o_nome(self):
        assert str(VoluntarioFactory(nome="Ana Souza")) == "Ana Souza"

    def test_voluntario_pode_ter_varias_funcoes(self):
        voluntario = VoluntarioFactory()
        voluntario.funcoes.set(
            [FuncaoFactory(nome="Cozinha"), FuncaoFactory(nome="Reforço escolar")]
        )
        assert voluntario.funcoes.count() == 2

    def test_exclusao_e_logica(self):
        voluntario = VoluntarioFactory()
        pk = voluntario.pk
        voluntario.delete()
        assert not Voluntario.objects.filter(pk=pk).exists()
        assert Voluntario.todos.filter(pk=pk).exists()

    def test_cpf_e_unico(self):
        from django.db import IntegrityError

        VoluntarioFactory(cpf="12345678901")
        with pytest.raises(IntegrityError):
            VoluntarioFactory(cpf="12345678901")


class TestFuncao:
    def test_nome_da_funcao_e_unico(self):
        from django.db import IntegrityError

        FuncaoFactory(nome="Cozinha")
        with pytest.raises(IntegrityError):
            FuncaoFactory(nome="Cozinha")
