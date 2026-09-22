from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from doacoes.models import Campanha, Doacao, Doador


@admin.register(Doacao)
class DoacaoAdmin(SimpleHistoryAdmin):
    list_display = ["data_recebimento", "tipo", "descricao", "doador", "valor"]
    list_filter = ["tipo", "recibo_emitido", "campanha"]
    search_fields = ["descricao", "doador__nome"]
    date_hierarchy = "data_recebimento"


@admin.register(Doador)
class DoadorAdmin(admin.ModelAdmin):
    list_display = ["nome", "tipo", "documento_formatado", "recorrente"]
    list_filter = ["tipo", "recorrente"]
    search_fields = ["nome", "cpf_cnpj"]


admin.site.register(Campanha)
