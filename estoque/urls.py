from django.urls import path

from estoque import views

app_name = "estoque"

urlpatterns = [
    path("estoque/", views.EstoqueListView.as_view(), name="lista"),
    path("estoque/entrada/", views.EntradaView.as_view(), name="entrada"),
    path("estoque/categorias/nova/", views.CategoriaCreateView.as_view(), name="categoria_nova"),
    path("estoque/itens/<int:pk>/", views.ItemDetailView.as_view(), name="item"),
    path("estoque/itens/<int:pk>/baixa/", views.BaixaView.as_view(), name="baixa"),
]
