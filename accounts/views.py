import random
import time

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from cards.progress import get_user_progress

from .forms import AddFriendForm, EmailCodeForm, EmailRegisterForm
from .models import Friendship, Profile, get_display_name

SESSION_KEY = 'pending_registration'
CODE_TTL_SECONDS = 600


def _generate_code():
    return f'{random.randint(0, 999999):06d}'


def _send_code_email(email, code):
    send_mail(
        subject='Код подтверждения регистрации',
        message=f'Ваш код подтверждения: {code}\nОн действует 10 минут.',
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
        messages.error(request, 'Сначала укажите email для регистрации.')
        return redirect('register')

    if time.time() - pending['created'] > CODE_TTL_SECONDS:
        del request.session[SESSION_KEY]
        messages.error(request, 'Код истёк, зарегистрируйтесь заново.')
        return redirect('register')

    form = EmailCodeForm(request.POST or None)

    if request.method == 'POST':
        if 'resend' in request.POST:
            pending['code'] = _generate_code()
            pending['created'] = time.time()
            request.session[SESSION_KEY] = pending
            _send_code_email(pending['email'], pending['code'])
            messages.info(request, 'Новый код отправлен на почту.')
            return redirect('verify_email')

        if form.is_valid():
            if form.cleaned_data['code'] != pending['code']:
                form.add_error('code', 'Неверный код.')
            elif Profile.objects.filter(nickname__iexact=pending['nickname']).exists():
                # Someone else claimed the nickname while this code was
                # pending (checked again here since it was only validated
                # once, back on the register step).
                del request.session[SESSION_KEY]
                messages.error(request, 'Этот никнейм уже заняли, зарегистрируйтесь заново.')
                return redirect('register')
            else:
                try:
                    with transaction.atomic():
                        user = User(username=pending['email'], email=pending['email'])
                        user.password = pending['password']
                        user.save()
                        Profile.objects.create(user=user, nickname=pending['nickname'])
                except IntegrityError:
                    messages.error(request, 'Этот никнейм уже заняли, зарегистрируйтесь заново.')
                    del request.session[SESSION_KEY]
                    return redirect('register')
                del request.session[SESSION_KEY]
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect('home')

    return render(request, 'registration/verify_email.html', {'form': form, 'email': pending['email']})


@login_required
def friends(request):
    """Friends hub: send a friend request, answer pending ones, and see the
    current friend list together with each friend's learning progress."""
    if request.method == 'POST':
        form = AddFriendForm(request.POST, user=request.user)
        if form.is_valid():
            target = form.target_user

            # Reuse an existing (declined) row between these two users
            # instead of creating a second one, which the
            # unique_friendship_pair constraint would reject.
            existing = Friendship.objects.filter(
                Q(from_user=request.user, to_user=target) | Q(from_user=target, to_user=request.user),
            ).first()
            if existing is not None:
                existing.from_user = request.user
                existing.to_user = target
                existing.status = Friendship.STATUS_PENDING
                existing.save()
            else:
                Friendship.objects.create(from_user=request.user, to_user=target)

            messages.success(request, f'Заявка в друзья отправлена пользователю {get_display_name(target)}.')
            return redirect('friends')
    else:
        form = AddFriendForm(user=request.user)

    # Built from the Friendship rows directly (rather than Friendship.friends_of)
    # so each entry also carries the friendship's own pk, needed by the
    # "remove friend" button/URL in the template.
    accepted = Friendship.objects.filter(
        Q(from_user=request.user) | Q(to_user=request.user),
        status=Friendship.STATUS_ACCEPTED,
    ).select_related('from_user__profile', 'to_user__profile')

    friends_with_progress = []
    for friendship in accepted:
        other = friendship.to_user if friendship.from_user_id == request.user.id else friendship.from_user
        friends_with_progress.append({
            'friendship_pk': friendship.pk,
            'user': other,
            'nickname': get_display_name(other),
            'progress': get_user_progress(other),
        })
    friends_with_progress.sort(key=lambda item: item['progress']['level'], reverse=True)

    return render(request, 'accounts/friends.html', {
        'form': form,
        'friends': friends_with_progress,
        'incoming_requests': Friendship.pending_received_by(request.user),
        'outgoing_requests': Friendship.pending_sent_by(request.user),
    })


@login_required
def friend_request_accept(request, pk):
    if request.method != 'POST':
        return redirect('friends')
    friend_request = get_object_or_404(
        Friendship, pk=pk, to_user=request.user, status=Friendship.STATUS_PENDING,
    )
    friend_request.status = Friendship.STATUS_ACCEPTED
    friend_request.save()
    messages.success(request, f'Теперь вы друзья с {get_display_name(friend_request.from_user)}.')
    return redirect('friends')


@login_required
def friend_request_decline(request, pk):
    if request.method != 'POST':
        return redirect('friends')
    friend_request = get_object_or_404(
        Friendship, pk=pk, to_user=request.user, status=Friendship.STATUS_PENDING,
    )
    friend_request.status = Friendship.STATUS_DECLINED
    friend_request.save()
    return redirect('friends')


@login_required
def friend_remove(request, pk):
    """Remove an accepted friendship. Either side of the friendship may
    remove it, so the lookup matches `pk` on either from_user or to_user."""
    if request.method != 'POST':
        return redirect('friends')
    friendship = get_object_or_404(
        Friendship,
        Q(from_user=request.user) | Q(to_user=request.user),
        pk=pk, status=Friendship.STATUS_ACCEPTED,
    )
    friendship.delete()
    messages.info(request, 'Пользователь удалён из друзей.')
    return redirect('friends')
