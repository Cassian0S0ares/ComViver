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

    # Todos os perfis veem a lista; o recorte de sigilo acontece dentro da ficha.
    itens.append({"rotulo": "Acolhidos", "url": reverse("acolhidos:lista"), "icone": "emoji-smile"})

    # Lista de plantao: toda a equipe administra remedio.
    itens.append(
        {"rotulo": "Medicações", "url": reverse("acolhidos:medicacoes"), "icone": "capsule"}
    )

    itens.extend(
        [
            {"rotulo": "Doações", "url": reverse("doacoes:lista"), "icone": "box2-heart"},
            {"rotulo": "Doadores", "url": reverse("doacoes:doador_lista"), "icone": "people"},
            {"rotulo": "Campanhas", "url": reverse("doacoes:campanha_lista"), "icone": "flag"},
        ]
    )

    itens.append(
        {"rotulo": "Voluntários", "url": reverse("voluntarios:lista"), "icone": "person-badge"}
    )

    itens.append(
        {"rotulo": "Escalas", "url": reverse("escalas:lista"), "icone": "calendar-week"}
    )

    if request.user.pode_gerenciar_usuarios():
        itens.append(
            {"rotulo": "Usuários", "url": reverse("accounts:usuario_list"), "icone": "people"}
        )

    # Marca o item da secao atual, inclusive nas subpaginas (/acolhidos/12/).
    for item in itens:
        url = item["url"]
        item["atual"] = request.path == url or (url != "/" and request.path.startswith(url))

    return {"menu_itens": itens}
