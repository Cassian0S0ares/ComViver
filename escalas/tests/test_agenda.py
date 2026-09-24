from datetime import time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.factories import UsuarioFactory
from escalas.factories import AlocacaoFactory, TurnoFactory
from escalas.models import StatusAlocacao
from escalas.services import agenda_do_dia

pytestmark = pytest.mark.django_db

HTMX = {"HTTP_HX_REQUEST": "true"}


def _minha(usuario, **turno):
    return AlocacaoFactory(voluntario=None, usuario=usuario, turno=TurnoFactory(**turno))


def test_agenda_traz_so_os_meus_turnos_do_dia_em_ordem(usuario_operacional):
    hoje = timezone.localdate()
    tarde = _minha(usuario_operacional, data=hoje, hora_inicio=time(14), hora_fim=time(16))
    manha = _minha(usuario_operacional, data=hoje, hora_inicio=time(8), hora_fim=time(10))
    _minha(usuario_operacional, data=hoje + timedelta(days=1))
    AlocacaoFactory(turno__data=hoje)
    excluido = _minha(usuario_operacional, data=hoje)
    excluido.turno.delete()
    assert [a.pk for a in agenda_do_dia(usuario_operacional, hoje)] == [manha.pk, tarde.pk]


def test_painel_mostra_meu_dia(client, usuario_operacional):
    hoje = timezone.localdate()
    minha = _minha(usuario_operacional, data=hoje, observacoes="Levar lanche")
    colega = AlocacaoFactory(turno=minha.turno)
    minha.turno.vagas = 2
    minha.turno.save()
    client.force_login(usuario_operacional)
    html = client.get(reverse("core:painel")).content.decode()
    assert "Meu dia" in html
    assert minha.turno.atividade.nome in html
    assert "Levar lanche" in html
    assert colega.voluntario.nome in html
    assert reverse("escalas:concluir", args=[minha.pk]) in html
    assert "0 de 1" in html


def test_painel_sem_turnos_mostra_o_proximo(client, usuario_operacional):
    depois = _minha(usuario_operacional, data=timezone.localdate() + timedelta(days=3))
    client.force_login(usuario_operacional)
    html = client.get(reverse("core:painel")).content.decode()
    assert "Nenhum turno seu" in html
    assert depois.turno.atividade.nome in html


def test_painel_navega_entre_dias(client, usuario_operacional):
    amanha = timezone.localdate() + timedelta(days=1)
    minha = _minha(usuario_operacional, data=amanha)
    client.force_login(usuario_operacional)
    html = client.get(reverse("core:painel"), {"dia": amanha.isoformat()}).content.decode()
    assert minha.turno.atividade.nome in html
    assert client.get(reverse("core:painel"), {"dia": "lixo"}).status_code == 200


def test_marcar_e_desmarcar_como_feito(client, usuario_operacional):
    minha = _minha(usuario_operacional, data=timezone.localdate())
    client.force_login(usuario_operacional)
    url = reverse("escalas:concluir", args=[minha.pk])
    resposta = client.post(url, **HTMX)
    assert resposta.status_code == 200
    assert 'aria-checked="true"' in resposta.content.decode()
    minha.refresh_from_db()
    assert minha.status == StatusAlocacao.CONFIRMADO
    client.post(url, **HTMX)
    minha.refresh_from_db()
    assert minha.status == StatusAlocacao.PREVISTO


def test_sem_htmx_volta_para_o_painel(client, usuario_operacional):
    minha = _minha(usuario_operacional, data=timezone.localdate())
    client.force_login(usuario_operacional)
    resposta = client.post(reverse("escalas:concluir", args=[minha.pk]))
    assert resposta.status_code == 302
    assert resposta.url.startswith(reverse("core:painel"))


def test_nao_marca_item_de_outra_pessoa_nem_do_futuro(client, usuario_operacional):
    alheia = _minha(UsuarioFactory(), data=timezone.localdate())
    futura = _minha(usuario_operacional, data=timezone.localdate() + timedelta(days=1))
    client.force_login(usuario_operacional)
    assert client.post(reverse("escalas:concluir", args=[alheia.pk])).status_code == 404
    assert client.post(reverse("escalas:concluir", args=[futura.pk]), **HTMX).status_code == 400
    futura.refresh_from_db()
    assert futura.status == StatusAlocacao.PREVISTO
