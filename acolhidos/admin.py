from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from acolhidos.models import (
    Acolhido,
    Consentimento,
    DadosSaude,
    DocumentoAcolhido,
    Escolaridade,
    FichaAcolhimento,
    Medicacao,
    Responsavel,
    VinculoFamiliar,
)


class VinculoInline(admin.TabularInline):
    model = VinculoFamiliar
    extra = 0


@admin.register(Acolhido)
class AcolhidoAdmin(SimpleHistoryAdmin):
    list_display = ["nome_exibicao", "idade", "status", "criado_em"]
    list_filter = ["status", "sexo"]
    search_fields = ["nome", "nome_social"]
    inlines = [VinculoInline]


@admin.register(FichaAcolhimento, DadosSaude)
class HistoricoAdmin(SimpleHistoryAdmin):
    pass


admin.site.register([Responsavel, Medicacao, Escolaridade, DocumentoAcolhido, Consentimento])
