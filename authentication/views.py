from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.db import transaction
import uuid
from datetime import datetime
from django.http import HttpResponse, JsonResponse

from .forms import UserLoginForm, UserForgotPasswordForm, UserPasswordResetForm
from .models import User, PasswordResetToken, Role

def user_login(request):
    """Handle user login with remember me functionality"""
    if request.user.is_authenticated:
        return redirect('redirect_to_portal')
    
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            remember_me = form.cleaned_data.get('remember_me')
            
            user = authenticate(request, username=email, password=password)
            
            if user is not None:
                login(request, user)
                
                # Set session expiry based on remember me option
                if not remember_me:
                    request.session.set_expiry(0)  # Session expires when browser closes
                # For remember me, use the SESSION_COOKIE_AGE from settings (2 weeks)
                
                messages.success(request, f'Welcome back, {user.full_name}!')
                return redirect('redirect_to_portal')
            else:
                messages.error(request, 'Invalid email or password.')
        else:
            messages.error(request, 'Invalid form submission. Please check your inputs.')
    else:
        form = UserLoginForm()
        
    return render(request, 'authentication/login.html', {'form': form})

@login_required
def user_logout(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('login')

@login_required
def redirect_to_portal(request):
    """Redirect user to appropriate portal based on role"""
    user = request.user
    role_name = user.get_role()
    
    if role_name == 'admin':
        return redirect('admin_portal:index')
    elif role_name == 'hod':
        return redirect('hod_portal:index')
    elif role_name == 'faculty':
        return redirect('faculty_portal:index')
    elif role_name == 'lab_assistant':
        return redirect('lab_assistant_portal:index')
    elif role_name == 'student':
        return redirect('student_portal:index')
    else:
        messages.error(request, f'No portal defined for role: {role_name}')
        return redirect('login')

def forgot_password(request):
    """Handle forgot password requests"""
    if request.user.is_authenticated:
        return redirect('redirect_to_portal')
    
    if request.method == 'POST':
        form = UserForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            
            try:
                user = User.objects.get(email=email)
                
                # Create password reset token
                token = PasswordResetToken.objects.create(user=user)
                
                # Build email
                current_site = get_current_site(request)
                mail_subject = 'Password Reset Request - MBIT Attendance System'
                message = render_to_string('authentication/reset_password_email.html', {
                    'user': user,
                    'domain': current_site.domain,
                    'token': token.token,
                })
                
                # Send email
                email_message = EmailMessage(mail_subject, message, 'abhijeetsahoo510@gmail.com', [email])
                email_message.send()
                
                messages.success(request, 'Password reset link has been sent to your email address.')
                return redirect('login')
                
            except User.DoesNotExist:
                messages.error(request, 'No account found with this email address.')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = UserForgotPasswordForm()
        
    return render(request, 'authentication/forgot_password.html', {'form': form})

def reset_password(request, token):
    """Handle password reset with token validation"""
    if request.user.is_authenticated:
        return redirect('redirect_to_portal')
    
    try:
        # Find and validate token
        reset_token = PasswordResetToken.objects.get(token=token)
        
        if not reset_token.is_valid():
            messages.error(request, 'Password reset link has expired. Please request a new one.')
            return redirect('forgot_password')
        
        user = reset_token.user
        
        if request.method == 'POST':
            form = UserPasswordResetForm(user, request.POST)
            if form.is_valid():
                with transaction.atomic():
                    # Save new password
                    form.save()
                    # Delete the used token
                    reset_token.delete()
                    
                messages.success(request, 'Your password has been successfully reset. You can now login with your new password.')
                return redirect('login')
            else:
                for error in form.errors.values():
                    messages.error(request, error)
        else:
            form = UserPasswordResetForm(user)
            
        return render(request, 'authentication/reset_password.html', {'form': form})
        
    except PasswordResetToken.DoesNotExist:
        messages.error(request, 'Invalid password reset link. Please request a new one.')
        return redirect('forgot_password')

# Function to check password token validity via AJAX
def check_token_validity(request, token):
    """Check if a password reset token is valid (for AJAX calls)"""
    try:
        reset_token = PasswordResetToken.objects.get(token=token)
        is_valid = reset_token.is_valid()
        return JsonResponse({'valid': is_valid})
    except PasswordResetToken.DoesNotExist:
        return JsonResponse({'valid': False})