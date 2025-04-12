from django.urls import path
from . import views

app_name = 'faculty_portal'

urlpatterns = [
    path('', views.index, name='index'),
]