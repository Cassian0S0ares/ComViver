from datetime import date, timedelta

import pytest

from acolhidos.factories import AcolhidoFactory, ResponsavelFactory, VinculoFamiliarFactory
from acolhidos.models import Acolhido, StatusAcolhido, VinculoFamiliar

pytestmark = pytest.mark.django_db


class TestAcolhido:
    def test_idade_calculada_do_nascimento(self):
        acolhido = AcolhidoFactory(nascimento=date.today() - timedelta(days=365 * 10 + 3))
        assert acolhido.idade == 10

    def test_idade_antes_do_aniversario_no_ano(self):
        hoje = date.today()
        nascimento = date(hoje.year - 8, 12, 31) if hoje.month < 12 else date(hoje.year - 8, 1, 1)
        acolhido = AcolhidoFactory(nascimento=nascimento)
        esperado = 7 if hoje.month < 12 else 8
        assert acolhido.idade == esperado

    def test_nome_exibicao_prefere_nome_social(self):
        acolhido = AcolhidoFactory(nome="João da Silva", nome_social="Joana")
        assert acolhido.nome_exibicao == "Joana"

    def test_nome_exibicao_cai_no_nome_quando_sem_social(self):
        acolhido = AcolhidoFactory(nome="João da Silva", nome_social="")
        assert acolhido.nome_exibicao == "João da Silva"

    def test_status_inicial_e_acolhido(self):
        assert AcolhidoFactory().status == StatusAcolhido.ACOLHIDO

    def test_exclusao_e_logica(self):
        acolhido = AcolhidoFactory()
        pk = acolhido.pk
        acolhido.delete()
        assert not Acolhido.objects.filter(pk=pk).exists()
        assert Acolhido.todos.filter(pk=pk).exists()

    def test_cpf_e_unico_quando_preenchido(self):
        from django.db import IntegrityError

        AcolhidoFactory(cpf="12345678901")
        with pytest.raises(IntegrityError):
            AcolhidoFactory(cpf="12345678901")

    def test_varios_acolhidos_podem_estar_sem_cpf(self):
        """Crianca acolhida frequentemente chega sem documento."""
        AcolhidoFactory(cpf="")
        AcolhidoFactory(cpf="")
        assert Acolhido.objects.filter(cpf__isnull=True).count() == 2


class TestVinculoFamiliar:
    def test_um_responsavel_vinculado_a_dois_irmaos(self):
        mae = ResponsavelFactory(nome="Maria")
        irmao_um = AcolhidoFactory()
        irmao_dois = AcolhidoFactory()
        VinculoFamiliarFactory(acolhido=irmao_um, responsavel=mae, parentesco="Mãe")
        VinculoFamiliarFactory(acolhido=irmao_dois, responsavel=mae, parentesco="Mãe")
        assert mae.vinculos.count() == 2

    def test_um_acolhido_com_varios_responsaveis(self):
        acolhido = AcolhidoFactory()
        VinculoFamiliarFactory(acolhido=acolhido, parentesco="Mãe")
        VinculoFamiliarFactory(acolhido=acolhido, parentesco="Avó", e_guardiao=True)
        assert acolhido.vinculos.count() == 2

    def test_nao_duplica_o_mesmo_vinculo(self):
        from django.db import IntegrityError

        acolhido = AcolhidoFactory()
        responsavel = ResponsavelFactory()
        VinculoFamiliarFactory(acolhido=acolhido, responsavel=responsavel)
        with pytest.raises(IntegrityError):
            VinculoFamiliarFactory(acolhido=acolhido, responsavel=responsavel)

    def test_autorizados_a_retirar_filtra_corretamente(self):
        acolhido = AcolhidoFactory()
        avo = ResponsavelFactory(nome="Ana")
        VinculoFamiliarFactory(
            acolhido=acolhido, responsavel=avo, parentesco="Avó", autorizado_retirar=True
        )
        VinculoFamiliarFactory(acolhido=acolhido, parentesco="Tio", autorizado_retirar=False)
        autorizados = VinculoFamiliar.objects.filter(acolhido=acolhido, autorizado_retirar=True)
        assert [v.responsavel.nome for v in autorizados] == ["Ana"]
