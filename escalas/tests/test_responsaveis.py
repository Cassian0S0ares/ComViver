from datetime import time
from importlib import import_module

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import connection
from django.urls import reverse

from accounts.factories import UsuarioFactory
from escalas.factories import AlocacaoFactory, AtividadeFactory, TurnoFactory
from escalas.forms import TurnoForm
from escalas.models import Alocacao, Atividade, Turno
from escalas.services import usuarios_disponiveis
from voluntarios.factories import VoluntarioFactory

pytestmark = pytest.mark.django_db


def test_select_agrupa_usuarios_e_voluntarios_sem_colisao():
    usuario = UsuarioFactory(is_active=True)
    voluntario = VoluntarioFactory(pk=usuario.pk)
    inativo = UsuarioFactory(is_active=False)
    choices = dict(TurnoForm().fields["responsavel"].choices)
    assert f"usuario:{usuario.pk}" in dict(choices["Usuários do sistema"])
    assert f"usuario:{inativo.pk}" not in dict(choices["Usuários do sistema"])
    assert str(voluntario.pk) in dict(choices["Voluntários"])


@pytest.mark.parametrize("inativo,conflito", [(False, False), (True, False), (False, True)])
def test_salvar_usuario_no_cronograma(client, usuario_admin, inativo, conflito):
    pessoa = UsuarioFactory(first_name="Maria", last_name="Silva", is_active=not inativo)
    atividade = AtividadeFactory()
    if conflito:
        turno = TurnoFactory(data="2026-09-23")
        Alocacao.objects.create(turno=turno, usuario=pessoa)
    total = Turno.objects.count()
    client.force_login(usuario_admin)
    resposta = client.post(reverse("escalas:calendario_turno_novo"), {
        "data": "2026-09-23", "hora_inicio": "09:00", "hora_fim": "11:00",
        "responsavel": f"usuario:{pessoa.pk}", "atividade": atividade.pk, "vagas": 1,
    })
    if inativo or conflito:
        assert resposta.status_code == 200
        assert "responsavel" in resposta.context["form"].errors
        assert Turno.objects.count() == total
    else:
        assert resposta.status_code == 302
        alocacao = Alocacao.objects.get(usuario=pessoa)
        assert alocacao.voluntario_id is None
        assert alocacao.turno.vagas_ocupadas == 1
        assert not alocacao.turno.esta_descoberto
        assert "Maria Silva" in client.get(resposta.url).content.decode()


def test_alocacao_exige_apenas_um_tipo_de_responsavel():
    turno = TurnoFactory()
    with pytest.raises(ValidationError):
        Alocacao(turno=turno).full_clean()
    with pytest.raises(ValidationError):
        Alocacao(turno=turno, usuario=UsuarioFactory(), voluntario=VoluntarioFactory()).full_clean()


def test_usuario_pode_assumir_horario_seguinte_e_remover_vaga(client, usuario_admin):
    pessoa = UsuarioFactory()
    turno = TurnoFactory(hora_inicio=time(8), hora_fim=time(10))
    Alocacao.objects.create(turno=turno, usuario=pessoa)
    proximo = TurnoFactory(data=turno.data, hora_inicio=time(10), hora_fim=time(12))
    assert pessoa in usuarios_disponiveis(proximo)
    assert pessoa not in usuarios_disponiveis(turno)
    client.force_login(usuario_admin)
    resposta = client.post(reverse("escalas:alocar", args=[proximo.pk]), {"usuario": pessoa.pk})
    assert pessoa.get_full_name() in resposta.content.decode()
    alocacao = Alocacao.objects.get(turno=proximo, usuario=pessoa)
    client.post(reverse("escalas:desalocar", args=[alocacao.pk]))
    assert proximo.vagas_ocupadas == 0


def test_atividades_iniciais_preservam_cadastros_e_nao_duplicam():
    cadastrar = import_module("escalas.migrations.0003_atividades_iniciais").cadastrar_atividades
    existente, _ = Atividade.objects.get_or_create(nome="Recreação")
    existente.descricao = "Descrição da instituição"
    existente.save()
    with connection.schema_editor() as editor:
        cadastrar(apps, editor)
        cadastrar(apps, editor)
    assert Atividade.objects.filter(nome="Recreação").count() == 1
    existente.refresh_from_db()
    assert existente.descricao == "Descrição da instituição"
    assert Atividade.objects.filter(nome="Portaria e recepção", ativa=True).exists()


def test_alocacoes_de_voluntarios_continuam_validas():
    alocacao = AlocacaoFactory()
    alocacao.full_clean()
    assert alocacao.nome_responsavel == alocacao.voluntario.nome
