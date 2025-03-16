from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('authentication.urls')),
    path('admin-portal/', include('admin_portal.urls')),
    path('hod-portal/', include('hod_portal.urls')),
    path('faculty-portal/', include('faculty_portal.urls')),
    path('lab-assistant-portal/', include('lab_assistant_portal.urls')),
    path('student-portal/', include('student_portal.urls')),
]