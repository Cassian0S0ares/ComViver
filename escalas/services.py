from datetime import date, timedelta

from django.db.models import Count, F, QuerySet

from escalas.models import Alocacao, Turno
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


def grade_da_escala(escala) -> dict:
    """Monta a grade: linhas de faixa horaria, colunas de dia.

    Devolve `dias` (as colunas) e `linhas`, cada uma com a faixa e a lista de
    turnos por dia — None onde nao ha turno.
    """
    turnos = (
        escala.turnos.select_related("atividade")
        .prefetch_related("alocacoes__voluntario")
        .order_by("hora_inicio", "data")
    )

    dias = []
    dia = escala.data_inicio
    while dia <= escala.data_fim:
        dias.append(dia)
        dia += timedelta(days=1)

    faixas: dict[tuple, dict] = {}
    for turno in turnos:
        chave = (turno.hora_inicio, turno.hora_fim)
        faixa = faixas.setdefault(
            chave,
            {
                "hora_inicio": turno.hora_inicio,
                "hora_fim": turno.hora_fim,
                "por_dia": {d: None for d in dias},
            },
        )
        faixa["por_dia"][turno.data] = turno

    linhas = [
        {
            "hora_inicio": faixa["hora_inicio"],
            "hora_fim": faixa["hora_fim"],
            "celulas": [faixa["por_dia"][d] for d in dias],
        }
        for _, faixa in sorted(faixas.items())
    ]

    return {"dias": dias, "linhas": linhas}


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
