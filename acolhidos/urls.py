from django.urls import path

from acolhidos import views

app_name = "acolhidos"

urlpatterns = [
    path("acolhidos/", views.AcolhidoListView.as_view(), name="lista"),
    path("acolhidos/<int:pk>/", views.AcolhidoDetailView.as_view(), name="detalhe"),
]
