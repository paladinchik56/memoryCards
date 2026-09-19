from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import CardForm
from .models import Card, ReviewLog
from .scheduler import MAX_STAGE, STAGE_LABELS, TEST_MODE_INTERVAL, schedule_next_review


def _ru_plural(n, one, few, many):
    """Pick the Russian plural form matching count `n` (e.g. карточка/карточки/карточек)."""
    n_abs = abs(n) % 100
    n1 = n_abs % 10
    if 11 <= n_abs <= 14:
        return many
    if n1 == 1:
        return one
    if 2 <= n1 <= 4:
        return few
    return many


def _hero_message(due_count, total_cards):
    if total_cards == 0:
        return 'Добавьте первую карточку, чтобы начать обучение!'
    if due_count == 0:
        return 'Все карточки повторены — отличная работа! 🎉'
    word = _ru_plural(due_count, 'карточка', 'карточки', 'карточек')
    return f'Сегодня к повторению: {due_count} {word}'


@login_required
def card_list(request):
    if request.method == 'POST':
        form = CardForm(request.POST, user=request.user)
        if form.is_valid():
            card = form.save(commit=False)
            card.user = request.user
            card.next_review_at = timezone.now()
            card.save()
            return redirect('cards:list')
    else:
        form = CardForm(user=request.user)

    cards = list(Card.objects.filter(user=request.user))
    for card in cards:
        card.stage_label = STAGE_LABELS[card.stage] if card.stage < len(STAGE_LABELS) else card.stage

    now = timezone.localtime()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timezone.timedelta(days=today_start.weekday())

    reviewed_today = ReviewLog.objects.filter(user=request.user, reviewed_at__gte=today_start).count()
    reviewed_this_week = ReviewLog.objects.filter(user=request.user, reviewed_at__gte=week_start).count()
    due_count = Card.objects.filter(user=request.user, next_review_at__lte=timezone.now()).count()

    total_cards = len(cards)
    not_started_count = sum(1 for card in cards if not card.is_reviewed)
    learned_count = sum(1 for card in cards if card.stage >= MAX_STAGE)
    learned_pct = round(learned_count / total_cards * 100) if total_cards else 0

    return render(request, 'cards/card_list.html', {
        'form': form,
        'cards': cards,
        'reviewed_today': reviewed_today,
        'reviewed_this_week': reviewed_this_week,
        'due_count': due_count,
        'total_cards': total_cards,
        'not_started_count': not_started_count,
        'learned_count': learned_count,
        'learned_pct': learned_pct,
        'hero_message': _hero_message(due_count, total_cards),
    })


@login_required
def card_edit(request, pk):
    card = get_object_or_404(Card, pk=pk, user=request.user)
    if request.method == 'POST':
        form = CardForm(request.POST, instance=card, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('cards:list')
    else:
        form = CardForm(instance=card, user=request.user)
    return render(request, 'cards/card_edit.html', {'form': form, 'card': card})


@login_required
def card_delete(request, pk):
    card = get_object_or_404(Card, pk=pk, user=request.user)
    if request.method == 'POST':
        card.delete()
        return redirect('cards:list')
    return render(request, 'cards/card_delete.html', {'card': card})


@login_required
def toggle_test_mode(request):
    if request.method != 'POST':
        return redirect('cards:review')

    request.session['test_mode'] = not request.session.get('test_mode', False)

    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('cards:review')


@login_required
def review(request):
    card = (
        Card.objects.filter(user=request.user, next_review_at__lte=timezone.now())
        .order_by('next_review_at')
        .first()
    )
    has_history = ReviewLog.objects.filter(user=request.user).exists()
    return render(request, 'cards/review.html', {'card': card, 'has_history': has_history})


@login_required
def review_grade(request, pk):
    if request.method != 'POST':
        return redirect('cards:review')

    card = get_object_or_404(Card, pk=pk, user=request.user)
    correct = request.POST.get('correct') == '1'

    previous_stage = card.stage
    previous_is_reviewed = card.is_reviewed
    previous_next_review_at = card.next_review_at if previous_is_reviewed else None

    test_mode = request.session.get('test_mode', False)
    new_stage, next_at = schedule_next_review(
        card.stage, correct,
        fixed_interval=TEST_MODE_INTERVAL if test_mode else None,
    )

    ReviewLog.objects.create(
        card=card,
        user=request.user,
        was_correct=correct,
        previous_stage=previous_stage,
        new_stage=new_stage,
        previous_is_reviewed=previous_is_reviewed,
        previous_next_review_at=previous_next_review_at,
        new_next_review_at=next_at,
    )

    card.stage = new_stage
    card.next_review_at = next_at
    card.is_reviewed = True
    card.save()

    return redirect('cards:review')


@login_required
def review_undo(request):
    if request.method != 'POST':
        return redirect('cards:review')

    last_log = ReviewLog.objects.filter(user=request.user).order_by('-reviewed_at').first()
    if last_log:
        card = last_log.card
        card.stage = last_log.previous_stage
        card.is_reviewed = last_log.previous_is_reviewed
        card.next_review_at = last_log.previous_next_review_at or timezone.now()
        card.save()

    return redirect('cards:review')
