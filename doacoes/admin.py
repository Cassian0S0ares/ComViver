from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from doacoes.models import Campanha, Doacao, Doador


class SemExclusaoAdmin:
    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            obj.criado_por = request.user
            if isinstance(obj, Doacao):
                obj.recebido_por = request.user
        super().save_model(request, obj, form, change)

    readonly_fields = ("criado_por", "criado_em", "atualizado_em")


@admin.register(Doacao)
class DoacaoAdmin(SemExclusaoAdmin, SimpleHistoryAdmin):
    readonly_fields = SemExclusaoAdmin.readonly_fields + ("recebido_por",)
    list_display = ["data_recebimento", "tipo", "descricao", "doador", "valor"]
    list_filter = ["tipo", "recibo_emitido", "campanha"]
    search_fields = ["descricao", "doador__nome"]
    date_hierarchy = "data_recebimento"


@admin.register(Doador)
class DoadorAdmin(SemExclusaoAdmin, admin.ModelAdmin):
    list_display = ["nome", "tipo", "documento_formatado", "recorrente"]
    list_filter = ["tipo", "recorrente"]
    search_fields = ["nome", "cpf_cnpj"]


@admin.register(Campanha)
class CampanhaAdmin(SemExclusaoAdmin, admin.ModelAdmin):
    list_display = ["nome", "data_inicio", "data_fim", "meta_valor"]
