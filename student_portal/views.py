from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from authentication.models import User, Role

@login_required
def index(request):
    """Student Dashboard view"""
    user = request.user
    # Check if user has student role
    if user.get_role() != 'student':
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_heading': 'Unauthorized Access',
            'error_message': 'You do not have permission to access the Student Portal.',
            'return_url': '/'
        })
    
    return render(request, 'student_portal/index.html')