"""Apaga os dados do sistema (menos usuarios) e cria um conjunto de exemplo.

Uso: python manage.py popular_exemplo --apagar-tudo

Mantem usuarios, grupos, sessoes e as tabelas de apoio (categorias do estoque,
atividades das escalas, funcoes de voluntario). Todo o resto e apagado de
verdade (TRUNCATE), inclusive historicos, e recriado com dados ficticios.
Nenhum e-mail e enviado: o aviso de nova alocacao fica desligado e o backend
de e-mail vira memoria enquanto o comando roda.
"""

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, models, transaction
from django.db.models.signals import post_save
from django.test.utils import override_settings
from django.utils import timezone

APPS_APAGADOS = ["acolhidos", "doacoes", "voluntarios", "escalas", "estoque"]
TABELAS_DE_APOIO = {"escalas.atividade", "estoque.categoriaitem", "voluntarios.funcao"}
EXTRAS_APAGADOS = ["accounts.logacessoficha", "core.arquivoenviado"]

VOLUNTARIOS = [
    "Aline Bastos", "Bernardo Teixeira", "Camila Rezende", "Diego Faria", "Elaine Couto",
    "Fábio Monteiro", "Giovana Prado", "Henrique Sales", "Ingrid Tavares", "João Pedro Lacerda",
    "Karina Assis", "Leonardo Pimenta", "Marina Vasconcelos", "Nelson Quintão", "Olívia Barreto",
    "Paulo Rangel", "Renata Siqueira", "Sônia Macedo",
]
FUNCOES = ["Cozinha", "Reforço escolar", "Recreação", "Manutenção", "Costura", "Transporte"]

DOADORES_PJ = [
    "Padaria Pão Nosso", "Supermercado Bom Preço", "Farmácia Vida & Saúde",
    "Paróquia São Benedito", "Rotary Club Itajubá", "Loja Tecidos Mantiqueira",
    "Papelaria Estrela", "Açougue e Mercearia Serra Azul",
]
DOADORES_PF = [
    "Ana Beatriz Rocha", "Carlos Eduardo Nunes", "Daniela Moreira", "Eduardo Guimarães",
    "Fernanda Lopes", "Gustavo Henrique Brito", "Helena Cardoso", "Igor Fonseca",
    "Juliana Martins", "Lucas Amaral", "Mariana Figueiredo", "Otávio Castro",
    "Patrícia Menezes", "Roberto Salgado", "Simone Aguiar", "Tatiane Peixoto",
    "Vinícius Rodrigues",
]

# (categoria, item, faixa de quantidade, dias de validade a partir da chegada ou None)
ITENS = [
    ("Alimentos", "Arroz 5kg", (5, 30), (180, 360)),
    ("Alimentos", "Feijão carioca 1kg", (5, 30), (150, 300)),
    ("Alimentos", "Macarrão espaguete 500g", (10, 40), (200, 400)),
    ("Alimentos", "Leite integral 1L", (12, 48), (40, 120)),
    ("Alimentos", "Óleo de soja 900ml", (4, 20), (200, 360)),
    ("Alimentos", "Açúcar cristal 1kg", (5, 20), (300, 540)),
    ("Alimentos", "Café 500g", (3, 12), (120, 300)),
    ("Alimentos", "Biscoito maisena", (10, 40), (60, 180)),
    ("Alimentos", "Achocolatado 400g", (4, 15), (150, 300)),
    ("Alimentos", "Molho de tomate", (10, 30), (180, 400)),
    ("Alimentos", "Sardinha em lata", (10, 36), (365, 720)),
    ("Alimentos", "Iogurte de morango", (6, 24), (10, 25)),
    ("Higiene pessoal", "Sabonete infantil", (10, 40), (400, 800)),
    ("Higiene pessoal", "Creme dental", (6, 24), (400, 700)),
    ("Higiene pessoal", "Escova de dentes", (6, 24), None),
    ("Higiene pessoal", "Shampoo infantil", (3, 12), (400, 720)),
    ("Higiene pessoal", "Fralda tamanho M", (20, 80), None),
    ("Higiene pessoal", "Papel higiênico", (12, 64), None),
    ("Limpeza", "Detergente", (6, 24), None),
    ("Limpeza", "Sabão em pó 1kg", (3, 12), None),
    ("Limpeza", "Água sanitária 2L", (3, 10), None),
    ("Limpeza", "Desinfetante", (3, 12), None),
    ("Vestuário", "Camiseta infantil", (5, 30), None),
    ("Vestuário", "Calça de moletom", (3, 15), None),
    ("Vestuário", "Casaco de frio", (2, 12), None),
    ("Vestuário", "Meias (par)", (10, 40), None),
    ("Vestuário", "Tênis infantil", (1, 6), None),
    ("Material escolar", "Caderno 10 matérias", (5, 20), None),
    ("Material escolar", "Lápis preto", (20, 60), None),
    ("Material escolar", "Caixa de lápis de cor", (5, 15), None),
    ("Material escolar", "Mochila", (1, 6), None),
    ("Utensílios", "Toalha de banho", (2, 10), None),
    ("Utensílios", "Jogo de lençol", (1, 6), None),
    ("Outros", "Livro infantil", (3, 15), None),
    ("Outros", "Brinquedo educativo", (2, 10), None),
]

SERVICOS = ["Corte de cabelo", "Aula de violão", "Consulta odontológica", "Manutenção elétrica",
            "Oficina de pintura"]

# (atividade, inicio, fim, vagas, dias da semana python weekday, so equipe)
TURNOS = [
    ("Cozinha e alimentação", time(7), time(11), 2, range(7), False),
    ("Limpeza e organização", time(8), time(10), 1, (0, 3), False),
    ("Reunião de equipe", time(9), time(10, 30), 4, (1,), True),
    ("Apoio à rotina", time(11), time(14), 1, range(5), False),
    ("Atendimento técnico", time(13), time(15), 1, (0, 2, 4), True),
    ("Acompanhamento escolar", time(14), time(16, 30), 2, range(5), False),
    ("Recreação", time(15), time(17), 2, (2, 5, 6), False),
    ("Portaria e recepção", time(18), time(22), 1, range(7), False),
]

MEDICACOES_EXTRAS = [
    # (indice do acolhido, nome, horarios, observacoes, dias de uso ja feitos, dura dias)
    (1, "Sulfato ferroso", [time(12)], "10 gotas, antes do almoço", 40, None),
    (2, "Loratadina", [time(20)], "1 comprimido", 15, None),
    (4, "Amoxicilina", [time(8), time(16), time(0)], "5 ml · até terminar o frasco", 3, 7),
    (5, "Metilfenidato", [time(7), time(12)], "1 comprimido, com comida", 120, None),
    (6, "Dipirona", [time(8), time(14), time(20)], "Só se tiver febre acima de 37,8 °C", 1, 3),
    (7, "Vitamina C", [time(9)], "1 comprimido efervescente", 30, None),
]


class Command(BaseCommand):
    help = "Apaga os dados (menos usuários) e cria dados de exemplo em quantidade."

    def add_arguments(self, parser):
        parser.add_argument("--apagar-tudo", action="store_true",
                            help="Confirma que todos os dados, menos usuários, serão apagados.")
        parser.add_argument("--forcar", action="store_true",
                            help="Permite rodar com DEBUG=False. Só em banco descartável.")

    def handle(self, *args, **opcoes):
        if not opcoes["apagar_tudo"]:
            raise CommandError("Isto apaga todos os dados menos os usuários. Repita com --apagar-tudo.")
        if not settings.DEBUG and not opcoes["forcar"]:
            raise CommandError("DEBUG está desligado. Se o banco for descartável, use --forcar.")

        from escalas.models import Alocacao
        from escalas.signals import avisar_nova_alocacao

        self.rng = random.Random(2026)
        self.hoje = timezone.localdate()
        post_save.disconnect(avisar_nova_alocacao, sender=Alocacao)
        try:
            with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
                with transaction.atomic():
                    self._apagar()
                    self._preparar_usuarios()
                    self._acolhidos()
                    self._voluntarios()
                    self._doacoes()
                    self._estoque_manual_e_baixas()
                    self._escalas()
        finally:
            post_save.connect(avisar_nova_alocacao, sender=Alocacao)
        self.stdout.write(self.style.SUCCESS("Dados de exemplo prontos."))

    # ------------------------------------------------------------------ limpeza
    def _apagar(self):
        modelos = []
        for rotulo in APPS_APAGADOS:
            modelos += [m for m in apps.get_app_config(rotulo).get_models(include_auto_created=True)
                        if m._meta.label_lower not in TABELAS_DE_APOIO]
        for rotulo in EXTRAS_APAGADOS:
            try:
                modelos.append(apps.get_model(rotulo))
            except LookupError:
                pass
        tabelas = sorted({m._meta.db_table for m in modelos})
        with connection.cursor() as cursor:
            # FK adiada pendente na mesma transacao impede o TRUNCATE.
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cursor.execute("TRUNCATE " + ", ".join(connection.ops.quote_name(t) for t in tabelas)
                           + " RESTART IDENTITY CASCADE")
        # Tabelas de apoio continuam; garante as que vem das migracoes.
        from importlib import import_module

        editor = SimpleNamespace(connection=connection)  # o que as funcoes de migracao usam
        import_module("escalas.migrations.0003_atividades_iniciais").cadastrar_atividades(apps, editor)
        import_module("estoque.migrations.0002_categorias_iniciais").cadastrar_categorias(apps, editor)
        self.stdout.write(f"{len(tabelas)} tabelas esvaziadas (usuários preservados).")

    def _preparar_usuarios(self):
        from accounts.models import Perfil, Usuario

        self.usuarios = list(Usuario.objects.filter(is_active=True))
        if not self.usuarios:
            raise CommandError("Nenhum usuário ativo: crie ao menos um antes.")
        self.gestao = [u for u in self.usuarios if u.perfil in (Perfil.ADMIN, Perfil.OPERACIONAL)] \
            or self.usuarios
        self.abastece = [u for u in self.usuarios if u.perfil in (Perfil.ADMIN, Perfil.TECNICO)] \
            or self.usuarios
        self.tecnicos = [u for u in self.usuarios if u.perfil == Perfil.TECNICO] or self.abastece

    def _datar(self, modelo, pk, quando):
        """criado_em e auto_now_add: reescreve para a data de exemplo."""
        momento = timezone.make_aware(datetime.combine(quando, time(self.rng.randint(8, 17),
                                                                     self.rng.choice((0, 15, 30, 45)))))
        campos = {"criado_em": momento}
        if any(f.name == "atualizado_em" for f in modelo._meta.fields):
            campos["atualizado_em"] = momento
        modelo._base_manager.filter(pk=pk).update(**campos)

    # ---------------------------------------------------------------- acolhidos
    def _acolhidos(self):
        from acolhidos.models import Acolhido, Medicacao

        call_command("seed_demo", forcar=True, stdout=self.stdout)
        # O seed de acolhidos tambem cria doacoes de demonstracao; aqui elas
        # sao substituidas pelo conjunto maior abaixo.
        from doacoes.demo import MARCADOR
        from doacoes.models import Campanha, Doacao, Doador

        # Exclusao fisica: a logica deixaria as linhas de demonstracao no banco.
        for modelo, filtro in [(Doacao, {"observacoes": MARCADOR}),
                               (Campanha, {"descricao": MARCADOR}),
                               (Doador, {"observacoes": MARCADOR})]:
            models.QuerySet.delete(modelo.todos.filter(**filtro))

        ativos = list(Acolhido.objects.filter(status="ACOLHIDO").order_by("pk"))
        for indice, nome, horarios, obs, dias_uso, dura in MEDICACOES_EXTRAS:
            if indice >= len(ativos):
                continue
            inicio = self.hoje - timedelta(days=dias_uso)
            Medicacao.objects.create(
                acolhido=ativos[indice], nome=nome, horarios=horarios, observacoes=obs,
                inicio=inicio, fim=inicio + timedelta(days=dura) if dura else None,
                criado_por=self.rng.choice(self.tecnicos),
            )
        # Um remedio ja encerrado, para o historico da ficha.
        Medicacao.objects.create(
            acolhido=ativos[0], nome="Amoxicilina", horarios=[time(8), time(20)],
            observacoes="5 ml", inicio=self.hoje - timedelta(days=70),
            fim=self.hoje - timedelta(days=60), criado_por=self.tecnicos[0],
        )

    # ------------------------------------------------------------- voluntarios
    def _voluntarios(self):
        from voluntarios.models import Disponibilidade, Funcao, StatusVoluntario, Turno, Voluntario

        funcoes = [Funcao.objects.get_or_create(nome=nome)[0] for nome in FUNCOES]
        self.voluntarios = []
        for i, nome in enumerate(VOLUNTARIOS):
            voluntario = Voluntario.objects.create(
                nome=nome,
                nascimento=date(1965 + (i * 3) % 38, 1 + i % 12, 1 + (i * 7) % 28),
                telefone=f"3599{8100000 + i * 3571:07d}",
                email=f"{nome.split()[0].lower()}.exemplo@example.com",
                cidade="Itajubá", uf="MG",
                data_cadastro=self.hoje - timedelta(days=30 + i * 19),
                status=StatusVoluntario.INATIVO if i in (7, 15) else StatusVoluntario.ATIVO,
                criado_por=self.rng.choice(self.gestao),
            )
            voluntario.funcoes.set(self.rng.sample(funcoes, self.rng.randint(1, 2)))
            dias = self.rng.sample(range(7), self.rng.randint(2, 4))
            turnos = self.rng.sample([Turno.MANHA, Turno.TARDE, Turno.NOITE], self.rng.randint(1, 2))
            Disponibilidade.objects.bulk_create(
                [Disponibilidade(voluntario=voluntario, dia_semana=d, turno=t)
                 for d in dias for t in turnos]
            )
            if voluntario.status == StatusVoluntario.ATIVO:
                self.voluntarios.append(voluntario)
        self.stdout.write(f"{len(VOLUNTARIOS)} voluntários com disponibilidade.")

    # ---------------------------------------------------------------- doacoes
    def _doacoes(self):
        from doacoes.models import Campanha, Doacao, Doador, MetaItemCampanha, TipoDoacao, TipoPessoa
        from estoque.models import CategoriaItem, LoteEstoque, MovimentacaoEstoque
        from estoque.services import item_por_nome, sincronizar_doacao

        doadores = []
        for i, nome in enumerate(DOADORES_PJ + DOADORES_PF):
            pj = nome in DOADORES_PJ
            doadores.append(Doador.objects.create(
                tipo=TipoPessoa.PJ if pj else TipoPessoa.PF, nome=nome,
                telefone=f"3536{2200000 + i * 4231:07d}" if pj else f"3598{8800000 + i * 2791:07d}",
                email=f"contato{i}@example.com", cidade="Itajubá", uf="MG",
                recorrente=i % 3 == 0, criado_por=self.rng.choice(self.gestao),
            ))

        categorias = {c.nome: c for c in CategoriaItem.objects.all()}
        agasalho = Campanha.objects.create(
            nome="Campanha do Agasalho 2026", descricao="Roupas de frio e cobertores para o inverno.",
            data_inicio=self.hoje - timedelta(days=45), data_fim=self.hoje + timedelta(days=30),
            meta_valor=Decimal("3000.00"),
        )
        MetaItemCampanha.objects.create(campanha=agasalho, tipo=TipoDoacao.ITEM,
                                        categoria=categorias["Vestuário"], quantidade=150,
                                        unidade="unidades")
        criancas = Campanha.objects.create(
            nome="Dia das Crianças", descricao="Material escolar e brinquedos para outubro.",
            data_inicio=self.hoje - timedelta(days=12), data_fim=self.hoje + timedelta(days=20),
            meta_valor=Decimal("2000.00"),
        )
        MetaItemCampanha.objects.create(campanha=criancas, tipo=TipoDoacao.ITEM,
                                        categoria=categorias["Material escolar"], quantidade=120,
                                        unidade="unidades")
        MetaItemCampanha.objects.create(campanha=criancas, tipo=TipoDoacao.ITEM,
                                        categoria=categorias["Outros"], quantidade=40,
                                        unidade="unidades")
        natal = Campanha.objects.create(
            nome="Natal Solidário 2025", descricao="Ceia e presentes de fim de ano.",
            data_inicio=self.hoje - timedelta(days=300), data_fim=self.hoje - timedelta(days=270),
            meta_valor=Decimal("5000.00"),
        )

        def campanha_para(dia, categoria_nome=None):
            if agasalho.data_inicio <= dia and categoria_nome in (None, "Vestuário") and self.rng.random() < .6:
                return agasalho
            if criancas.data_inicio <= dia and categoria_nome in (None, "Material escolar", "Outros") \
                    and self.rng.random() < .7:
                return criancas
            if natal.data_inicio <= dia <= natal.data_fim and self.rng.random() < .8:
                return natal
            return None

        total = {"dinheiro": 0, "itens": 0, "servicos": 0}
        # Natal passado: um punhado de doacoes na epoca.
        dias = [natal.data_inicio + timedelta(days=self.rng.randint(0, 30)) for _ in range(12)]
        dias += [self.hoje - timedelta(days=self.rng.randint(0, 180)) for _ in range(130)]
        for dia in sorted(dias):
            doador = None if self.rng.random() < .12 else self.rng.choice(doadores)
            recebeu = self.rng.choice(self.gestao)
            sorteio = self.rng.random()
            if sorteio < .4:
                valor = Decimal(self.rng.choice([20, 30, 50, 50, 100, 100, 150, 200, 250, 500, 800, 1200]))
                doacao = Doacao.objects.create(
                    doador=doador, campanha=campanha_para(dia), tipo=TipoDoacao.DINHEIRO,
                    valor=valor, data_recebimento=dia, recebido_por=recebeu,
                    recibo_emitido=bool(doador) and self.rng.random() < .6,
                )
                total["dinheiro"] += 1
            elif sorteio < .95:
                cat_nome, nome, (qmin, qmax), validade = self.rng.choice(ITENS)
                quantidade = self.rng.randint(qmin, qmax)
                doacao = Doacao.objects.create(
                    doador=doador, campanha=campanha_para(dia, cat_nome), tipo=TipoDoacao.ITEM,
                    categoria=categorias[cat_nome], descricao=nome, quantidade=quantidade,
                    unidade="unidades", data_recebimento=dia, recebido_por=recebeu,
                )
                vence = dia + timedelta(days=self.rng.randint(*validade)) if validade else None
                lote = sincronizar_doacao(doacao, item_por_nome(categorias[cat_nome], nome), vence, recebeu)
                self._datar(LoteEstoque, lote.pk, dia)
                MovimentacaoEstoque.objects.filter(lote=lote).update(
                    criado_em=timezone.make_aware(datetime.combine(dia, time(10))))
                total["itens"] += 1
            else:
                doacao = Doacao.objects.create(
                    doador=doador or doadores[0], tipo=TipoDoacao.SERVICO,
                    descricao=self.rng.choice(SERVICOS), quantidade=self.rng.randint(1, 6),
                    unidade="horas", data_recebimento=dia, recebido_por=recebeu,
                )
                total["servicos"] += 1
            self._datar(Doacao, doacao.pk, dia)

        # Alimentos que vencem logo (e um ja vencido), para o alerta do painel.
        for nome, dias_para_vencer in [("Iogurte de morango", 2), ("Leite integral 1L", 5),
                                       ("Biscoito maisena", 0), ("Iogurte de morango", -2)]:
            dia = self.hoje - timedelta(days=self.rng.randint(8, 20))
            recebeu = self.rng.choice(self.gestao)
            doacao = Doacao.objects.create(
                doador=self.rng.choice(doadores), tipo=TipoDoacao.ITEM,
                categoria=categorias["Alimentos"], descricao=nome,
                quantidade=self.rng.randint(6, 18), unidade="unidades",
                data_recebimento=dia, recebido_por=recebeu,
            )
            lote = sincronizar_doacao(doacao, item_por_nome(categorias["Alimentos"], nome),
                                      self.hoje + timedelta(days=dias_para_vencer), recebeu)
            self._datar(Doacao, doacao.pk, dia)
            self._datar(LoteEstoque, lote.pk, dia)
            total["itens"] += 1
        # Campanha de Natal encerrada a mao.
        Campanha.objects.filter(pk=natal.pk).update(
            encerrada_em=timezone.make_aware(datetime.combine(natal.data_fim, time(18))))
        self.stdout.write(
            f"{len(doadores)} doadores, 3 campanhas e {sum(total.values())} doações "
            f"({total['dinheiro']} em dinheiro, {total['itens']} de itens, {total['servicos']} serviços)."
        )

    # ----------------------------------------------------------------- estoque
    def _estoque_manual_e_baixas(self):
        from estoque.models import CategoriaItem, ItemEstoque, LoteEstoque, MovimentacaoEstoque
        from estoque.services import dar_baixa, item_por_nome, registrar_entrada

        categorias = {c.nome: c for c in CategoriaItem.objects.all()}
        compras = 0
        for _ in range(18):
            cat_nome, nome, (qmin, qmax), validade = self.rng.choice(ITENS[:22])
            dia = self.hoje - timedelta(days=self.rng.randint(1, 120))
            vence = dia + timedelta(days=self.rng.randint(*validade)) if validade else None
            if vence and vence < self.hoje:
                vence = self.hoje + timedelta(days=self.rng.randint(15, 90))
            lote = registrar_entrada(item_por_nome(categorias[cat_nome], nome),
                                     self.rng.randint(qmin, qmax), self.rng.choice(self.abastece),
                                     validade=vence, observacao="Compra do mês")
            self._datar(LoteEstoque, lote.pk, dia)
            MovimentacaoEstoque.objects.filter(lote=lote).update(
                criado_em=timezone.make_aware(datetime.combine(dia, time(9))))
            compras += 1

        motivos = ["Almoço", "Jantar", "Café da manhã", "Kit de higiene", "Troca de roupa",
                   "Limpeza da casa", "Tarefa escolar", "Lanche da tarde", ""]
        baixas = 0
        itens = list(ItemEstoque.objects.all())
        for _ in range(70):
            item = self.rng.choice(itens)
            disponivel = sum(item.lotes.values_list("saldo", flat=True))
            if disponivel < 2:
                continue
            ultimo = MovimentacaoEstoque.objects.order_by("-pk").values_list("pk", flat=True).first() or 0
            dar_baixa(item, self.rng.randint(1, max(1, disponivel // 3)), self.rng.choice(self.usuarios),
                      self.rng.choice(motivos))
            quando = self.hoje - timedelta(days=self.rng.randint(0, 60))
            MovimentacaoEstoque.objects.filter(pk__gt=ultimo).update(
                criado_em=timezone.make_aware(datetime.combine(quando, time(self.rng.randint(7, 20)))))
            baixas += 1
        self.stdout.write(f"{ItemEstoque.objects.count()} itens no estoque, {compras} entradas "
                          f"manuais e {baixas} baixas.")

    # ----------------------------------------------------------------- escalas
    def _escalas(self):
        from django.core.exceptions import ValidationError

        from escalas.models import Alocacao, Atividade, Escala, StatusAlocacao, StatusEscala, Turno

        atividades = {a.nome: a for a in Atividade.objects.all()}
        domingo = self.hoje - timedelta(days=(self.hoje.weekday() + 1) % 7)
        agora = timezone.localtime().time()
        turnos_hoje, total_turnos, total_alocacoes = [], 0, 0

        def alocar(turno, **pessoa):
            alocacao = Alocacao(turno=turno, **pessoa)
            try:
                alocacao.full_clean()
            except ValidationError:
                return False
            if turno.data < self.hoje or (turno.data == self.hoje and turno.hora_fim <= agora):
                alocacao.status = (StatusAlocacao.FALTOU if self.rng.random() < .08
                                   else StatusAlocacao.CONFIRMADO)
            alocacao.save()
            return True

        for semana in (-1, 0, 1):
            inicio = domingo + timedelta(weeks=semana)
            escala = Escala.objects.create(
                titulo=f"Semana de {inicio:%d/%m/%Y}", data_inicio=inicio,
                data_fim=inicio + timedelta(days=6), criado_por=self.rng.choice(self.gestao),
                status=StatusEscala.RASCUNHO if semana == 1 else StatusEscala.PUBLICADA,
            )
            for d in range(7):
                dia = inicio + timedelta(days=d)
                for nome, hora_inicio, hora_fim, vagas, dias_semana, so_equipe in TURNOS:
                    if dia.weekday() not in dias_semana or nome not in atividades:
                        continue
                    turno = Turno.objects.create(
                        escala=escala, data=dia, hora_inicio=hora_inicio, hora_fim=hora_fim,
                        atividade=atividades[nome], vagas=vagas,
                        criado_por=self.rng.choice(self.gestao),
                        observacoes="Cardápio na porta da geladeira" if nome.startswith("Cozinha")
                        and d == 0 else "",
                    )
                    total_turnos += 1
                    if dia == self.hoje:
                        turnos_hoje.append(turno)
                    # Semana que vem fica mais vazia: ainda esta sendo montada.
                    preencher = vagas if semana < 1 else self.rng.randint(0, vagas)
                    if semana < 1 and self.rng.random() < .15:
                        preencher = max(0, vagas - 1)  # algumas vagas em aberto
                    candidatos = [{"usuario": u} for u in self.usuarios]
                    if not so_equipe:
                        disponiveis = [v for v in self.voluntarios
                                       if v.esta_disponivel(dia.weekday(), turno.turno_do_dia)]
                        candidatos = [{"voluntario": v} for v in disponiveis] * 2 + candidatos
                    self.rng.shuffle(candidatos)
                    for pessoa in candidatos:
                        if turno.alocacoes.count() >= preencher:
                            break
                        if alocar(turno, **pessoa):
                            total_alocacoes += 1

        # "Meu dia" no painel: cada usuario com pelo menos um turno hoje.
        for usuario in self.usuarios:
            if Alocacao.objects.filter(usuario=usuario, turno__data=self.hoje).exists():
                continue
            for turno in self.rng.sample(turnos_hoje, len(turnos_hoje)):
                if turno.alocacoes.count() >= turno.vagas:
                    turno.vagas += 1
                    turno.save(update_fields=["vagas"])
                if alocar(turno, usuario=usuario):
                    total_alocacoes += 1
                    break
        self.stdout.write(f"3 semanas de escala, {total_turnos} turnos e {total_alocacoes} alocações.")
