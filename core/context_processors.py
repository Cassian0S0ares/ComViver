from django.urls import reverse


def menu(request):
    """Monta o menu conforme o perfil.

    Item sem permissao nao e renderizado, em vez de exibido e retornar 403.
    """
    if not request.user.is_authenticated:
        return {"menu_itens": []}

    itens = [
        {"rotulo": "Painel", "url": reverse("core:painel"), "icone": "house"},
    ]

    # Os itens de dominio entram nas fases 2 a 5, cada um com seu recorte de perfil.

    if request.user.pode_gerenciar_usuarios():
        itens.append(
            {"rotulo": "Usuários", "url": reverse("accounts:usuario_list"), "icone": "people"}
        )

    return {"menu_itens": itens}
