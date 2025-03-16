from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from authentication.models import User, Role

@login_required
def index(request):
    """Lab Assistant Dashboard view"""
    user = request.user
    # Check if user has lab_assistant role
    if user.get_role() != 'lab_assistant':
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_heading': 'Unauthorized Access',
            'error_message': 'You do not have permission to access the Lab Assistant Portal.',
            'return_url': '/'
        })
    
    return render(request, 'lab_assistant_portal/index.html')