from django.urls import path

from acolhidos import views

app_name = "acolhidos"

urlpatterns = [
    path("acolhidos/", views.AcolhidoListView.as_view(), name="lista"),
    path("acolhidos/novo/", views.AcolhimentoWizard.as_view(), name="novo"),
    path("acolhidos/<int:pk>/", views.AcolhidoDetailView.as_view(), name="detalhe"),
    path("acolhidos/<int:pk>/editar/", views.AcolhidoUpdateView.as_view(), name="editar"),
    path("acolhidos/<int:pk>/ficha/", views.FichaUpdateView.as_view(), name="editar_ficha"),
    path("acolhidos/<int:pk>/desligar/", views.DesligamentoView.as_view(), name="desligar"),
    path("acolhidos/<int:pk>/vinculo/", views.VinculoCreateView.as_view(), name="vinculo_novo"),
    path(
        "acolhidos/<int:pk>/medicacao/",
        views.MedicacaoCreateView.as_view(),
        name="medicacao_nova",
    ),
    path(
        "acolhidos/medicacoes/<int:pk>/editar/",
        views.MedicacaoUpdateView.as_view(),
        name="medicacao_editar",
    ),
    path(
        "acolhidos/medicacoes/<int:pk>/remover/",
        views.MedicacaoRemoverView.as_view(),
        name="medicacao_remover",
    ),
    path(
        "acolhidos/vinculos/<int:pk>/editar/",
        views.VinculoUpdateView.as_view(),
        name="vinculo_editar",
    ),
]
