from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q
from django import forms

from .models import Friendship, Profile, nickname_validator


class EmailRegisterForm(forms.Form):
    nickname = forms.CharField(
        label='Nickname', min_length=3, max_length=30, validators=[nickname_validator],
        help_text='3-30 characters: letters, digits, "_" or "-". Visible to friends and used to log in.',
    )
    email = forms.EmailField(label='Email')
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput)

    def clean_nickname(self):
        nickname = self.cleaned_data['nickname'].strip()
        if Profile.objects.filter(nickname__iexact=nickname).exists():
            raise forms.ValidationError('This nickname is already taken.')
        return nickname

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('A user with this email is already registered.')
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Passwords do not match.')
        if password1:
            try:
                validate_password(password1)
            except ValidationError as exc:
                self.add_error('password1', exc)
        return cleaned


class EmailCodeForm(forms.Form):
    code = forms.CharField(label='Code from the email', min_length=6, max_length=6)


class AddFriendForm(forms.Form):
    """Send a friend request by nickname or email. Requires the logged-in
    user so it can reject requests to self and duplicate requests."""

    identifier = forms.CharField(label="Friend's nickname or email")

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_identifier(self):
        identifier = self.cleaned_data['identifier'].strip()
        target = User.objects.filter(
            Q(email__iexact=identifier) | Q(profile__nickname__iexact=identifier),
        ).first()
        if target is None:
            raise forms.ValidationError('No user found with that nickname or email.')

        if target == self.user:
            raise forms.ValidationError("You can't add yourself as a friend.")

        existing = Friendship.objects.filter(
            Q(from_user=self.user, to_user=target) | Q(from_user=target, to_user=self.user),
        ).exclude(status=Friendship.STATUS_DECLINED).first()
        if existing is not None and existing.status == Friendship.STATUS_ACCEPTED:
            raise forms.ValidationError('You are already friends.')
        if existing is not None and existing.status == Friendship.STATUS_PENDING:
            raise forms.ValidationError('A request has already been sent and is awaiting a response.')

        self.target_user = target
        return identifier
