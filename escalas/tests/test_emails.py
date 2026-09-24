"""Avisos de inclusão em atividade, inclusive pelos dois fluxos da grade."""

from datetime import date

import pytest
from django.core import mail
from django.db import transaction
from django.urls import reverse

from accounts.factories import UsuarioFactory
from escalas.factories import AtividadeFactory, TurnoFactory
from escalas.models import Alocacao
from voluntarios.factories import VoluntarioFactory

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def email_em_memoria(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


def test_criacao_com_duas_pessoas_envia_email_individual_com_equipe_completa(client, usuario_admin):
    atividade = AtividadeFactory(nome="Cozinha", descricao="Preparar o almoço coletivo.")
    voluntario = VoluntarioFactory(nome="Ana Souza", email="ana@exemplo.org")
    usuario = UsuarioFactory(first_name="Bruno", last_name="Lima", email="bruno@exemplo.org")
    client.force_login(usuario_admin)

    resposta = client.post(reverse("escalas:calendario_turno_novo"), {
        "data": "2026-09-23", "hora_inicio": "09:00", "hora_fim": "11:00",
        "atividade": atividade.pk, "vagas": 2, "observacoes": "Trazer avental.",
        "responsavel": [str(voluntario.pk), f"usuario:{usuario.pk}"],
    })

    assert resposta.status_code == 302
    assert len(mail.outbox) == 2
    assert {m.to[0] for m in mail.outbox} == {voluntario.email, usuario.email}
    for mensagem in mail.outbox:
        assert "Cozinha" in mensagem.subject
        assert "23/09/2026" in mensagem.body
        assert "09:00 às 11:00" in mensagem.body
        assert "Ana Souza, Bruno Lima" in mensagem.body
        assert "Preparar o almoço coletivo." in mensagem.body
        assert "Trazer avental." in mensagem.body
        assert "cid:logo-comviver" in mensagem.alternatives[0].content
        assert any(anexo.get("Content-ID") == "<logo-comviver>" for anexo in mensagem.attachments)


def test_adicionar_depois_avisa_so_a_pessoa_nova(client, usuario_admin):
    turno = TurnoFactory(data=date(2026, 9, 23), vagas=2)
    anterior = VoluntarioFactory(nome="Ana Souza", email="ana@exemplo.org")
    Alocacao.objects.create(turno=turno, voluntario=anterior)
    mail.outbox.clear()
    novo = UsuarioFactory(first_name="Bruno", last_name="Lima", email="bruno@exemplo.org")
    client.force_login(usuario_admin)

    resposta = client.post(reverse("escalas:alocar", args=[turno.pk]), {"usuario": novo.pk})

    assert resposta.status_code == 200
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [novo.email]
    assert "Ana Souza, Bruno Lima" in mail.outbox[0].body


def test_edicao_rollback_e_pessoa_sem_email_nao_geram_aviso():
    turno = TurnoFactory()
    pessoa = VoluntarioFactory(email="ana@exemplo.org")
    with pytest.raises(RuntimeError), transaction.atomic():
        Alocacao.objects.create(turno=turno, voluntario=pessoa)
        raise RuntimeError("cancelar")
    assert mail.outbox == []

    alocacao = Alocacao.objects.create(turno=turno, voluntario=pessoa)
    assert len(mail.outbox) == 1
    alocacao.observacao = "Nova observação"
    alocacao.save()
    assert len(mail.outbox) == 1

    sem_email = VoluntarioFactory(email="")
    outro_turno = TurnoFactory()
    Alocacao.objects.create(turno=outro_turno, voluntario=sem_email)
    assert len(mail.outbox) == 1
