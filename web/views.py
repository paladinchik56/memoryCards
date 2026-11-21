"""The website: the same three tabs and rules as the mobile app (Study,
Library, Profile). Shared logic lives in cards/ (scheduler, blitz order,
services); this module only does pages and forms."""
import csv
import random
import uuid as uuid_lib
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.http import require_POST

from accounts.models import Profile, get_display_name, nickname_validator
from cards import blitz
from cards.models import Card, Collection, ReviewLog, TopicRun, TopicSubscription
from cards.scheduler import MAX_STAGE, REQUIRED_CORRECT, STAGE_INTERVALS, TEST_MODE_INTERVAL
from cards.services import (
    add_foreign_to_pool, apply_review, copy_into_topic, remove_from_pool, reset_into_pool,
)

from .i18n import LANGUAGES, format_duration, strings, tr

VIEWABLE_BY_OTHERS = [Collection.VISIBILITY_PUBLIC, Collection.VISIBILITY_UNLISTED]
SESSION_BLITZ = 'blitz'
SESSION_UNDO = 'blitz_undo'
NONE = 'none'  # the "No topic" pseudo-topic


def home(request):
    return redirect('web:study' if request.user.is_authenticated else 'login')


def _safe_next(request, default):
    nxt = request.POST.get('next') or request.GET.get('next')
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return default


def _when(card, t, now=None):
    now = now or timezone.now()
    if card.next_review_at <= now:
        return t['cards_now']
    return format_duration((card.next_review_at - now).total_seconds(), t)


# ==================================================================== study

@login_required
def study(request):
    now = timezone.now()
    pool = Card.objects.filter(user=request.user, in_pool=True)
    return render(request, 'web/study.html', {
        'tab': 'study',
        'due': pool.filter(next_review_at__lte=now).count(),
        'total': pool.count(),
    })


def _filter_topics(request):
    """Topics offered by the blitz filter: own + added (subscribed)."""
    own = list(Collection.objects.filter(owner=request.user).order_by('name'))
    added = list(Collection.objects.filter(subscriptions__user=request.user).order_by('name'))
    return own, added


FULL_STAGES = (1, MAX_STAGE + 1)  # stages as the user sees them: 1..7


def _blitz_filter(request):
    """Blitz filter from ?t=<collection uuid>&t=none&smin=2&smax=7.
    Topics: any of them (OR); stages: an inclusive range, numbered from 1."""
    data = request.GET if request.method == 'GET' else request.POST
    values = [v for v in data.getlist('t') if v][:50]

    def stage(key, default):
        try:
            return min(max(int(data.get(key, '')), FULL_STAGES[0]), FULL_STAGES[1])
        except ValueError:
            return default

    lo, hi = stage('smin', FULL_STAGES[0]), stage('smax', FULL_STAGES[1])
    return values, (min(lo, hi), max(lo, hi))


def _due(user, values, stages, now):
    cards = Card.objects.filter(user=user, in_pool=True, next_review_at__lte=now)
    if values:
        uuids = [v for v in values if v != NONE]
        q = Q(collection__uuid__in=uuids) | Q(source_collection__uuid__in=uuids)
        if NONE in values:
            q |= Q(collection__isnull=True)
        cards = cards.filter(q)
    if stages != FULL_STAGES:
        cards = cards.filter(stage__gte=stages[0] - 1, stage__lte=stages[1] - 1)
    return list(cards)


def _blitz_params(values, stages):
    """The filter as (name, value) pairs: for links and hidden form fields."""
    pairs = [('t', v) for v in values]
    if stages != FULL_STAGES:
        pairs += [('smin', stages[0]), ('smax', stages[1])]
    return pairs


def _blitz_url(values, stages):
    params = _blitz_params(values, stages)
    return reverse('web:blitz') + (('?' + urlencode(params)) if params else '')


@login_required
def blitz_view(request):
    values, stages = _blitz_filter(request)
    now = timezone.now()
    due = _due(request.user, values, stages, now)
    state = request.session.get(SESSION_BLITZ) or blitz.new_state()
    card = next((c for c in due if c.pk == state.get('current')), None)
    if card is None:
        card = blitz.choose_next(due, now, state)
        state['current'] = card.pk if card else None
        request.session[SESSION_BLITZ] = state
    own, added = _filter_topics(request)
    t = strings(request)
    selected = set(values)
    label = t['blitz_all_topics'] if not values else tr(request, 'blitz_topics_n', n=len(values))
    if stages != FULL_STAGES:
        label += ' · ' + tr(request, 'blitz_stages_range', lo=stages[0], hi=stages[1])
    return render(request, 'web/blitz.html', {
        'card': card,
        'left': len(due),
        'params': _blitz_params(values, stages),
        'stages': stages,
        'stage_options': [(i + 1, format_duration(iv.total_seconds(), t)) for i, iv in enumerate(STAGE_INTERVALS)],
        'filter_label': label,
        'filtered': bool(values) or stages != FULL_STAGES,
        'own_topics': [(c.uuid, c.name, str(c.uuid) in selected) for c in own],
        'added_topics': [(c.uuid, c.name, str(c.uuid) in selected) for c in added],
        'none_selected': NONE in selected,
        'add_url': reverse('web:add') + '?' + urlencode({'next': _blitz_url(values, stages)}),
        'can_undo': bool(request.session.get(SESSION_UNDO)),
    })


@login_required
@require_POST
def blitz_answer(request):
    values, stages = _blitz_filter(request)
    card = get_object_or_404(Card, user=request.user, uuid=_as_uuid(request.POST.get('card')))
    correct = request.POST.get('correct') == '1'
    test_mode = request.session.get('test_mode', False)
    log = apply_review(card, correct, fixed_interval=TEST_MODE_INTERVAL if test_mode else None)
    state = request.session.get(SESSION_BLITZ) or blitz.new_state()
    request.session[SESSION_BLITZ] = blitz.after_answer(state, card.pk, correct)
    request.session[SESSION_UNDO] = log.pk
    return redirect(_blitz_url(values, stages))


@login_required
@require_POST
def blitz_remove(request):
    values, stages = _blitz_filter(request)
    card = get_object_or_404(Card, user=request.user, uuid=_as_uuid(request.POST.get('card')))
    remove_from_pool(card)
    state = request.session.get(SESSION_BLITZ) or blitz.new_state()
    request.session[SESSION_BLITZ] = {**state, 'last': card.pk, 'current': None}
    return redirect(_blitz_url(values, stages))


@login_required
@require_POST
def blitz_undo(request):
    """Roll back the last answer given on this page (once). Only answers made
    here: a review that came from the phone is never deleted, or a re-sent
    copy of it would be applied again."""
    values, stages = _blitz_filter(request)
    log_pk = request.session.pop(SESSION_UNDO, None)
    log = ReviewLog.objects.filter(user=request.user, pk=log_pk).select_related('card').first() if log_pk else None
    if log:
        card = log.card
        card.stage, card.correct_count = log.previous_stage, log.previous_correct_count
        card.is_reviewed = log.previous_is_reviewed
        card.next_review_at = log.previous_next_review_at or timezone.now()
        card.save()
        log.delete()
        state = request.session.get(SESSION_BLITZ) or blitz.new_state()
        request.session[SESSION_BLITZ] = {**state, 'current': card.pk, 'last': None}
    return redirect(_blitz_url(values, stages))


@login_required
def add_card(request):
    """Add a card (straight into the blitz). The form stays open and keeps the
    chosen topic; opened from the blitz, it returns there after adding."""
    own = Collection.objects.filter(owner=request.user).order_by('name')
    nxt = _safe_next(request, '')
    topic_uuid = request.session.get('last_topic') or ''
    error, question, answer = None, '', ''
    if request.method == 'POST':
        question = request.POST.get('question', '').strip()
        answer = request.POST.get('answer', '').strip()
        topic_uuid = request.POST.get('topic', '')
        topic = own.filter(uuid=topic_uuid).first() if topic_uuid else None
        request.session['last_topic'] = str(topic.uuid) if topic else ''
        if not question or not answer:
            error = tr(request, 'add_empty')
        elif Card.objects.filter(user=request.user, question=question).exists():
            error = tr(request, 'add_duplicate')
        else:
            Card.objects.create(user=request.user, question=question, answer=answer, collection=topic, in_pool=True)
            messages.success(request, tr(request, 'add_added'))
            if nxt:
                return redirect(nxt)
            return redirect(reverse('web:add'))
    return render(request, 'web/add_card.html', {
        'tab': 'study', 'topics': own, 'topic_uuid': topic_uuid, 'error': error,
        'question': question, 'answer': answer, 'next': nxt,
    })


@login_required
def cards_list(request):
    t = strings(request)
    now = timezone.now()
    cards = (
        Card.objects.filter(user=request.user, in_pool=True)
        .select_related('collection', 'source_collection').order_by('next_review_at')
    )
    rows = [{
        'topic': (c.collection or c.source_collection).name if (c.collection_id or c.source_collection_id) else t['lib_no_topic'],
        'question': c.question, 'answer': c.answer, 'when': _when(c, t, now), 'uuid': c.uuid, 'own_topic': bool(c.collection_id),
    } for c in cards]
    return render(request, 'web/cards.html', {'tab': 'study', 'rows': rows})


# ============================================================= topic study

def _studyable(user):
    """Own topics + added topics: the ones topic study offers."""
    return Collection.objects.filter(Q(owner=user) | Q(subscriptions__user=user)).distinct()


def _run_status(request, run, count):
    if not run:
        return tr(request, 'simple_cards_n', n=count)
    if not run.queue and not run.wrong:
        return tr(request, 'simple_done')
    return tr(request, 'simple_status', round=run.round, left=len(run.queue) or len(run.wrong))


@login_required
def simple_list(request):
    runs = {r.collection_id: r for r in TopicRun.objects.filter(user=request.user)}
    own, added = [], []
    for c in _studyable(request.user).annotate(n=Count('cards')).select_related('owner__profile').order_by('name'):
        item = {'uuid': c.uuid, 'name': c.name, 'status': _run_status(request, runs.get(c.pk), c.n),
                'owner': get_display_name(c.owner)}
        (own if c.owner_id == request.user.id else added).append(item)
    return render(request, 'web/simple_list.html', {'tab': 'study', 'own': own, 'added': added})


def _new_round(card_pks):
    pks = list(card_pks)
    random.shuffle(pks)
    return {'queue': pks, 'wrong': [], 'round_total': len(pks), 'correct_count': 0}


@login_required
def simple_topic(request, uuid):
    """Ask "continue or start over" if there is a run, otherwise start one."""
    collection = get_object_or_404(_studyable(request.user), uuid=uuid)
    run = TopicRun.objects.filter(user=request.user, collection=collection).first()
    if run is None:
        TopicRun.objects.create(user=request.user, collection=collection, round=1,
                                **_new_round(collection.cards.values_list('pk', flat=True)))
        return redirect('web:simple_play', uuid=uuid)
    finished = not run.queue and not run.wrong
    return render(request, 'web/simple_choose.html', {
        'tab': 'study', 'collection': collection, 'run': run, 'finished': finished,
        'continue_text': tr(request, 'simple_continue_text', round=run.round,
                            left=len(run.queue) or len(run.wrong), total=run.round_total),
    })


@login_required
@require_POST
def simple_restart(request, uuid):
    collection = get_object_or_404(_studyable(request.user), uuid=uuid)
    with transaction.atomic():
        TopicRun.objects.filter(user=request.user, collection=collection).delete()
        TopicRun.objects.create(user=request.user, collection=collection, round=1,
                                **_new_round(collection.cards.values_list('pk', flat=True)))
    return redirect('web:simple_play', uuid=uuid)


@login_required
def simple_play(request, uuid):
    collection = get_object_or_404(_studyable(request.user), uuid=uuid)
    run = TopicRun.objects.filter(user=request.user, collection=collection).first()
    if run is None:
        return redirect('web:simple_topic', uuid=uuid)
    alive = set(collection.cards.values_list('pk', flat=True))
    if any(pk not in alive for pk in run.queue + run.wrong):  # cards deleted meanwhile
        run.queue = [pk for pk in run.queue if pk in alive]
        run.wrong = [pk for pk in run.wrong if pk in alive]
        run.save()
    card = Card.objects.get(pk=run.queue[0]) if run.queue else None
    return render(request, 'web/simple_play.html', {
        'tab': 'study', 'collection': collection, 'run': run, 'card': card,
        'position': run.round_total - len(run.queue) + 1,
    })


@login_required
@require_POST
def simple_answer(request, uuid):
    collection = get_object_or_404(_studyable(request.user), uuid=uuid)
    run = get_object_or_404(TopicRun, user=request.user, collection=collection)
    card_pk = Card.objects.filter(uuid=_as_uuid(request.POST.get('card'))).values_list('pk', flat=True).first()
    # Only the card the page was showing: a double submit must not grade the next one.
    if run.queue and run.queue[0] == card_pk:
        run.queue.pop(0)
        if request.POST.get('correct') == '1':
            run.correct_count += 1
        else:
            run.wrong.append(card_pk)
        run.save()
    return redirect('web:simple_play', uuid=uuid)


@login_required
@require_POST
def simple_next(request, uuid):
    collection = get_object_or_404(_studyable(request.user), uuid=uuid)
    run = get_object_or_404(TopicRun, user=request.user, collection=collection)
    if not run.queue and run.wrong:
        for key, value in _new_round(run.wrong).items():
            setattr(run, key, value)
        run.round += 1
        run.save()
    return redirect('web:simple_play', uuid=uuid)


# ================================================================== library

@login_required
def library(request):
    return render(request, 'web/library.html', {
        'tab': 'library',
        'mine': Collection.objects.filter(owner=request.user).count(),
        'added': TopicSubscription.objects.filter(user=request.user).count(),
    })


@login_required
def topics_mine(request):
    topics = Collection.objects.filter(owner=request.user).annotate(n=Count('cards')).order_by('name')
    no_topic = Card.objects.filter(user=request.user, collection__isnull=True).count()
    return render(request, 'web/topics_mine.html', {'tab': 'library', 'topics': topics, 'no_topic': no_topic})


@login_required
def topics_added(request):
    topics = (
        Collection.objects.filter(subscriptions__user=request.user, visibility__in=VIEWABLE_BY_OTHERS)
        .annotate(n=Count('cards')).select_related('owner__profile').order_by('name')
    )
    return render(request, 'web/topics_added.html', {
        'tab': 'library', 'topics': [(c, get_display_name(c.owner)) for c in topics],
    })


def _topic_rows(topics):
    return [{'topic': c, 'owner': get_display_name(c.owner), 'n': c.n} for c in topics]


@login_required
def browse(request):
    q = request.GET.get('q', '').strip().lower()
    topics = (
        Collection.objects.filter(visibility=Collection.VISIBILITY_PUBLIC).exclude(owner=request.user)
        .annotate(n=Count('cards')).select_related('owner__profile').order_by('-created_at')
    )
    if q:
        topics = [c for c in topics if q in f'{c.name} {c.description} {" ".join(c.tags)}'.lower()]
    return render(request, 'web/browse.html', {'tab': 'library', 'rows': _topic_rows(topics), 'q': request.GET.get('q', '')})


@login_required
def author(request, nickname):
    owner = get_object_or_404(Profile, nickname__iexact=nickname).user
    topics = (
        Collection.objects.filter(owner=owner, visibility=Collection.VISIBILITY_PUBLIC)
        .annotate(n=Count('cards')).order_by('-created_at')
    )
    return render(request, 'web/author.html', {'tab': 'library', 'nickname': get_display_name(owner), 'topics': topics})


def _viewable(user, token):
    return get_object_or_404(
        Collection.objects.filter(Q(owner=user) | Q(visibility__in=VIEWABLE_BY_OTHERS)).select_related('owner__profile'),
        share_token=token,
    )


@login_required
def topic(request, token):
    collection = _viewable(request.user, token)
    is_owner = collection.owner_id == request.user.id
    cards = list(collection.cards.order_by('created_at'))
    if is_owner:
        in_blitz = {c.pk for c in cards if c.in_pool}
    else:
        in_blitz = set(Card.objects.filter(user=request.user, in_pool=True, source_card__in=cards).values_list('source_card_id', flat=True))
    return render(request, 'web/topic.html', {
        'tab': 'library',
        'collection': collection,
        'is_owner': is_owner,
        'owner_name': get_display_name(collection.owner),
        'is_added': TopicSubscription.objects.filter(user=request.user, collection=collection).exists(),
        'cards': [(c, c.pk in in_blitz) for c in cards],
        'selecting': request.GET.get('select') == '1',
        'own_topics': Collection.objects.filter(owner=request.user).exclude(pk=collection.pk).order_by('name'),
        'share_url': request.build_absolute_uri(reverse('web:topic', args=[collection.share_token])),
        'source': str(collection.share_token),
    })


@login_required
def no_topic(request):
    cards = list(Card.objects.filter(user=request.user, collection__isnull=True).order_by('created_at'))
    return render(request, 'web/topic.html', {
        'tab': 'library',
        'collection': None,
        'is_owner': True,
        'cards': [(c, c.in_pool) for c in cards],
        'selecting': request.GET.get('select') == '1',
        'own_topics': Collection.objects.filter(owner=request.user).order_by('name'),
        'source': NONE,
    })


@login_required
@require_POST
def subscribe(request, token):
    collection = _viewable(request.user, token)
    if collection.owner_id != request.user.id:
        sub = TopicSubscription.objects.filter(user=request.user, collection=collection)
        if sub.exists():
            sub.delete()
        else:
            TopicSubscription.objects.create(user=request.user, collection=collection)
    return redirect('web:topic', token=token)


def _parse_tags(text):
    return list(dict.fromkeys(t.strip()[:30] for t in text.split(',') if t.strip()))[:10]


@login_required
def topic_edit(request, token=None):
    collection = get_object_or_404(Collection, owner=request.user, share_token=token) if token else None
    error = None
    data = {
        'name': collection.name if collection else '',
        'description': collection.description if collection else '',
        'tags': ', '.join(collection.tags) if collection else '',
        'visibility': collection.visibility if collection else Collection.VISIBILITY_PRIVATE,
    }
    if request.method == 'POST':
        data = {k: request.POST.get(k, '').strip() for k in data}
        if data['visibility'] not in dict(Collection.VISIBILITY_CHOICES):
            data['visibility'] = Collection.VISIBILITY_PRIVATE
        if not data['name']:
            error = tr(request, 'topic_name_required')
        else:
            collection = collection or Collection(owner=request.user)
            collection.name = data['name'][:100]
            collection.description = data['description'][:700]
            collection.tags = _parse_tags(data['tags'])
            collection.visibility = data['visibility']
            collection.save()
            return redirect('web:topic', token=collection.share_token)
    return render(request, 'web/topic_form.html', {
        'tab': 'library', 'collection': collection, 'data': data, 'error': error,
        'visibilities': [(v, f'topic_{v}') for v, _ in Collection.VISIBILITY_CHOICES],
    })


def _as_uuid(value):
    try:
        return uuid_lib.UUID(str(value))
    except ValueError:
        return None


def _back_to_source(source):
    return reverse('web:no_topic') if source == NONE else reverse('web:topic', args=[source])


@login_required
@require_POST
def topic_action(request):
    """Bulk actions on picked cards of a topic page.

    source = share token of the topic, or 'none' (own cards without topic).
    action = to_blitz | copy | move | from_deck | delete. "to_blitz" first
    shows the skip/reset question when some cards are already in the blitz.
    """
    source = request.POST.get('source', '')
    if source != NONE and _as_uuid(source) is None:
        raise Http404
    action = request.POST.get('action', '')
    uuids = [u for u in map(_as_uuid, request.POST.getlist('cards')) if u]
    back = _back_to_source(source)
    if not uuids:
        messages.info(request, tr(request, 'lib_pick_cards'))
        return redirect(back + '?select=1')

    if source == NONE:
        collection, is_owner = None, True
        cards = list(Card.objects.filter(user=request.user, collection__isnull=True, uuid__in=uuids))
    else:
        if _as_uuid(source) is None:
            raise Http404
        collection = _viewable(request.user, source)
        is_owner = collection.owner_id == request.user.id
        cards = list(collection.cards.filter(uuid__in=uuids))
    if not cards:
        return redirect(back)

    if action == 'to_blitz':
        if is_owner:
            conflicts = [c for c in cards if c.in_pool]
        else:
            mine = set(Card.objects.filter(user=request.user, in_pool=True, source_card__in=cards).values_list('source_card_id', flat=True))
            conflicts = [c for c in cards if c.pk in mine]
        if conflicts and request.POST.get('confirm') != '1':
            return render(request, 'web/conflict.html', {
                'tab': 'library', 'source': source, 'cards': cards, 'conflicts': conflicts,
                'new_count': len(cards) - len(conflicts), 'back': back,
            })
        reset = {str(c.uuid) for c in conflicts if request.POST.get(f'choice-{c.uuid}') == 'reset'}
        with transaction.atomic():
            if is_owner:
                fresh = [c for c in cards if not c.in_pool]
                for c in fresh + [c for c in conflicts if str(c.uuid) in reset]:
                    reset_into_pool(c)
                added, n_reset = len(fresh), len([c for c in conflicts if str(c.uuid) in reset])
                skipped = len(conflicts) - n_reset
            else:
                added, n_reset, skipped = add_foreign_to_pool(request.user, cards, {c.uuid for c in cards if str(c.uuid) in reset})
        messages.success(request, tr(request, 'lib_blitz_result', added=added, reset=n_reset, skipped=skipped))
        return redirect(back)

    if action == 'copy':
        target = Collection.objects.filter(owner=request.user, uuid=_as_uuid(request.POST.get('target'))).first()
        if target is None:
            messages.info(request, tr(request, 'lib_no_own_topics'))
            return redirect(back + '?select=1')
        messages.success(request, tr(request, 'lib_copied', n=copy_into_topic(request.user, cards, target)))
        return redirect(back)

    if not is_owner:
        raise Http404
    now = timezone.now()
    if action == 'move':
        target_value = request.POST.get('target') or ''
        target = Collection.objects.filter(owner=request.user, uuid=_as_uuid(target_value)).first() if target_value not in ('', NONE) else None
        if target_value not in ('', NONE) and target is None:
            raise Http404
        Card.objects.filter(pk__in=[c.pk for c in cards]).update(collection=target, content_updated_at=now, updated_at=now)
        messages.success(request, tr(request, 'lib_moved', n=len(cards)))
    elif action == 'from_deck' and collection is not None:
        Card.objects.filter(pk__in=[c.pk for c in cards]).update(collection=None, content_updated_at=now, updated_at=now)
        messages.success(request, tr(request, 'lib_removed', n=len(cards)))
    elif action == 'delete':
        for c in cards:
            c.delete()  # one by one so tombstones reach the phone
        messages.success(request, tr(request, 'lib_deleted', n=len(cards)))
    return redirect(back)


@login_required
def card_detail(request, uuid):
    card = get_object_or_404(Card.objects.select_related('collection'), user=request.user, uuid=uuid)
    back = _safe_next(request, reverse('web:topic', args=[card.collection.share_token]) if card.collection else reverse('web:no_topic'))
    t = strings(request)
    if request.method == 'POST':
        op = request.POST.get('op')
        if op == 'save':
            q, a = request.POST.get('question', '').strip(), request.POST.get('answer', '').strip()
            if q and a:
                card.question, card.answer, card.content_updated_at = q, a, timezone.now()
                card.save()
                messages.success(request, t['card_saved'])
            else:
                messages.info(request, t['add_empty'])
        elif op == 'blitz':
            reset_into_pool(card)
        elif op == 'delete':
            card.delete()
            return redirect(back)
        return redirect(reverse('web:card', args=[card.uuid]) + '?' + urlencode({'next': back}))
    now = timezone.now()
    status = tr(request, 'card_status', stage=card.stage + 1,
                when=t['card_due_now'] if card.next_review_at <= now else tr(request, 'card_due_in', t=_when(card, t, now))) \
        if card.in_pool else t['card_not_in_blitz']
    return render(request, 'web/card.html', {'tab': 'library', 'card': card, 'status': status, 'back': back})


# ================================================================== profile

def _streak(user):
    days = {timezone.localtime(d).date() for d in ReviewLog.objects.filter(user=user).values_list('reviewed_at', flat=True)}
    day = timezone.localdate()
    if day not in days:
        day -= timedelta(days=1)
    n = 0
    while day in days:
        n += 1
        day -= timedelta(days=1)
    return n


@login_required
def profile(request):
    pool = Card.objects.filter(user=request.user, in_pool=True)
    return render(request, 'web/profile.html', {
        'tab': 'profile',
        'nickname': get_display_name(request.user),
        'total': pool.count(),
        'learned': pool.filter(stage__gte=MAX_STAGE).count(),
        'streak': _streak(request.user),
        'test_mode': request.session.get('test_mode', False),
    })


@require_POST
def set_language(request):
    lang = request.POST.get('lang')
    if lang in LANGUAGES:
        request.session['lang'] = lang
    return redirect(_safe_next(request, reverse('web:profile')))


@login_required
@require_POST
def toggle_test_mode(request):
    request.session['test_mode'] = not request.session.get('test_mode', False)
    return redirect('web:profile')


@login_required
def algorithm(request):
    t = strings(request)
    rows = [{
        'stage': i + 1,
        'interval': format_duration(iv.total_seconds(), t),
        'need': REQUIRED_CORRECT[i] if i < MAX_STAGE else t['algo_max'],
    } for i, iv in enumerate(STAGE_INTERVALS)]
    return render(request, 'web/algorithm.html', {'tab': 'profile', 'rows': rows})


@login_required
def account(request):
    user = request.user
    nickname = get_display_name(user)
    errors = []
    if request.method == 'POST':
        nickname = request.POST.get('nickname', '').strip()
        new_password = request.POST.get('new_password', '')
        if not user.check_password(request.POST.get('current_password', '')):
            errors.append(tr(request, 'account_wrong'))
        else:
            if nickname and nickname != get_display_name(user):
                try:
                    nickname_validator(nickname)
                except ValidationError as e:
                    errors += e.messages
                else:
                    if Profile.objects.filter(nickname__iexact=nickname).exclude(user=user).exists():
                        errors.append(tr(request, 'account_taken'))
            if new_password:
                try:
                    validate_password(new_password, user)
                except ValidationError as e:
                    errors += e.messages
            if not errors:
                if nickname:
                    Profile.objects.update_or_create(user=user, defaults={'nickname': nickname})
                if new_password:
                    user.set_password(new_password)
                    user.save(update_fields=['password'])
                    from django.contrib.auth import update_session_auth_hash
                    update_session_auth_hash(request, user)
                messages.success(request, tr(request, 'account_saved'))
                return redirect('web:account')
    return render(request, 'web/account.html', {'tab': 'profile', 'nickname': nickname, 'errors': errors})


@login_required
def export_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="cards.csv"'
    response.write('﻿')  # BOM so Excel opens UTF-8 correctly
    writer = csv.writer(response)
    writer.writerow(['topic', 'question', 'answer', 'in_blitz', 'stage'])
    for c in Card.objects.filter(user=request.user).select_related('collection').order_by('collection__name', 'created_at'):
        writer.writerow([c.collection.name if c.collection else '', c.question, c.answer, int(c.in_pool), c.stage + 1])
    return response
