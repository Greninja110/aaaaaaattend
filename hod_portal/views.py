from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from authentication.models import User, Role

@login_required
def index(request):
    """HOD Dashboard view"""
    user = request.user
    # Check if user has HOD role
    if user.get_role() != 'hod':
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_heading': 'Unauthorized Access',
            'error_message': 'You do not have permission to access the HOD Portal.',
            'return_url': '/'
        })
    
    return render(request, 'hod_portal/index.html')