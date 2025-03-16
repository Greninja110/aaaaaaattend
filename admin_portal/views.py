from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from authentication.models import User, Role

@login_required
def index(request):
    """Admin Dashboard view"""
    user = request.user
    # Check if user has admin role
    if user.get_role() != 'admin':
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_heading': 'Unauthorized Access',
            'error_message': 'You do not have permission to access the Admin Portal.',
            'return_url': '/'
        })
    
    return render(request, 'admin_portal/index.html')