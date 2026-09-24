from datetime import date, timedelta

from django.db.models import Count, F, QuerySet
from django.utils import timezone

from accounts.models import Usuario
from escalas.models import Alocacao, StatusAlocacao, Turno
from voluntarios.models import StatusVoluntario, Voluntario


def voluntarios_disponiveis(turno: Turno) -> QuerySet[Voluntario]:
    """Voluntarios que podem assumir este turno.

    Filtra por quatro criterios, nesta ordem: esta ativo, declarou o dia e o
    turno, ainda nao esta neste turno, e nao tem conflito de horario no dia.

    O ultimo criterio evita sugerir alguem que o clean() do model recusaria —
    oferecer e depois recusar so gera frustracao.
    """
    dia_semana = turno.data.weekday()

    candidatos = Voluntario.objects.filter(
        status=StatusVoluntario.ATIVO,
        disponibilidades__dia_semana=dia_semana,
        disponibilidades__turno=turno.turno_do_dia,
    ).exclude(alocacoes__turno=turno).distinct()

    ocupados_no_dia = (
        Alocacao.objects.filter(turno__data=turno.data)
        .exclude(turno=turno)
        .select_related("turno")
    )
    com_conflito = {
        alocacao.voluntario_id
        for alocacao in ocupados_no_dia
        if turno.sobrepoe(alocacao.turno)
    }

    return candidatos.exclude(pk__in=com_conflito)


def usuarios_disponiveis(turno):
    ocupados = Alocacao.objects.filter(
        usuario__isnull=False, turno__data=turno.data,
        turno__hora_inicio__lt=turno.hora_fim, turno__hora_fim__gt=turno.hora_inicio,
    ).values_list("usuario_id", flat=True)
    return Usuario.objects.filter(is_active=True).exclude(pk__in=ocupados)


def grade_da_escala(escala=None, inicio=None) -> dict:
    """Sete dias com posições em minutos e faixas paralelas para sobreposições."""
    inicio = inicio or (escala.data_inicio if escala else timezone.localdate())
    if escala:
        inicio = max(escala.data_inicio, min(inicio, escala.data_fim))
    inicio -= timedelta(days=(inicio.weekday() + 1) % 7)
    dias = [inicio + timedelta(days=i) for i in range(7)]
    base = escala.turnos if escala else Turno.objects.filter(escala__deleted_at__isnull=True)
    turnos = list(
        base.filter(data__range=(dias[0], dias[-1])).select_related("atividade")
        .prefetch_related("alocacoes__voluntario", "alocacoes__usuario")
        .order_by("hora_inicio", "hora_fim", "pk")
    )
    colunas = []
    for dia in dias:
        finais = []
        eventos = []
        for turno in (t for t in turnos if t.data == dia):
            comeco = turno.hora_inicio.hour * 60 + turno.hora_inicio.minute
            fim = turno.hora_fim.hour * 60 + turno.hora_fim.minute
            faixa = next((i for i, final in enumerate(finais) if final <= comeco), len(finais))
            if faixa == len(finais):
                finais.append(fim)
            else:
                finais[faixa] = fim
            eventos.append({"turno": turno, "inicio": comeco + 1,
                            "fim": fim + 1, "faixa": faixa + 1})
        colunas.append({"data": dia, "eventos": eventos,
                        "faixas": max(1, len(finais)),
                        "ativo": not escala or escala.data_inicio <= dia <= escala.data_fim})
    horas = [{"rotulo": f"{h:02d}:00", "fim": f"{h + 1:02d}:00" if h < 23 else "23:59",
              "inicio": h * 60 + 1, "linha_fim": (h + 1) * 60 + 1} for h in range(24)]
    return {"dias": dias, "colunas": colunas, "horas": horas,
            "inicio_semana": dias[0], "fim_semana": dias[-1],
            "total_turnos": len(turnos),
            "turnos_descobertos": sum(t.esta_descoberto for t in turnos),
            "semana_anterior": inicio - timedelta(days=7)
            if not escala or inicio > escala.data_inicio else None,
            "semana_seguinte": inicio + timedelta(days=7)
            if not escala or dias[-1] < escala.data_fim else None}


def turnos_descobertos_proximos(dias: int = 7) -> QuerySet[Turno]:
    """Turnos com vaga em aberto na janela a frente.

    E a pergunta real do coordenador: onde esta o buraco.
    """
    hoje = date.today()
    return (
        Turno.objects.filter(data__gte=hoje, data__lte=hoje + timedelta(days=dias))
        .annotate(ocupadas=Count("alocacoes"))
        .filter(ocupadas__lt=F("vagas"))
        .select_related("atividade", "escala")
        .order_by("data", "hora_inicio")
    )


def _minhas_alocacoes(usuario):
    return Alocacao.objects.filter(
        usuario=usuario, turno__deleted_at__isnull=True,
        turno__escala__deleted_at__isnull=True,
    ).select_related("turno__atividade")


def agenda_do_dia(usuario, dia) -> list:
    """To-do pessoal: os turnos do dia em que a pessoa esta escalada.

    Cada item traz `feito`, `liberado` (so se marca a partir do dia do
    turno) e `colegas`, os demais responsaveis do mesmo turno.
    """
    hoje = timezone.localdate()
    itens = list(
        _minhas_alocacoes(usuario).filter(turno__data=dia)
        .prefetch_related("turno__alocacoes__usuario", "turno__alocacoes__voluntario")
        .order_by("turno__hora_inicio", "turno__hora_fim", "pk")
    )
    for item in itens:
        preparar_item_da_agenda(item, hoje)
    return itens


def preparar_item_da_agenda(item, hoje=None):
    hoje = hoje or timezone.localdate()
    item.feito = item.status == StatusAlocacao.CONFIRMADO
    item.liberado = item.turno.data <= hoje
    item.colegas = [a.nome_responsavel for a in item.turno.alocacoes.all() if a.pk != item.pk]
    return item


def proximo_turno(usuario, depois_de):
    return (
        _minhas_alocacoes(usuario).filter(turno__data__gt=depois_de)
        .order_by("turno__data", "turno__hora_inicio").first()
    )
