from datetime import date, time, timedelta

import pytest
from django.urls import reverse

from accounts.models import AcaoFicha, LogAcessoFicha
from acolhidos.factories import AcolhidoFactory, MedicacaoFactory
from acolhidos.models import Medicacao

pytestmark = pytest.mark.django_db

HOJE = date.today()


def dados(**extra):
    return {
        "nome": "Dipirona",
        "horarios": ["08:00", "20:00"],
        "inicio": HOJE.isoformat(),
        "fim": "",
        "observacoes": "500mg",
    } | extra


class TestAcesso:
    def test_operacional_nao_cadastra(self, client, usuario_operacional):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_operacional)
        url = reverse("acolhidos:medicacao_nova", args=[acolhido.pk])
        assert client.get(url).status_code == 403

    def test_operacional_nao_edita_nem_remove(self, client, usuario_operacional):
        medicacao = MedicacaoFactory()
        client.force_login(usuario_operacional)
        for rota in ("acolhidos:medicacao_editar", "acolhidos:medicacao_remover"):
            assert client.get(reverse(rota, args=[medicacao.pk])).status_code == 403

    def test_operacional_le_mas_nao_ve_os_botoes(self, client, usuario_operacional):
        """A equipe operacional precisa saber o que administrar, e so isso."""
        medicacao = MedicacaoFactory(nome="Dipirona")
        client.force_login(usuario_operacional)
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[medicacao.acolhido.pk])
        ).content.decode()
        assert "Dipirona" in conteudo
        assert reverse("acolhidos:medicacao_nova", args=[medicacao.acolhido.pk]) not in conteudo
        assert reverse("acolhidos:medicacao_editar", args=[medicacao.pk]) not in conteudo

    def test_tecnico_ve_os_botoes(self, client, usuario_tecnico):
        medicacao = MedicacaoFactory()
        client.force_login(usuario_tecnico)
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[medicacao.acolhido.pk])
        ).content.decode()
        assert reverse("acolhidos:medicacao_nova", args=[medicacao.acolhido.pk]) in conteudo
        assert reverse("acolhidos:medicacao_editar", args=[medicacao.pk]) in conteudo


class TestCadastro:
    def test_tecnico_cadastra_medicacao(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        resposta = client.post(reverse("acolhidos:medicacao_nova", args=[acolhido.pk]), dados())
        assert resposta.url == reverse("acolhidos:detalhe", args=[acolhido.pk])
        medicacao = Medicacao.em_vigor.get(acolhido=acolhido)
        assert medicacao.nome == "Dipirona"
        assert medicacao.criado_por == usuario_tecnico

    def test_cadastro_registra_no_log_da_ficha(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        client.post(reverse("acolhidos:medicacao_nova", args=[acolhido.pk]), dados())
        assert LogAcessoFicha.objects.filter(acolhido=acolhido, acao=AcaoFicha.EDIT).exists()

    def test_tecnico_corrige_a_dose_nas_observacoes(self, client, usuario_tecnico):
        medicacao = MedicacaoFactory(observacoes="500mg")
        client.force_login(usuario_tecnico)
        client.post(
            reverse("acolhidos:medicacao_editar", args=[medicacao.pk]),
            dados(observacoes="250mg", horarios=["07:00", "13:00", "21:00"]),
        )
        medicacao.refresh_from_db()
        assert medicacao.observacoes == "250mg"
        assert medicacao.horarios == [time(7), time(13), time(21)]
        assert medicacao.horarios_rotulo == "07:00 · 13:00 · 21:00"

    def test_exige_pelo_menos_um_horario(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        resposta = client.post(reverse("acolhidos:medicacao_nova", args=[acolhido.pk]),
                               dados(horarios=[]))
        assert "Marque pelo menos um horário." in resposta.content.decode()
        assert not Medicacao.objects.filter(acolhido=acolhido).exists()

    def test_horario_fora_da_lista_e_recusado(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        resposta = client.post(reverse("acolhidos:medicacao_nova", args=[acolhido.pk]),
                               dados(horarios=["08:15"]))
        assert resposta.status_code == 200
        assert not Medicacao.objects.filter(acolhido=acolhido).exists()

    def test_formulario_sugere_medicamentos_ja_registrados(self, client, usuario_tecnico):
        MedicacaoFactory(nome="Vitamina D")
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        html = client.get(reverse("acolhidos:medicacao_nova", args=[acolhido.pk])).content.decode()
        assert '<datalist id="medicamentos-lista"><option value="Vitamina D">' in html
        assert 'data-combobox' in html and 'value="13:00"' in html
        assert 'name="dosagem"' not in html and 'name="frequencia"' not in html

    def test_mesmo_medicamento_reaproveita_a_grafia_registrada(self, client, usuario_tecnico):
        MedicacaoFactory(nome="Vitamina D")
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        client.post(reverse("acolhidos:medicacao_nova", args=[acolhido.pk]),
                    dados(nome="  vitamina   d "))
        assert Medicacao.objects.get(acolhido=acolhido).nome == "Vitamina D"

    def test_fim_antes_do_inicio_e_recusado(self, client, usuario_tecnico):
        acolhido = AcolhidoFactory()
        client.force_login(usuario_tecnico)
        resposta = client.post(
            reverse("acolhidos:medicacao_nova", args=[acolhido.pk]),
            dados(inicio=HOJE.isoformat(), fim=(HOJE - timedelta(days=1)).isoformat()),
        )
        assert resposta.status_code == 200
        assert "anterior ao início" in resposta.content.decode()
        assert not Medicacao.objects.filter(acolhido=acolhido).exists()


class TestEncerrarERemover:
    def test_encerrar_tira_do_cuidado_diario(self, client, usuario_tecnico):
        """Remedio suspenso nao pode continuar na lista de quem administra."""
        medicacao = MedicacaoFactory(inicio=HOJE - timedelta(days=30))
        client.force_login(usuario_tecnico)
        client.post(
            reverse("acolhidos:medicacao_editar", args=[medicacao.pk]),
            dados(
                nome=medicacao.nome,
                inicio=medicacao.inicio.isoformat(),
                fim=(HOJE - timedelta(days=1)).isoformat(),
            ),
        )
        contexto = client.get(reverse("acolhidos:detalhe", args=[medicacao.acolhido.pk])).context
        assert list(contexto["medicacoes_em_vigor"]) == []

    def test_encerrada_continua_no_historico_da_equipe_tecnica(self, client, usuario_tecnico):
        medicacao = MedicacaoFactory(
            nome="Amoxicilina",
            inicio=HOJE - timedelta(days=30),
            fim=HOJE - timedelta(days=10),
        )
        client.force_login(usuario_tecnico)
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[medicacao.acolhido.pk])
        ).content.decode()
        assert "Amoxicilina" in conteudo

    def test_historico_de_medicacao_nao_chega_ao_operacional(self, client, usuario_operacional):
        medicacao = MedicacaoFactory(
            nome="Amoxicilina",
            inicio=HOJE - timedelta(days=30),
            fim=HOJE - timedelta(days=10),
        )
        client.force_login(usuario_operacional)
        conteudo = client.get(
            reverse("acolhidos:detalhe", args=[medicacao.acolhido.pk])
        ).content.decode()
        assert "Amoxicilina" not in conteudo

    def test_remover_e_exclusao_logica(self, client, usuario_tecnico):
        """Lancamento errado sai da tela, mas a linha fica no banco."""
        medicacao = MedicacaoFactory()
        client.force_login(usuario_tecnico)
        resposta = client.post(reverse("acolhidos:medicacao_remover", args=[medicacao.pk]))
        assert resposta.status_code == 302
        assert not Medicacao.objects.filter(pk=medicacao.pk).exists()
        assert Medicacao.todos.filter(pk=medicacao.pk).exists()

    def test_remocao_pede_confirmacao_em_pagina_propria(self, client, usuario_tecnico):
        medicacao = MedicacaoFactory(nome="Dipirona")
        client.force_login(usuario_tecnico)
        resposta = client.get(reverse("acolhidos:medicacao_remover", args=[medicacao.pk]))
        assert resposta.status_code == 200
        assert "Dipirona" in resposta.content.decode()
        assert Medicacao.objects.filter(pk=medicacao.pk).exists()
