from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('authentication.urls')),
    path('admin-portal/', include('admin_portal.urls')),
    path('hod-portal/', include('hod_portal.urls')),
    path('faculty-portal/', include('faculty_portal.urls')),
    path('lab-assistant-portal/', include('lab_assistant_portal.urls')),
    path('student-portal/', include('student_portal.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    