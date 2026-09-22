from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("entrar/", views.EntrarView.as_view(), name="login"),
    path("sair/", views.SairView.as_view(), name="logout"),
    path("esqueci-senha/", views.EsqueciSenhaView.as_view(), name="esqueci_senha"),
    path(
        "esqueci-senha/enviado/",
        views.EsqueciSenhaEnviadoView.as_view(),
        name="esqueci_senha_enviado",
    ),
    path(
        "redefinir-senha/<uidb64>/<token>/",
        views.RedefinirSenhaView.as_view(),
        name="redefinir_senha",
    ),
    path(
        "redefinir-senha/concluido/",
        views.RedefinirSenhaConcluidoView.as_view(),
        name="redefinir_senha_concluido",
    ),
    path("trocar-senha/", views.TrocarSenhaView.as_view(), name="trocar_senha"),
    path("usuarios/", views.UsuarioListView.as_view(), name="usuario_list"),
    path("usuarios/novo/", views.UsuarioCreateView.as_view(), name="usuario_novo"),
    path("usuarios/<int:pk>/editar/", views.UsuarioUpdateView.as_view(), name="usuario_editar"),
    path(
        "usuarios/<int:pk>/desativar/",
        views.UsuarioDesativarView.as_view(),
        name="usuario_desativar",
    ),
]
