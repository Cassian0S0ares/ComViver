from django.shortcuts import redirect
from django.urls import reverse


class TrocaSenhaObrigatoriaMiddleware:
    """Desvia para a troca de senha quem ainda usa a senha provisoria.

    Senha provisoria e definida pela coordenacao ao criar o usuario, entao
    circula por bilhete ou mensagem. Precisa ser trocada no primeiro acesso.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.precisa_trocar_senha:
            liberadas = {
                reverse("accounts:trocar_senha"),
                reverse("accounts:logout"),
            }
            if request.path not in liberadas and not request.path.startswith("/static/"):
                return redirect("accounts:trocar_senha")
        return self.get_response(request)
