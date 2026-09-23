from django.contrib import admin

from voluntarios.models import Disponibilidade, DocumentoVoluntario, Funcao, Voluntario


@admin.register(Funcao)
class FuncaoAdmin(admin.ModelAdmin):
    list_display = ["nome"]
    search_fields = ["nome"]


class DisponibilidadeInline(admin.TabularInline):
    model = Disponibilidade
    extra = 0


@admin.register(Voluntario)
class VoluntarioAdmin(admin.ModelAdmin):
    list_display = ["nome", "status", "criado_em"]
    list_filter = ["status"]
    search_fields = ["nome", "cpf", "email"]
    inlines = [DisponibilidadeInline]


admin.site.register(DocumentoVoluntario)
