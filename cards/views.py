import random

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode

from .forms import CardForm, CollectionForm
from .models import Card, Collection, ReviewLog, TopicRun
from .quotes import get_quote_of_the_day
from .scheduler import MAX_STAGE, STAGE_LABELS, TEST_MODE_INTERVAL, schedule_next_review

# Visibility levels a collection can be viewed at by someone other than its
# owner: PUBLIC ones show up in the shared library listing; UNLISTED ones
# are reachable only by their secret share-link (share_token) but not listed.
# PRIVATE collections never appear here -- only their owner can see them.
VIEWABLE_BY_OTHERS = [Collection.VISIBILITY_PUBLIC, Collection.VISIBILITY_UNLISTED]


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

    cards = list(Card.objects.filter(user=request.user).select_related('collection'))
    for card in cards:
        card.stage_label = STAGE_LABELS[card.stage] if card.stage < len(STAGE_LABELS) else card.stage

    now = timezone.localtime()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timezone.timedelta(days=today_start.weekday())

    reviewed_today = ReviewLog.objects.filter(user=request.user, reviewed_at__gte=today_start).count()
    reviewed_this_week = ReviewLog.objects.filter(user=request.user, reviewed_at__gte=week_start).count()
    due_count = Card.objects.filter(user=request.user, next_review_at__lte=timezone.now()).count()

    learned_count = sum(1 for card in cards if card.stage >= MAX_STAGE)
    quote_text, quote_author = get_quote_of_the_day()

    return render(request, 'cards/card_list.html', {
        'form': form,
        'cards': cards,
        'collections': Collection.objects.filter(owner=request.user),
        'reviewed_today': reviewed_today,
        'reviewed_this_week': reviewed_this_week,
        'due_count': due_count,
        'learned_count': learned_count,
        'quote_text': quote_text,
        'quote_author': quote_author,
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
def card_set_collection(request, pk):
    """Move one of the current user's own cards into a different one of
    their own collections (or out of any collection). Only `collection`
    changes -- stage/next_review_at/etc are left untouched, so moving a
    card between collections never resets its learning progress."""
    if request.method != 'POST':
        return redirect('cards:list')

    card = get_object_or_404(Card, pk=pk, user=request.user)
    collection_id = request.POST.get('collection')
    if collection_id:
        card.collection = get_object_or_404(Collection, pk=collection_id, owner=request.user)
    else:
        card.collection = None
    card.save()

    return redirect('cards:list')


@login_required
def card_take(request, pk):
    """Copy a card from a collection the user can see (their own, or
    someone else's public/unlisted one) into the user's own cards.

    This always creates a *new* Card row for the current user (never
    reuses someone else's row) -- spaced-repetition progress is personal,
    so a freshly taken card always starts at stage 0. `source_collection`
    records where it came from and is never changed again; `collection`
    is where it lands in the taker's own library and can be moved later
    via card_set_collection.
    """
    if request.method != 'POST':
        return redirect('cards:library')

    source_card = get_object_or_404(
        Card.objects.filter(
            Q(collection__visibility__in=VIEWABLE_BY_OTHERS) | Q(collection__owner=request.user),
        ),
        pk=pk,
    )

    target_collection = None
    collection_id = request.POST.get('collection')
    if collection_id:
        target_collection = get_object_or_404(Collection, pk=collection_id, owner=request.user)

    card, created = Card.objects.get_or_create(
        user=request.user,
        question=source_card.question,
        defaults={
            'answer': source_card.answer,
            'collection': target_collection,
            'source_collection': source_card.collection,
        },
    )
    if created:
        messages.success(request, 'Card added to your cards.')
    else:
        messages.info(request, 'You already have a card with this question.')

    return redirect('cards:collection_view', token=source_card.collection.share_token)


COLLECTION_TAKE_NEW = 'new'


@login_required
def collection_take(request, token):
    """Copy every card of a collection the user can see into their own cards
    in one go -- the bulk version of card_take, with the same rules: each
    card becomes a new row for this user starting at stage 0, and questions
    the user already has are skipped rather than duplicated.

    POST `collection` picks where the copies land:
      'new' (default) -- the user's own collection holding earlier copies
                         from this source if there is one, otherwise a new
                         private collection named after the source;
      ''              -- no collection (straight into the study pool);
      <pk>            -- one of the user's existing collections.
    Taking the same collection again therefore only adds cards the owner
    has added since.
    """
    collection = get_object_or_404(
        Collection.objects.filter(Q(visibility__in=VIEWABLE_BY_OTHERS) | Q(owner=request.user)),
        share_token=token,
    )
    if request.method != 'POST':
        return redirect('cards:collection_view', token=token)

    choice = request.POST.get('collection', COLLECTION_TAKE_NEW)
    if choice == COLLECTION_TAKE_NEW:
        earlier_copy = (
            Card.objects.filter(user=request.user, source_collection=collection, collection__owner=request.user)
            .values_list('collection_id', flat=True).first()
        )
        if earlier_copy:
            target = Collection.objects.get(pk=earlier_copy)
        else:
            target = Collection.objects.create(
                owner=request.user, name=collection.name, description=collection.description,
            )
    elif choice:
        target = get_object_or_404(Collection, pk=choice, owner=request.user)
    else:
        target = None

    existing = set(Card.objects.filter(user=request.user).values_list('question', flat=True))
    new_cards = [
        Card(
            user=request.user, question=card.question, answer=card.answer,
            collection=target, source_collection=collection,
        )
        for card in collection.cards.all()
        if card.question not in existing
    ]
    Card.objects.bulk_create(new_cards)
    skipped = collection.cards.count() - len(new_cards)

    msg = f'Added {len(new_cards)} card(s)'
    msg += f' to "{target.name}".' if target else ' without a collection.'
    if skipped:
        msg += f' Skipped {skipped} you already have.'
    messages.success(request, msg)

    if target:
        return redirect('cards:collection_detail', pk=target.pk)
    return redirect('cards:list')


@login_required
def toggle_test_mode(request):
    if request.method != 'POST':
        return redirect('cards:review')

    request.session['test_mode'] = not request.session.get('test_mode', False)

    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('cards:review')


NO_COLLECTION = 'none'


def _parse_topic_filter(user, values):
    """Turn the ?collection=... values (any number of them) into the user's
    selected collections plus whether "no collection" is ticked. Unknown or
    foreign ids are ignored rather than 404ing -- it's just a filter."""
    ids = [v for v in values if v.isdigit()]
    selected = list(Collection.objects.filter(owner=user, pk__in=ids))
    return selected, NO_COLLECTION in values


def _topic_query(selected, include_none):
    params = [('collection', c.pk) for c in selected]
    if include_none:
        params.append(('collection', NO_COLLECTION))
    return urlencode(params)


def _review_url(selected, include_none):
    """The review screen's URL carrying the active topic filter along."""
    query = _topic_query(selected, include_none)
    return reverse('cards:review') + (f'?{query}' if query else '')


@login_required
def review(request):
    # The topic filter is read from the query string even on a POST (the
    # add-card form's `action` carries it along, see review.html) so adding
    # a card while a filter is active returns to the same filtered view.
    selected, include_none = _parse_topic_filter(request.user, request.GET.getlist('collection'))

    if request.method == 'POST':
        form = CardForm(request.POST, user=request.user)
        if form.is_valid():
            card = form.save(commit=False)
            card.user = request.user
            # Due immediately, so it joins today's review pool right away
            # -- it sorts behind cards that were already due, rather than
            # jumping the queue ahead of them.
            card.next_review_at = timezone.now()
            card.save()
            return redirect(_review_url(selected, include_none))
    else:
        initial = {'collection': selected[0].pk} if len(selected) == 1 and not include_none else None
        form = CardForm(user=request.user, initial=initial)

    cards = Card.objects.filter(user=request.user, next_review_at__lte=timezone.now())
    if selected or include_none:
        topic_q = Q(collection__in=selected)
        if include_none:
            topic_q |= Q(collection__isnull=True)
        cards = cards.filter(topic_q)

    card = cards.order_by('next_review_at').first()
    has_history = ReviewLog.objects.filter(user=request.user).exists()
    return render(request, 'cards/review.html', {
        'card': card,
        'has_history': has_history,
        'collections': Collection.objects.filter(owner=request.user),
        'selected_ids': {c.pk for c in selected},
        'include_none': include_none,
        'filter_active': bool(selected or include_none),
        'filter_names': [c.name for c in selected] + (['No collection'] if include_none else []),
        'topic_query': _topic_query(selected, include_none),
        'form': form,
    })


def _review_redirect(request):
    """Redirect back to the review screen, preserving the topic filter that
    was active when the grade/undo form was submitted."""
    selected, include_none = _parse_topic_filter(request.user, request.POST.getlist('collection'))
    return redirect(_review_url(selected, include_none))


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

    return _review_redirect(request)


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

    return _review_redirect(request)


@login_required
def collection_list(request):
    if request.method == 'POST':
        form = CollectionForm(request.POST)
        if form.is_valid():
            collection = form.save(commit=False)
            collection.owner = request.user
            collection.save()
            return redirect('cards:collections')
    else:
        form = CollectionForm()

    collections = list(Collection.objects.filter(owner=request.user))

    return render(request, template_name='cards/collection_list.html', context={
        'form': form,
        'collections': collections,
    })


@login_required
def collection_detail(request, pk):
    """A user's own collection: its card list, a form to add a new card
    straight into it, plus (for anything other than a private collection)
    the share link other users can use to reach `collection_view` for it."""
    collection = get_object_or_404(Collection, pk=pk, owner=request.user)

    if request.method == 'POST':
        form = CardForm(request.POST, user=request.user)
        if form.is_valid():
            card = form.save(commit=False)
            card.user = request.user
            card.next_review_at = timezone.now()
            card.save()
            return redirect('cards:collection_detail', pk=collection.pk)
    else:
        form = CardForm(user=request.user, initial={'collection': collection.pk})

    return render(request, template_name='cards/collection_detail.html', context={
        'collection': collection,
        'visibility_choices': Collection.VISIBILITY_CHOICES,
        'share_path': reverse('cards:collection_view', args=[collection.share_token]),
        'cards': collection.cards.all(),
        'form': form,
    })


@login_required
def collection_set_visibility(request, pk):
    """Change who can see one of the user's own collections. The share
    link (share_token) stays the same, so switching private -> by-link ->
    private turns the same link on and off."""
    collection = get_object_or_404(Collection, pk=pk, owner=request.user)
    if request.method == 'POST':
        visibility = request.POST.get('visibility')
        if visibility in dict(Collection.VISIBILITY_CHOICES):
            collection.visibility = visibility
            collection.save(update_fields=['visibility'])
    return redirect('cards:collection_detail', pk=pk)


@login_required
def collection_library(request):
    """Shared library: every PUBLIC collection other than the current
    user's own (those already show up on their "My collections" page)."""
    collections = (
        Collection.objects.filter(visibility=Collection.VISIBILITY_PUBLIC)
        .exclude(owner=request.user)
        .select_related('owner__profile')
    )
    return render(request, 'cards/collection_library.html', {'collections': collections})


@login_required
def collection_view(request, token):
    """View a collection by its secret share token -- works for the
    owner's own collections (any visibility) and for anyone else as long
    as the collection is public or unlisted. A private collection looked
    up by someone other than its owner 404s, same as a wrong token would.
    """
    collection = get_object_or_404(
        Collection.objects.filter(Q(visibility__in=VIEWABLE_BY_OTHERS) | Q(owner=request.user)),
        share_token=token,
    )
    is_owner = collection.owner_id == request.user.id

    return render(request, 'cards/collection_view.html', {
        'collection': collection,
        'cards': collection.cards.all(),
        'is_owner': is_owner,
        'my_collections': None if is_owner else Collection.objects.filter(owner=request.user),
    })


@login_required
def study_topics(request):
    """Topic picker: the user's own collections, each leading to
    study_choose, with the state of its whole-topic run if one is going."""
    collections = list(Collection.objects.filter(owner=request.user))
    runs = {r.collection_id: r for r in TopicRun.objects.filter(user=request.user)}
    for collection in collections:
        collection.run = runs.get(collection.pk)
    return render(request, 'cards/study_topics.html', {'collections': collections})


@login_required
def study_choose(request, pk):
    """Ask how to study one topic: go through the whole thing (a TopicRun,
    see topic_run) or just what's due (the ordinary spaced-repetition review,
    filtered to this collection)."""
    collection = get_object_or_404(Collection, pk=pk, owner=request.user)
    run = TopicRun.objects.filter(user=request.user, collection=collection).first()
    return render(request, 'cards/study_choose.html', {'collection': collection, 'run': run})


def _new_round(card_ids):
    card_ids = list(card_ids)
    random.shuffle(card_ids)
    return {'queue': card_ids, 'wrong': [], 'round_total': len(card_ids), 'correct_count': 0}


@login_required
def run_start(request, pk):
    """Continue this topic's run, or start round 1 over every card in the
    topic if there's none yet. Never touches Card.stage or ReviewLog."""
    if request.method != 'POST':
        return redirect('cards:study_choose', pk=pk)
    collection = get_object_or_404(Collection, pk=pk, owner=request.user)
    if not TopicRun.objects.filter(user=request.user, collection=collection).exists():
        card_ids = collection.cards.filter(user=request.user).values_list('pk', flat=True)
        TopicRun.objects.create(user=request.user, collection=collection, **_new_round(card_ids))
    return redirect('cards:topic_run', pk=pk)


@login_required
def topic_run(request, pk):
    collection = get_object_or_404(Collection, pk=pk, owner=request.user)
    run = TopicRun.objects.filter(user=request.user, collection=collection).first()
    if run is None:
        return redirect('cards:study_choose', pk=pk)

    # Drop cards deleted since the run started.
    if run.queue:
        alive = set(Card.objects.filter(user=request.user, pk__in=run.queue).values_list('pk', flat=True))
        if len(alive) != len(run.queue):
            run.queue = [cid for cid in run.queue if cid in alive]
            run.save()

    context = {'collection': collection, 'run': run}
    if run.queue:
        context['card'] = Card.objects.get(pk=run.queue[0])
        context['position'] = run.round_total - len(run.queue) + 1
    return render(request, 'cards/quiz.html', context)


@login_required
def run_grade(request, pk):
    if request.method != 'POST':
        return redirect('cards:topic_run', pk=pk)
    run = get_object_or_404(TopicRun, user=request.user, collection_id=pk)
    # Only grade the card the form was showing -- a double-submit or a stale
    # tab must not grade the next card in the queue.
    if run.queue and str(run.queue[0]) == request.POST.get('card'):
        card_id = run.queue.pop(0)
        if request.POST.get('correct') == '1':
            run.correct_count += 1
        else:
            run.wrong.append(card_id)
        run.save()
    return redirect('cards:topic_run', pk=pk)


@login_required
def run_next_round(request, pk):
    """Start the next round over only the cards missed in this one."""
    if request.method != 'POST':
        return redirect('cards:topic_run', pk=pk)
    run = get_object_or_404(TopicRun, user=request.user, collection_id=pk)
    if run.round_finished and run.wrong:
        for field, value in _new_round(run.wrong).items():
            setattr(run, field, value)
        run.round += 1
        run.save()
    return redirect('cards:topic_run', pk=pk)


@login_required
def run_reset(request, pk):
    """Throw away this topic's run progress (spaced-repetition progress is
    untouched). With restart=1, immediately start a fresh round 1."""
    if request.method != 'POST':
        return redirect('cards:study_choose', pk=pk)
    collection = get_object_or_404(Collection, pk=pk, owner=request.user)
    TopicRun.objects.filter(user=request.user, collection=collection).delete()
    if request.POST.get('restart') == '1':
        return run_start(request, pk)
    messages.info(request, f'Progress for "{collection.name}" reset.')
    return redirect('cards:study_choose', pk=pk)
