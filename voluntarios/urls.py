from django.urls import path

from voluntarios import views

app_name = "voluntarios"

urlpatterns = [
    path("voluntarios/", views.VoluntarioListView.as_view(), name="lista"),
    path("voluntarios/novo/", views.VoluntarioCreateView.as_view(), name="novo"),
    path("voluntarios/<int:pk>/", views.VoluntarioDetailView.as_view(), name="detalhe"),
    path("voluntarios/<int:pk>/editar/", views.VoluntarioUpdateView.as_view(), name="editar"),
    path("funcoes/", views.FuncaoListView.as_view(), name="funcao_lista"),
    path("funcoes/nova/", views.FuncaoCreateView.as_view(), name="funcao_nova"),
]
