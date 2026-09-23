from django.urls import path

from escalas import views

app_name = "escalas"

urlpatterns = [
    path("escalas/", views.EscalaListView.as_view(), name="lista"),
    path("escalas/nova/", views.EscalaCreateView.as_view(), name="nova"),
    path("escalas/<int:pk>/", views.EscalaGradeView.as_view(), name="grade"),
    path("escalas/<int:pk>/turno/", views.TurnoCreateView.as_view(), name="turno_novo"),
    path("escalas/<int:pk>/publicar/", views.PublicarView.as_view(), name="publicar"),
    path("turnos/<int:pk>/disponiveis/", views.DisponiveisView.as_view(), name="disponiveis"),
    path("turnos/<int:pk>/alocar/", views.AlocarView.as_view(), name="alocar"),
    path("alocacoes/<int:pk>/remover/", views.DesalocarView.as_view(), name="desalocar"),
]
