from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from .models import User

class UserLoginForm(AuthenticationForm):
    username = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Email Address',
                'autocomplete': 'email',
                'id': 'email'
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Password',
                'id': 'password'
            }
        )
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={
                'class': 'form-check-input',
                'id': 'remember-me'
            }
        )
    )
    
    class Meta:
        model = User
        fields = ['username', 'password', 'remember_me']

class UserForgotPasswordForm(PasswordResetForm):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Email Address',
                'id': 'email'
            }
        )
    )
    
    class Meta:
        fields = ['email']
        
    def clean_email(self):
        email = self.cleaned_data['email']
        # Check if email ends with mbit.edu.in
        if not email.endswith('@mbit.edu.in'):
            raise forms.ValidationError('Please enter a valid MBIT email address')
        # Check if the email exists in the database
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError('No account found with this email address')
        return email

class UserPasswordResetForm(SetPasswordForm):
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'New Password',
                'id': 'new-password'
            }
        ),
        label='New Password'
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Confirm New Password',
                'id': 'confirm-password'
            }
        ),
        label='Confirm New Password'
    )
    
    class Meta:
        model = User
        fields = ['new_password1', 'new_password2']