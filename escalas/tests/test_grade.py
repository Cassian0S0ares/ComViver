from datetime import date, time, timedelta

import pytest
from django.urls import reverse

from escalas.factories import AlocacaoFactory, EscalaFactory, TurnoFactory
from escalas.models import Alocacao, Escala, StatusEscala
from escalas.services import turnos_descobertos_proximos, voluntarios_disponiveis
from voluntarios.factories import DisponibilidadeFactory, VoluntarioFactory
from voluntarios.models import StatusVoluntario
from voluntarios.models import Turno as TurnoDisponibilidade

pytestmark = pytest.mark.django_db


class TestVoluntariosDisponiveis:
    def test_sugere_quem_declarou_o_dia_e_turno(self):
        segunda = date(2026, 9, 21)  # segunda-feira
        turno = TurnoFactory(data=segunda, hora_inicio=time(8, 0), hora_fim=time(12, 0))
        disponivel = VoluntarioFactory(nome="Ana")
        DisponibilidadeFactory(
            voluntario=disponivel, dia_semana=0, turno=TurnoDisponibilidade.MANHA
        )
        VoluntarioFactory(nome="Bruno")  # sem disponibilidade declarada

        nomes = [v.nome for v in voluntarios_disponiveis(turno)]
        assert nomes == ["Ana"]

    def test_nao_sugere_quem_declarou_outro_turno(self):
        segunda = date(2026, 9, 21)
        turno = TurnoFactory(data=segunda, hora_inicio=time(8, 0), hora_fim=time(12, 0))
        voluntario = VoluntarioFactory()
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=0, turno=TurnoDisponibilidade.NOITE
        )
        assert voluntario not in voluntarios_disponiveis(turno)

    def test_nao_sugere_voluntario_inativo(self):
        segunda = date(2026, 9, 21)
        turno = TurnoFactory(data=segunda, hora_inicio=time(8, 0), hora_fim=time(12, 0))
        inativo = VoluntarioFactory(status=StatusVoluntario.INATIVO)
        DisponibilidadeFactory(
            voluntario=inativo, dia_semana=0, turno=TurnoDisponibilidade.MANHA
        )
        assert inativo not in voluntarios_disponiveis(turno)

    def test_nao_sugere_quem_ja_esta_alocado_no_turno(self):
        segunda = date(2026, 9, 21)
        turno = TurnoFactory(data=segunda, hora_inicio=time(8, 0), hora_fim=time(12, 0))
        voluntario = VoluntarioFactory()
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=0, turno=TurnoDisponibilidade.MANHA
        )
        AlocacaoFactory(turno=turno, voluntario=voluntario)
        assert voluntario not in voluntarios_disponiveis(turno)

    def test_nao_sugere_quem_tem_conflito_de_horario(self):
        """Sugerir quem vai ser recusado pelo clean() so gera frustracao."""
        segunda = date(2026, 9, 21)
        voluntario = VoluntarioFactory()
        DisponibilidadeFactory(
            voluntario=voluntario, dia_semana=0, turno=TurnoDisponibilidade.MANHA
        )
        ocupado = TurnoFactory(data=segunda, hora_inicio=time(8, 0), hora_fim=time(12, 0))
        AlocacaoFactory(turno=ocupado, voluntario=voluntario)

        novo = TurnoFactory(data=segunda, hora_inicio=time(10, 0), hora_fim=time(14, 0))
        assert voluntario not in voluntarios_disponiveis(novo)


class TestTelaDaGrade:
    def test_tecnico_ve_a_grade_mas_nao_aloca(self, client, usuario_tecnico):
        escala = EscalaFactory()
        client.force_login(usuario_tecnico)
        assert client.get(reverse("escalas:grade", args=[escala.pk])).status_code == 200
        turno = TurnoFactory(escala=escala)
        voluntario = VoluntarioFactory()
        resposta = client.post(
            reverse("escalas:alocar", args=[turno.pk]), {"voluntario": voluntario.pk}
        )
        assert resposta.status_code == 403

    def test_operacional_aloca(self, client, usuario_operacional):
        escala = EscalaFactory()
        turno = TurnoFactory(escala=escala)
        voluntario = VoluntarioFactory()
        client.force_login(usuario_operacional)
        client.post(reverse("escalas:alocar", args=[turno.pk]), {"voluntario": voluntario.pk})
        assert Alocacao.objects.filter(turno=turno, voluntario=voluntario).exists()

    def test_alocacao_conflitante_devolve_mensagem(self, client, usuario_operacional):
        hoje = date.today()
        escala = EscalaFactory()
        voluntario = VoluntarioFactory(nome="Ana Souza")
        ocupado = TurnoFactory(
            escala=escala, data=hoje, hora_inicio=time(8, 0), hora_fim=time(12, 0)
        )
        AlocacaoFactory(turno=ocupado, voluntario=voluntario)
        novo = TurnoFactory(
            escala=escala, data=hoje, hora_inicio=time(10, 0), hora_fim=time(14, 0)
        )

        client.force_login(usuario_operacional)
        resposta = client.post(
            reverse("escalas:alocar", args=[novo.pk]), {"voluntario": voluntario.pk}
        )
        assert "já está escalada" in resposta.content.decode()
        assert Alocacao.objects.filter(turno=novo).count() == 0

    def test_mensagem_de_conflito_escapa_o_nome(self, client, usuario_operacional):
        """O nome do voluntario entra na mensagem de erro. Sem escape, um nome
        com marcacao viraria XSS refletido em quem monta a escala."""
        hoje = date.today()
        escala = EscalaFactory()
        voluntario = VoluntarioFactory(nome="<script>alert(1)</script>")
        ocupado = TurnoFactory(
            escala=escala, data=hoje, hora_inicio=time(8, 0), hora_fim=time(12, 0)
        )
        AlocacaoFactory(turno=ocupado, voluntario=voluntario)
        novo = TurnoFactory(
            escala=escala, data=hoje, hora_inicio=time(10, 0), hora_fim=time(14, 0)
        )

        client.force_login(usuario_operacional)
        resposta = client.post(
            reverse("escalas:alocar", args=[novo.pk]), {"voluntario": voluntario.pk}
        )
        conteudo = resposta.content.decode()
        assert "<script>alert(1)</script>" not in conteudo
        assert "&lt;script&gt;" in conteudo

    def test_alocar_voluntario_inativo_e_recusado(self, client, usuario_operacional):
        from voluntarios.models import StatusVoluntario

        turno = TurnoFactory()
        inativo = VoluntarioFactory(status=StatusVoluntario.INATIVO)
        client.force_login(usuario_operacional)
        resposta = client.post(
            reverse("escalas:alocar", args=[turno.pk]), {"voluntario": inativo.pk}
        )
        assert resposta.status_code == 404
        assert not Alocacao.objects.filter(turno=turno).exists()

    def test_desalocar_remove_a_alocacao(self, client, usuario_operacional):
        alocacao = AlocacaoFactory()
        client.force_login(usuario_operacional)
        client.post(reverse("escalas:desalocar", args=[alocacao.pk]))
        assert not Alocacao.objects.filter(pk=alocacao.pk).exists()

    def test_grade_marca_turno_descoberto(self, client, usuario_operacional):
        escala = EscalaFactory()
        TurnoFactory(escala=escala, vagas=2)
        client.force_login(usuario_operacional)
        resposta = client.get(reverse("escalas:grade", args=[escala.pk]))
        assert resposta.context["escala"].turnos_descobertos == 1


class TestPublicacao:
    def test_publicar_muda_o_status(self, client, usuario_operacional):
        escala = EscalaFactory()
        TurnoFactory(escala=escala)
        client.force_login(usuario_operacional)
        client.post(reverse("escalas:publicar", args=[escala.pk]))
        escala.refresh_from_db()
        assert escala.status == StatusEscala.PUBLICADA

    def test_escala_sem_turno_nao_e_publicada(self, client, usuario_operacional):
        escala = EscalaFactory()
        client.force_login(usuario_operacional)
        client.post(reverse("escalas:publicar", args=[escala.pk]), follow=True)
        escala.refresh_from_db()
        assert escala.status == StatusEscala.RASCUNHO

    def test_tecnico_nao_publica(self, client, usuario_tecnico):
        escala = EscalaFactory()
        client.force_login(usuario_tecnico)
        assert client.post(reverse("escalas:publicar", args=[escala.pk])).status_code == 403


class TestTurnosDescobertosProximos:
    def test_lista_turnos_sem_gente_nos_proximos_dias(self):
        TurnoFactory(data=date.today() + timedelta(days=2), vagas=1)
        coberto = TurnoFactory(data=date.today() + timedelta(days=3), vagas=1)
        AlocacaoFactory(turno=coberto)
        assert turnos_descobertos_proximos(dias=7).count() == 1

    def test_ignora_turno_fora_da_janela(self):
        TurnoFactory(data=date.today() + timedelta(days=30), vagas=1)
        assert turnos_descobertos_proximos(dias=7).count() == 0

    def test_ignora_turno_no_passado(self):
        TurnoFactory(data=date.today() - timedelta(days=2), vagas=1)
        assert turnos_descobertos_proximos(dias=7).count() == 0


class TestEscalaSempreSemanal:
    """A escala e sempre uma tabela de horario de uma semana: o formulario so
    pede o inicio, e o termino e sempre calculado como 6 dias depois — mesmo
    que alguem tente forcar outro valor no POST."""

    def test_formulario_nao_pede_o_termino(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        resposta = client.get(reverse("escalas:nova"))
        assert "data_fim" not in resposta.context["form"].fields

    def test_escala_criada_cobre_sempre_uma_semana(self, client, usuario_operacional):
        client.force_login(usuario_operacional)
        inicio = date(2026, 9, 21)  # segunda-feira
        client.post(
            reverse("escalas:nova"),
            {
                "titulo": "Semana teste",
                "data_inicio": inicio.isoformat(),
                "data_fim": (inicio + timedelta(days=20)).isoformat(),  # tentativa ignorada
                "observacoes": "",
            },
        )
        escala = Escala.objects.get(titulo="Semana teste")
        assert escala.data_fim == inicio + timedelta(days=6)


class TestSanidadeDasPaginas:
    """As paginas reais renderizam, sem erro de template, para os perfis que
    tem acesso a cada uma — inclusive com turnos e alocacoes na grade."""

    def test_lista_renderiza_para_admin_e_tecnico(self, client, usuario_admin, usuario_tecnico):
        EscalaFactory()
        client.force_login(usuario_admin)
        assert client.get(reverse("escalas:lista")).status_code == 200

        client.force_login(usuario_tecnico)
        assert client.get(reverse("escalas:lista")).status_code == 200

    def test_nova_renderiza_para_admin_e_e_recusada_para_tecnico(
        self, client, usuario_admin, usuario_tecnico
    ):
        client.force_login(usuario_admin)
        assert client.get(reverse("escalas:nova")).status_code == 200

        client.force_login(usuario_tecnico)
        assert client.get(reverse("escalas:nova")).status_code == 403

    def test_grade_com_turnos_e_alocacoes_renderiza_para_admin_e_tecnico(
        self, client, usuario_admin, usuario_tecnico
    ):
        escala = EscalaFactory()
        turno = TurnoFactory(escala=escala, vagas=2)
        AlocacaoFactory(turno=turno)
        TurnoFactory(escala=escala)  # turno descoberto, sem alocacao

        client.force_login(usuario_admin)
        assert client.get(reverse("escalas:grade", args=[escala.pk])).status_code == 200

        client.force_login(usuario_tecnico)
        assert client.get(reverse("escalas:grade", args=[escala.pk])).status_code == 200

    def test_disponiveis_renderiza_para_admin_e_e_recusado_para_tecnico(
        self, client, usuario_admin, usuario_tecnico
    ):
        turno = TurnoFactory()

        client.force_login(usuario_admin)
        assert client.get(reverse("escalas:disponiveis", args=[turno.pk])).status_code == 200

        client.force_login(usuario_tecnico)
        assert client.get(reverse("escalas:disponiveis", args=[turno.pk])).status_code == 403
