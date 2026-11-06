import random
import time

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render

from .forms import EmailCodeForm, EmailRegisterForm
from .models import Profile

SESSION_KEY = 'pending_registration'
CODE_TTL_SECONDS = 600


def _generate_code():
    return f'{random.randint(0, 999999):06d}'


def _send_code_email(email, code):
    send_mail(
        subject='Your registration confirmation code',
        message=f'Your confirmation code: {code}\nIt is valid for 10 minutes.',
        from_email=None,
        recipient_list=[email],
    )


def register(request):
    if request.method == 'POST':
        form = EmailRegisterForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            code = _generate_code()
            request.session[SESSION_KEY] = {
                'nickname': form.cleaned_data['nickname'],
                'email': email,
                'password': make_password(form.cleaned_data['password1']),
                'code': code,
                'created': time.time(),
            }
            _send_code_email(email, code)
            return redirect('verify_email')
    else:
        form = EmailRegisterForm()
    return render(request, 'registration/register.html', {'form': form})


def verify_email(request):
    pending = request.session.get(SESSION_KEY)
    if not pending:
        messages.error(request, 'Please enter your email to register first.')
        return redirect('register')

    if time.time() - pending['created'] > CODE_TTL_SECONDS:
        del request.session[SESSION_KEY]
        messages.error(request, 'The code has expired, please register again.')
        return redirect('register')

    form = EmailCodeForm(request.POST or None)

    if request.method == 'POST':
        if 'resend' in request.POST:
            pending['code'] = _generate_code()
            pending['created'] = time.time()
            request.session[SESSION_KEY] = pending
            _send_code_email(pending['email'], pending['code'])
            messages.info(request, 'A new code has been sent to your email.')
            return redirect('verify_email')

        if form.is_valid():
            if form.cleaned_data['code'] != pending['code']:
                form.add_error('code', 'Incorrect code.')
            elif Profile.objects.filter(nickname__iexact=pending['nickname']).exists():
                # Someone else claimed the nickname while this code was
                # pending (checked again here since it was only validated
                # once, back on the register step).
                del request.session[SESSION_KEY]
                messages.error(request, 'That nickname was just taken, please register again.')
                return redirect('register')
            else:
                try:
                    with transaction.atomic():
                        user = User(username=pending['email'], email=pending['email'])
                        user.password = pending['password']
                        user.save()
                        Profile.objects.create(user=user, nickname=pending['nickname'])
                except IntegrityError:
                    messages.error(request, 'That nickname was just taken, please register again.')
                    del request.session[SESSION_KEY]
                    return redirect('register')
                del request.session[SESSION_KEY]
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect('home')

    return render(request, 'registration/verify_email.html', {'form': form, 'email': pending['email']})
