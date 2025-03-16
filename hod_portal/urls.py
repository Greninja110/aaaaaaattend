from django.urls import path
from . import views

app_name = 'hod_portal'

urlpatterns = [
    path('', views.index, name='index'),
]