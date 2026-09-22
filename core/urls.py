from django.urls import path

from core import views

app_name = "core"

urlpatterns = [path("", views.PainelView.as_view(), name="painel")]
