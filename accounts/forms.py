from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q
from django import forms

from .models import Friendship, Profile, nickname_validator


class EmailRegisterForm(forms.Form):
    nickname = forms.CharField(
        label='Никнейм', min_length=3, max_length=30, validators=[nickname_validator],
        help_text='3-30 символов: буквы, цифры, "_" или "-". Виден друзьям и используется для входа.',
    )
    email = forms.EmailField(label='Email')
    password1 = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Подтверждение пароля', widget=forms.PasswordInput)

    def clean_nickname(self):
        nickname = self.cleaned_data['nickname'].strip()
        if Profile.objects.filter(nickname__iexact=nickname).exists():
            raise forms.ValidationError('Этот никнейм уже занят.')
        return nickname

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Пользователь с таким email уже зарегистрирован.')
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Пароли не совпадают.')
        if password1:
            try:
                validate_password(password1)
            except ValidationError as exc:
                self.add_error('password1', exc)
        return cleaned


class EmailCodeForm(forms.Form):
    code = forms.CharField(label='Код из письма', min_length=6, max_length=6)


class AddFriendForm(forms.Form):
    """Send a friend request by nickname or email. Requires the logged-in
    user so it can reject requests to self and duplicate requests."""

    identifier = forms.CharField(label='Никнейм или email друга')

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_identifier(self):
        identifier = self.cleaned_data['identifier'].strip()
        target = User.objects.filter(
            Q(email__iexact=identifier) | Q(profile__nickname__iexact=identifier),
        ).first()
        if target is None:
            raise forms.ValidationError('Пользователь с таким ником или email не найден.')

        if target == self.user:
            raise forms.ValidationError('Нельзя добавить самого себя в друзья.')

        existing = Friendship.objects.filter(
            Q(from_user=self.user, to_user=target) | Q(from_user=target, to_user=self.user),
        ).exclude(status=Friendship.STATUS_DECLINED).first()
        if existing is not None and existing.status == Friendship.STATUS_ACCEPTED:
            raise forms.ValidationError('Вы уже друзья.')
        if existing is not None and existing.status == Friendship.STATUS_PENDING:
            raise forms.ValidationError('Заявка уже отправлена и ожидает ответа.')

        self.target_user = target
        return identifier
