from datetime import date, time

import pytest
from django.urls import reverse

from accounts.factories import UsuarioFactory
from accounts.models import Perfil
from escalas.factories import AlocacaoFactory, AtividadeFactory, EscalaFactory, TurnoFactory
from escalas.models import Alocacao, Turno
from voluntarios.factories import VoluntarioFactory

pytestmark = pytest.mark.django_db

HTMX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def escala():
    return EscalaFactory(data_inicio=date(2026, 9, 20), data_fim=date(2026, 9, 26))


@pytest.fixture
def turno(escala, usuario_operacional):
    return TurnoFactory(escala=escala, data=date(2026, 9, 22), criado_por=usuario_operacional,
                        observacoes="Levar lanche")


def _dados(turno, **extra):
    return {
        "data": turno.data.isoformat(), "hora_inicio": "10:00", "hora_fim": "12:00",
        "atividade": turno.atividade.pk, "vagas": 2, "observacoes": "Novo texto",
    } | extra


def test_detalhe_mostra_dados_e_acoes_para_o_criador(client, turno, usuario_operacional):
    AlocacaoFactory(turno=turno)
    client.force_login(usuario_operacional)
    resposta = client.get(reverse("escalas:turno_detalhe", args=[turno.pk]), **HTMX)
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "escalas/partials/_turno_detalhe.html" in [t.name for t in resposta.templates]
    assert turno.atividade.nome in html
    assert "Levar lanche" in html
    assert turno.alocacoes.get().nome_responsavel in html
    assert reverse("escalas:turno_editar", args=[turno.pk]) in html
    assert reverse("escalas:turno_excluir", args=[turno.pk]) in html


def test_detalhe_existe_so_no_modal(client, turno, usuario_operacional):
    client.force_login(usuario_operacional)
    for nome in ("turno_detalhe", "turno_editar", "turno_excluir"):
        resposta = client.get(reverse(f"escalas:{nome}", args=[turno.pk]))
        assert resposta.status_code == 302
        assert resposta.url.startswith(reverse("escalas:grade", args=[turno.escala.pk]))


def test_horarios_do_formulario_vao_de_meia_em_meia_hora(client, turno, usuario_operacional):
    client.force_login(usuario_operacional)
    html = client.get(reverse("escalas:turno_editar", args=[turno.pk]), **HTMX).content.decode()
    assert '<option value="08:30"' in html
    assert '<option value="08:15"' not in html
    assert '<option value="08:00" selected>' in html
    resposta = client.post(reverse("escalas:turno_editar", args=[turno.pk]),
                           _dados(turno, hora_inicio="10:15"), **HTMX)
    assert "Escolha um horário em hora cheia ou meia hora." in resposta.content.decode()


def test_ultimo_horario_do_dia_termina_em_23_59(client, usuario_operacional):
    client.force_login(usuario_operacional)
    resposta = client.post(reverse("escalas:calendario_turno_novo"), {
        "data": "2026-09-23", "hora_inicio": "23:00", "hora_fim": "23:59",
        "atividade": AtividadeFactory().pk, "vagas": 1,
    })
    assert resposta.status_code == 302
    assert Turno.objects.get().duracao == "1h"


def test_outro_usuario_ve_detalhe_sem_editar_nem_excluir(client, turno):
    outro = UsuarioFactory(perfil=Perfil.OPERACIONAL)
    client.force_login(outro)
    html = client.get(reverse("escalas:turno_detalhe", args=[turno.pk]), **HTMX).content.decode()
    assert turno.atividade.nome in html
    assert reverse("escalas:turno_editar", args=[turno.pk]) not in html
    assert reverse("escalas:turno_excluir", args=[turno.pk]) not in html
    assert client.get(reverse("escalas:turno_editar", args=[turno.pk])).status_code == 403
    assert client.post(reverse("escalas:turno_editar", args=[turno.pk]),
                       _dados(turno)).status_code == 403
    assert client.post(reverse("escalas:turno_excluir", args=[turno.pk])).status_code == 403
    assert Turno.objects.filter(pk=turno.pk).exists()


def test_admin_edita_turno_de_outra_pessoa(client, turno, usuario_admin):
    client.force_login(usuario_admin)
    html = client.get(reverse("escalas:turno_detalhe", args=[turno.pk]), **HTMX).content.decode()
    assert reverse("escalas:turno_editar", args=[turno.pk]) in html
    resposta = client.post(reverse("escalas:turno_editar", args=[turno.pk]), _dados(turno))
    assert resposta.status_code == 302
    turno.refresh_from_db()
    assert turno.hora_inicio == time(10, 0)
    assert turno.vagas == 2
    assert turno.observacoes == "Novo texto"


def test_edicao_por_htmx_redireciona_para_a_grade(client, turno, usuario_operacional):
    client.force_login(usuario_operacional)
    resposta = client.post(reverse("escalas:turno_editar", args=[turno.pk]), _dados(turno), **HTMX)
    assert resposta.status_code == 204
    assert resposta["HX-Redirect"].startswith(reverse("escalas:grade", args=[turno.escala.pk]))


def test_formulario_de_edicao_nao_tem_responsavel(client, turno, usuario_operacional):
    client.force_login(usuario_operacional)
    resposta = client.get(reverse("escalas:turno_editar", args=[turno.pk]), **HTMX)
    assert "escalas/partials/_turno_editar.html" in [t.name for t in resposta.templates]
    assert 'name="responsavel"' not in resposta.content.decode()


def test_admin_adiciona_pessoas_ate_o_limite(client, turno, usuario_admin):
    turno.vagas = 2
    turno.save()
    a, b, c = VoluntarioFactory(), VoluntarioFactory(), VoluntarioFactory()
    client.force_login(usuario_admin)
    url = reverse("escalas:alocar", args=[turno.pk])
    html = client.get(reverse("escalas:turno_detalhe", args=[turno.pk]), **HTMX).content.decode()
    assert "Adicionar pessoa" in html
    client.post(url, {"voluntario": a.pk}, **HTMX)
    resposta = client.post(url, {"voluntario": b.pk}, **HTMX)
    assert f'id="turno-{turno.pk}"' in resposta.content.decode()
    assert 'hx-swap-oob="outerHTML"' in resposta.content.decode()
    resposta = client.post(url, {"voluntario": c.pk}, **HTMX)
    html = resposta.content.decode()
    assert "O limite de 2 vagas já foi atingido" in html
    assert "Editar vagas" in html
    assert turno.alocacoes.count() == 2


def test_usuario_comum_so_se_adiciona(client, turno):
    comum = UsuarioFactory(perfil=Perfil.TECNICO)
    client.force_login(comum)
    url = reverse("escalas:alocar", args=[turno.pk])
    html = client.get(reverse("escalas:turno_detalhe", args=[turno.pk]), **HTMX).content.decode()
    assert "Me adicionar" in html
    assert "Adicionar pessoa" not in html
    assert client.post(url, {"voluntario": VoluntarioFactory().pk}, **HTMX).status_code == 403
    assert client.post(url, {"usuario": UsuarioFactory().pk}, **HTMX).status_code == 403
    assert client.get(reverse("escalas:disponiveis", args=[turno.pk])).status_code == 403
    resposta = client.post(url, **HTMX)
    assert resposta.status_code == 200
    assert turno.alocacoes.get().usuario == comum
    assert "Me adicionar" not in resposta.content.decode()


def test_usuario_comum_sai_mas_nao_tira_outra_pessoa(client, turno):
    comum = UsuarioFactory(perfil=Perfil.OPERACIONAL)
    minha = AlocacaoFactory(turno=turno, voluntario=None, usuario=comum)
    turno.vagas = 2
    turno.save()
    alheia = AlocacaoFactory(turno=turno)
    client.force_login(comum)
    html = client.get(reverse("escalas:turno_detalhe", args=[turno.pk]), **HTMX).content.decode()
    assert reverse("escalas:desalocar", args=[minha.pk]) in html
    assert reverse("escalas:desalocar", args=[alheia.pk]) not in html
    assert client.post(reverse("escalas:desalocar", args=[alheia.pk]), **HTMX).status_code == 403
    client.post(reverse("escalas:desalocar", args=[minha.pk]), **HTMX)
    assert list(turno.alocacoes.all()) == [alheia]


def test_reduzir_vagas_mantem_os_mais_antigos(client, turno, usuario_operacional):
    turno.vagas = 4
    turno.save()
    alocacoes = [AlocacaoFactory(turno=turno) for _ in range(4)]
    client.force_login(usuario_operacional)
    resposta = client.post(reverse("escalas:turno_editar", args=[turno.pk]),
                           _dados(turno, vagas=2), **HTMX)
    assert resposta.status_code == 204
    assert set(turno.alocacoes.all()) == set(alocacoes[:2])


def _novo_turno(**extra):
    return {"data": "2026-09-23", "hora_inicio": "09:00", "hora_fim": "11:00",
            "atividade": AtividadeFactory().pk} | extra


def test_criacao_aceita_varios_responsaveis_sem_exigir_todos(client, usuario_admin):
    a, b = VoluntarioFactory(), VoluntarioFactory()
    client.force_login(usuario_admin)
    resposta = client.post(reverse("escalas:calendario_turno_novo"),
                           _novo_turno(vagas=4, responsavel=[a.pk, "", b.pk, ""]))
    assert resposta.status_code == 302
    turno = Turno.objects.get()
    assert turno.vagas == 4
    assert {x.voluntario for x in turno.alocacoes.all()} == {a, b}


def test_criacao_recusa_mais_responsaveis_que_vagas_e_repetidos(client, usuario_admin):
    a, b = VoluntarioFactory(), VoluntarioFactory()
    client.force_login(usuario_admin)
    url = reverse("escalas:calendario_turno_novo")
    resposta = client.post(url, _novo_turno(vagas=1, responsavel=[a.pk, b.pk]))
    assert "Há 2 responsáveis para 1 vaga." in resposta.content.decode()
    resposta = client.post(url, _novo_turno(vagas=2, responsavel=[a.pk, a.pk]))
    assert "A mesma pessoa foi escolhida mais de uma vez." in resposta.content.decode()
    assert not Turno.objects.exists()


def test_formulario_renderiza_um_select_por_responsavel_escolhido(client, usuario_admin):
    a, b = VoluntarioFactory(), VoluntarioFactory()
    client.force_login(usuario_admin)
    resposta = client.post(reverse("escalas:calendario_turno_novo"),
                           _novo_turno(vagas=1, responsavel=[a.pk, b.pk]))
    html = resposta.content.decode()
    assert 'id="id_responsavel"' in html
    assert 'id="id_responsavel_1"' in html


def test_criacao_por_usuario_comum_so_oferece_ele_mesmo(client, usuario_operacional):
    outra = VoluntarioFactory()
    client.force_login(usuario_operacional)
    resposta = client.post(reverse("escalas:calendario_turno_novo"), {
        "data": "2026-09-23", "hora_inicio": "09:00", "hora_fim": "11:00",
        "atividade": AtividadeFactory().pk, "vagas": 1, "responsavel": outra.pk,
    })
    assert resposta.status_code == 200
    assert "responsavel" in resposta.context["form"].errors
    resposta = client.post(reverse("escalas:calendario_turno_novo"), {
        "data": "2026-09-23", "hora_inicio": "09:00", "hora_fim": "11:00",
        "atividade": AtividadeFactory().pk, "vagas": 1,
        "responsavel": f"usuario:{usuario_operacional.pk}",
    })
    assert resposta.status_code == 302
    assert Alocacao.objects.get().usuario == usuario_operacional


def test_edicao_invalida_por_htmx_devolve_formulario_com_erro(client, turno, usuario_operacional):
    client.force_login(usuario_operacional)
    resposta = client.post(reverse("escalas:turno_editar", args=[turno.pk]),
                           _dados(turno, hora_fim="09:00"), **HTMX)
    assert resposta.status_code == 200
    assert "O término precisa ser depois do início." in resposta.content.decode()


def test_edicao_que_gera_conflito_do_responsavel_e_recusada(client, turno, usuario_operacional):
    alocacao = AlocacaoFactory(turno=turno)
    outro = TurnoFactory(escala=turno.escala, data=turno.data,
                         hora_inicio=time(13, 0), hora_fim=time(15, 0))
    AlocacaoFactory(turno=outro, voluntario=alocacao.voluntario)
    client.force_login(usuario_operacional)
    resposta = client.post(reverse("escalas:turno_editar", args=[turno.pk]),
                           _dados(turno, hora_inicio="10:00", hora_fim="14:00"), **HTMX)
    assert resposta.status_code == 200
    assert "já está escalada neste horário" in resposta.content.decode()
    turno.refresh_from_db()
    assert turno.hora_fim == time(12, 0)


def test_criador_exclui_turno_e_libera_os_responsaveis(client, turno, usuario_operacional):
    alocacao = AlocacaoFactory(turno=turno)
    client.force_login(usuario_operacional)
    confirmacao = client.get(reverse("escalas:turno_excluir", args=[turno.pk]), **HTMX)
    assert "Excluir este turno?" in confirmacao.content.decode()
    resposta = client.post(reverse("escalas:turno_excluir", args=[turno.pk]), **HTMX)
    assert resposta.status_code == 204
    assert not Turno.objects.filter(pk=turno.pk).exists()
    assert not Alocacao.objects.filter(pk=alocacao.pk).exists()
    novo = TurnoFactory(escala=turno.escala, data=turno.data)
    livre = Alocacao(turno=novo, voluntario=alocacao.voluntario)
    livre.full_clean()


def test_criacao_registra_o_autor(client, usuario_operacional):
    client.force_login(usuario_operacional)
    client.post(reverse("escalas:calendario_turno_novo"), {
        "data": "2026-09-23", "hora_inicio": "09:00", "hora_fim": "11:00",
        "atividade": AtividadeFactory().pk, "vagas": 1,
    })
    assert Turno.objects.get().criado_por == usuario_operacional


def test_grade_liga_cada_turno_ao_seu_detalhe(client, turno, usuario_tecnico):
    client.force_login(usuario_tecnico)
    html = client.get(reverse("escalas:grade", args=[turno.escala.pk])).content.decode()
    assert f'data-turno-detalhe="{reverse("escalas:turno_detalhe", args=[turno.pk])}"' in html
    assert 'id="turno-detalhe"' in html
