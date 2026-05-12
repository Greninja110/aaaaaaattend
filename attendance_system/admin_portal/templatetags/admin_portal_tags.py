from django import template
from django.utils import timezone
import datetime

register = template.Library()

@register.filter
def format_datetime(dt):
    """Format datetime for display"""
    if not dt:
        return "N/A"
    
    now = timezone.now()
    diff = now - dt
    
    if diff.days == 0:
        # Today
        if diff.seconds < 60:
            return "Just now"
        elif diff.seconds < 3600:
            return f"{diff.seconds // 60} minute{'s' if diff.seconds // 60 != 1 else ''} ago"
        else:
            return f"{diff.seconds // 3600} hour{'s' if diff.seconds // 3600 != 1 else ''} ago"
    elif diff.days == 1:
        return "Yesterday"
    elif diff.days < 7:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    else:
        return dt.strftime("%b %d, %Y %H:%M")

@register.filter
def user_role_badge(role_name):
    """Return a Bootstrap badge for user role"""
    badge_classes = {
        'admin': 'bg-danger',
        'hod': 'bg-warning',
        'faculty': 'bg-primary',
        'lab_assistant': 'bg-info',
        'student': 'bg-success'
    }
    
    badge_class = badge_classes.get(role_name.lower(), 'bg-secondary')
    return f'<span class="badge {badge_class}">{role_name.title()}</span>'

@register.simple_tag
def get_attendance_status_class(percentage):
    """Return appropriate class for attendance percentage"""
    if percentage >= 85:
        return 'text-success'
    elif percentage >= 75:
        return 'text-info'
    elif percentage >= 65:
        return 'text-warning'
    else:
        return 'text-danger'