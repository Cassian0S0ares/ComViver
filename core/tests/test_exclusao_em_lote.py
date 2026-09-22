import pytest

from tests.testapp.models import ModeloExcluivel

pytestmark = pytest.mark.django_db


def test_queryset_delete_preserva_linhas():
    ModeloExcluivel.objects.create(nome="Primeiro")
    ModeloExcluivel.objects.create(nome="Segundo")
    ModeloExcluivel.objects.all().delete()
    assert ModeloExcluivel.objects.count() == 0
    assert ModeloExcluivel.todos.count() == 2


def test_manager_todos_tambem_exclui_logicamente():
    objeto = ModeloExcluivel.objects.create(nome="Preservado")
    ModeloExcluivel.todos.filter(pk=objeto.pk).delete()
    assert ModeloExcluivel.todos.get(pk=objeto.pk).deleted_at is not None
