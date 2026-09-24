from datetime import date, time

import pytest
from django.urls import reverse
from django.utils import timezone

from escalas.factories import AlocacaoFactory, AtividadeFactory, EscalaFactory, TurnoFactory
from escalas.models import Alocacao, Turno
from escalas.services import grade_da_escala
from voluntarios.factories import VoluntarioFactory
from voluntarios.models import StatusVoluntario

pytestmark = pytest.mark.django_db


def test_menu_escalas_abre_calendario_sem_cadastro_previo(client, usuario_operacional):
    client.force_login(usuario_operacional)
    resposta = client.get(reverse("escalas:lista"))
    assert resposta.status_code == 200
    assert "escalas/escala_grade.html" in [t.name for t in resposta.templates]
    assert len(resposta.context["dias"]) == 7
    assert resposta.context["dias"][0].weekday() == 6
    assert resposta.context["dias"][0] <= timezone.localdate() <= resposta.context["dias"][-1]
    assert resposta.content.decode().count('class="cronograma-slot"') == 168
    assert "Nova escala" not in resposta.content.decode()


def test_calendario_mostra_itens_de_escalas_existentes(client, usuario_operacional):
    a = TurnoFactory(data=date(2026, 9, 21))
    b = TurnoFactory(data=date(2026, 9, 22))
    TurnoFactory(data=date(2026, 9, 28))
    client.force_login(usuario_operacional)
    resposta = client.get(reverse("escalas:lista"), {"semana": "2026-09-23"})
    assert resposta.context["total_turnos"] == 2
    assert a.atividade.nome in resposta.content.decode()
    assert b.atividade.nome in resposta.content.decode()
    assert resposta.context["semana_seguinte"] == date(2026, 9, 27)


def test_primeiro_turno_cria_semana_automaticamente(client, usuario_admin):
    pessoa = VoluntarioFactory()
    atividade = AtividadeFactory()
    client.force_login(usuario_admin)
    resposta = client.post(reverse("escalas:calendario_turno_novo"), {
        "data": "2026-09-23", "hora_inicio": "09:00", "hora_fim": "11:00",
        "responsavel": pessoa.pk, "atividade": atividade.pk, "vagas": 1,
    })
    assert resposta.status_code == 302
    assert resposta.url.startswith(reverse("escalas:lista") + "?semana=2026-09-23")
    turno = Turno.objects.get()
    assert turno.escala.data_inicio == date(2026, 9, 20)
    assert turno.escala.data_fim == date(2026, 9, 26)
    assert turno.alocacoes.get().voluntario == pessoa


def test_grade_vazia_tem_domingo_a_sabado_e_24_horas(client, usuario_operacional):
    escala = EscalaFactory(data_inicio=date(2026, 9, 20), data_fim=date(2026, 9, 26))
    client.force_login(usuario_operacional)
    resposta = client.get(reverse("escalas:grade", args=[escala.pk]))
    assert [d.weekday() for d in resposta.context["dias"]] == [6, 0, 1, 2, 3, 4, 5]
    assert len(resposta.context["horas"]) == 24
    assert resposta.content.decode().count('class="cronograma-slot"') == 168
    assert "Todos os turnos cobertos" not in resposta.content.decode()


def test_turnos_simultaneos_nao_se_sobrescrevem():
    escala = EscalaFactory(data_inicio=date(2026, 9, 20), data_fim=date(2026, 9, 26))
    a = TurnoFactory(escala=escala, data=escala.data_inicio,
                    hora_inicio=time(8, 30), hora_fim=time(10))
    b = TurnoFactory(escala=escala, data=escala.data_inicio,
                    hora_inicio=time(8, 30), hora_fim=time(10))
    c = TurnoFactory(escala=escala, data=escala.data_inicio,
                    hora_inicio=time(10), hora_fim=time(11))
    coluna = grade_da_escala(escala)["colunas"][0]
    assert [e["turno"] for e in coluna["eventos"]] == [a, b, c]
    assert [e["faixa"] for e in coluna["eventos"]] == [1, 2, 1]
    assert coluna["eventos"][0]["inicio"] == 511
    assert coluna["eventos"][0]["fim"] == 601


def test_escala_antiga_preserva_periodo_e_navega_semanas():
    escala = EscalaFactory(data_inicio=date(2026, 9, 24), data_fim=date(2026, 10, 1))
    grade = grade_da_escala(escala)
    assert grade["dias"][0] == date(2026, 9, 20)
    assert not grade["colunas"][0]["ativo"]
    assert grade["semana_seguinte"] == date(2026, 9, 27)
    proxima = grade_da_escala(escala, grade["semana_seguinte"])
    assert proxima["semana_anterior"] == date(2026, 9, 20)
    assert proxima["semana_seguinte"] is None


def test_clique_pre_preenche_data_e_horarios(client, usuario_operacional):
    escala = EscalaFactory()
    client.force_login(usuario_operacional)
    resposta = client.get(reverse("escalas:turno_novo", args=[escala.pk]), {
        "data": escala.data_inicio.isoformat(), "hora_inicio": "14:00", "hora_fim": "15:00"
    })
    assert resposta.context["form"]["hora_inicio"].value() == "14:00"
    assert resposta.context["form"]["hora_fim"].value() == "15:00"
    assert resposta.context["form"]["data"].value() == escala.data_inicio.isoformat()


@pytest.mark.parametrize("conflito,inativo", [(False, False), (True, False), (False, True)])
def test_salva_turno_e_responsavel_juntos(client, usuario_admin, conflito, inativo):
    escala = EscalaFactory()
    pessoa = VoluntarioFactory(
        status=StatusVoluntario.INATIVO if inativo else StatusVoluntario.ATIVO
    )
    atividade = AtividadeFactory()
    if conflito:
        AlocacaoFactory(voluntario=pessoa, turno__data=escala.data_inicio)
    client.force_login(usuario_admin)
    resposta = client.post(reverse("escalas:turno_novo", args=[escala.pk]), {
        "data": escala.data_inicio.isoformat(), "hora_inicio": "09:30", "hora_fim": "12:30",
        "responsavel": pessoa.pk, "atividade": atividade.pk, "vagas": 1,
        "observacoes": "Acompanhar a equipe",
    })
    if conflito or inativo:
        assert resposta.status_code == 200
        assert "responsavel" in resposta.context["form"].errors
        assert not Turno.objects.filter(escala=escala).exists()
        assert resposta.context["form"]["observacoes"].value() == "Acompanhar a equipe"
    else:
        assert resposta.status_code == 302
        turno = Turno.objects.get(escala=escala)
        assert Alocacao.objects.filter(turno=turno, voluntario=pessoa).exists()
        grade = client.get(resposta.url).content.decode()
        assert pessoa.nome in grade
        assert "09:30 às 12:30" in grade


def test_tecnico_nao_recebe_horarios_clicaveis_nem_cria_turnos(client, usuario_tecnico):
    escala = EscalaFactory()
    client.force_login(usuario_tecnico)
    grade = client.get(reverse("escalas:grade", args=[escala.pk])).content.decode()
    assert 'class="cronograma-slot" href=' not in grade
    assert "Adicionar turno em" not in grade
    assert client.post(reverse("escalas:turno_novo", args=[escala.pk]), {}).status_code == 403
