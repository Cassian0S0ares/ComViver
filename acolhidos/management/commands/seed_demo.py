from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction

from acolhidos.models import (
    Acolhido,
    DadosSaude,
    Destino,
    Escolaridade,
    FichaAcolhimento,
    Medicacao,
    Responsavel,
    Sexo,
    StatusAcolhido,
    Turno,
    VinculoFamiliar,
)

# Dados ficticios. Nenhum nome, processo ou endereco corresponde a pessoa real.

# (nome, nome social, idade, sexo). Os dois primeiros sao irmaos e dividem a
# mesma responsavel; o ultimo entra ja desligado.
ACOLHIDOS = [
    ("Ana Clara Ribeiro", "", 10, Sexo.FEMININO),
    ("Bruno Ribeiro", "", 7, Sexo.MASCULINO),
    ("Carolina Mendes Alves", "", 14, Sexo.FEMININO),
    ("Davi Nogueira", "", 4, Sexo.MASCULINO),
    ("Eduarda Pires Lima", "Duda", 12, Sexo.FEMININO),
    ("Felipe Andrade", "", 16, Sexo.MASCULINO),
    ("Gabriela Moura", "", 9, Sexo.FEMININO),
    ("Heitor Campos", "", 6, Sexo.MASCULINO),
    ("Isabela Duarte", "", 15, Sexo.FEMININO),
]

MOTIVOS = [
    "Negligência familiar",
    "Situação de rua da família",
    "Violência doméstica",
    "Abandono",
    "Genitores sem condições de cuidado no momento",
]

ORGAOS = ["Conselho Tutelar", "Vara da Infância e Juventude", "Ministério Público"]


def _serie(idade: int) -> str | None:
    if idade < 6:
        return None  # educacao infantil, sem escola registrada na demonstracao
    if idade <= 14:
        return f"{idade - 5}º ano do Ensino Fundamental"
    return f"{min(idade - 14, 3)}º ano do Ensino Médio"


class Command(BaseCommand):
    help = "Popula o banco com dados fictícios coerentes para demonstração."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limpar",
            action="store_true",
            help="Apaga TODOS os acolhidos e responsáveis antes de recriar. Só com DEBUG=True.",
        )
        parser.add_argument(
            "--forcar",
            action="store_true",
            help="Permite rodar com DEBUG=False. Use apenas em banco descartável.",
        )

    @transaction.atomic
    def handle(self, *args, **opcoes):
        # `--limpar` apaga acolhidos e responsaveis. Rodado por engano no banco
        # da instituicao, levaria junto a ficha de cada crianca. Por isso so
        # passa com DEBUG ligado, ou com --forcar explicito.
        if not settings.DEBUG and not opcoes["forcar"]:
            raise CommandError(
                "Este comando cria dados fictícios e não deve rodar em produção. "
                "Se o banco for descartável, repita com --forcar."
            )

        if opcoes["limpar"]:
            # Exclusao fisica de proposito: a logica deixaria os registros
            # ficticios no banco e a contagem dobraria a cada execucao.
            models.QuerySet.delete(Acolhido.todos.all())
            models.QuerySet.delete(Responsavel.todos.all())
            self.stdout.write("Dados anteriores removidos.")

        hoje = date.today()
        ultimo = len(ACOLHIDOS) - 1

        # Responsavel compartilhado por dois irmaos: o caso que exercita o
        # modelo de vinculo muitos-para-muitos.
        mae_ribeiro = Responsavel.objects.create(
            nome="Marta Ribeiro", telefone="35999990001", cidade="Itajubá", uf="MG"
        )

        for indice, (nome, social, idade, sexo) in enumerate(ACOLHIDOS):
            desligado = indice == ultimo
            acolhido = Acolhido.objects.create(
                nome=nome,
                nome_social=social,
                nascimento=date(hoje.year - idade, hoje.month, min(hoje.day, 28))
                - timedelta(days=40 + indice * 17),
                sexo=sexo,
                naturalidade="Itajubá",
                status=StatusAcolhido.DESLIGADO if desligado else StatusAcolhido.ACOLHIDO,
            )

            entrada = hoje - timedelta(days=60 + indice * 45)
            FichaAcolhimento.objects.create(
                acolhido=acolhido,
                data_entrada=entrada,
                motivo=MOTIVOS[indice % len(MOTIVOS)],
                orgao_requisitante=ORGAOS[indice % len(ORGAOS)],
                processo_numero=f"000{1000 + indice}-56.2026.8.13.0301",
                vara="Vara da Infância e Juventude de Itajubá",
                data_desligamento=hoje - timedelta(days=5) if desligado else None,
                destino=Destino.REINTEGRACAO if desligado else "",
            )

            DadosSaude.objects.create(
                acolhido=acolhido,
                tipo_sanguineo=["O+", "A+", "B+", "AB+"][indice % 4],
                alergias="Nenhuma conhecida" if indice % 3 else "Dipirona",
            )

            serie = _serie(idade)
            if serie:
                Escolaridade.objects.create(
                    acolhido=acolhido,
                    escola="E.E. Dom Pedro II",
                    serie=serie,
                    turno=Turno.MANHA if indice % 2 == 0 else Turno.TARDE,
                    ano_letivo=hoje.year,
                )

            if indice % 3 == 0:
                Medicacao.objects.create(
                    acolhido=acolhido,
                    nome="Vitamina D",
                    dosagem="1 gota",
                    frequencia="Manhã",
                    inicio=entrada,
                )

            if indice < 2:
                responsavel = mae_ribeiro  # Ana Clara e Bruno sao irmaos
            else:
                responsavel = Responsavel.objects.create(
                    nome=f"Responsável de {nome.split()[0]}",
                    telefone=f"3599999{1000 + indice}",
                    cidade="Itajubá",
                    uf="MG",
                )

            VinculoFamiliar.objects.create(
                acolhido=acolhido,
                responsavel=responsavel,
                parentesco="Mãe" if indice < 2 else "Avó",
                e_guardiao=indice % 2 == 0,
                autorizado_visita=True,
                autorizado_retirar=indice % 2 == 0,
            )

        from doacoes.demo import criar_doacoes_demo

        criar_doacoes_demo()
        self.stdout.write("Doadores, campanha e doações fictícias preparados.")
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(ACOLHIDOS)} acolhidos criados com ficha, saúde, escola e responsáveis."
            )
        )
