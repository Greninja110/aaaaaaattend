from django.urls import path
from . import views

app_name = 'lab_assistant_portal'

urlpatterns = [
    path('', views.index, name='index'),
]