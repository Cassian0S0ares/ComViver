import pytest
from django.utils import timezone

from tests.testapp.models import ModeloComEndereco, ModeloDatado, ModeloExcluivel

pytestmark = pytest.mark.django_db


class TestTimeStampedModel:
    def test_preenche_criado_em_ao_salvar(self):
        antes = timezone.now()
        obj = ModeloDatado.objects.create(nome="teste")
        assert antes <= obj.criado_em <= timezone.now()

    def test_atualiza_atualizado_em_ao_salvar_de_novo(self):
        obj = ModeloDatado.objects.create(nome="teste")
        primeiro = obj.atualizado_em
        obj.nome = "alterado"
        obj.save()
        obj.refresh_from_db()
        assert obj.atualizado_em > primeiro


class TestSoftDeleteModel:
    def test_delete_nao_remove_a_linha_do_banco(self):
        obj = ModeloExcluivel.objects.create(nome="teste")
        pk = obj.pk
        obj.delete()
        assert ModeloExcluivel.todos.filter(pk=pk).exists()

    def test_delete_preenche_deleted_at(self):
        obj = ModeloExcluivel.objects.create(nome="teste")
        obj.delete()
        obj.refresh_from_db()
        assert obj.deleted_at is not None

    def test_excluido_some_do_manager_padrao(self):
        obj = ModeloExcluivel.objects.create(nome="teste")
        obj.delete()
        assert not ModeloExcluivel.objects.filter(pk=obj.pk).exists()

    def test_manager_todos_enxerga_o_excluido(self):
        obj = ModeloExcluivel.objects.create(nome="teste")
        obj.delete()
        assert ModeloExcluivel.todos.filter(pk=obj.pk).exists()

    def test_restaurar_traz_de_volta(self):
        obj = ModeloExcluivel.objects.create(nome="teste")
        obj.delete()
        obj.restaurar()
        assert ModeloExcluivel.objects.filter(pk=obj.pk).exists()


class TestEndereco:
    def test_endereco_formatado_monta_a_linha_completa(self):
        obj = ModeloComEndereco.objects.create(
            nome="teste",
            cep="37500-000",
            logradouro="Rua das Flores",
            numero="123",
            bairro="Centro",
            cidade="Itajubá",
            uf="MG",
        )
        assert obj.endereco_formatado == "Rua das Flores, 123 - Centro, Itajubá/MG"

    def test_endereco_formatado_vazio_quando_sem_logradouro(self):
        obj = ModeloComEndereco.objects.create(nome="teste")
        assert obj.endereco_formatado == ""
