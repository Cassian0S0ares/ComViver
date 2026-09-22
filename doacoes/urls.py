from django.urls import path

from doacoes import views

app_name = "doacoes"

urlpatterns = [
    path("doacoes/", views.DoacaoListView.as_view(), name="lista"),
    path("doacoes/nova/", views.DoacaoCreateView.as_view(), name="nova"),
    path("doacoes/<int:pk>/editar/", views.DoacaoUpdateView.as_view(), name="editar"),
    path("doacoes/<int:pk>/recibo/", views.ReciboView.as_view(), name="recibo"),
    path("doacoes/buscar-doador/", views.BuscarDoadorView.as_view(), name="buscar_doador"),

    path("doadores/", views.DoadorListView.as_view(), name="doador_lista"),
    path("doadores/novo/", views.DoadorCreateView.as_view(), name="doador_novo"),
    path("doadores/<int:pk>/", views.DoadorDetailView.as_view(), name="doador_detalhe"),
    path("doadores/<int:pk>/editar/", views.DoadorUpdateView.as_view(), name="doador_editar"),

    path("campanhas/", views.CampanhaListView.as_view(), name="campanha_lista"),
    path("campanhas/nova/", views.CampanhaCreateView.as_view(), name="campanha_nova"),
    path("campanhas/<int:pk>/editar/", views.CampanhaUpdateView.as_view(), name="campanha_editar"),
]
