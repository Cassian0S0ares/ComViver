from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import Usuario


def acesso_manutencao(request):
    return request.user.is_active and request.user.is_superuser


admin.site.has_permission = acesso_manutencao
admin.site.site_header = "ComViver · Manutenção"


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ["username", "first_name", "last_name", "perfil", "is_active"]
    list_filter = ["perfil", "is_active"]
    fieldsets = UserAdmin.fieldsets + (
        ("ComViver", {"fields": ("perfil", "telefone", "precisa_trocar_senha")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (("ComViver", {"fields": ("perfil", "telefone")}),)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.sincronizar_grupo()
