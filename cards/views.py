import random

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import CardForm, CollectionForm
from .models import Card, ReviewLog, Collection
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


@login_required
def review(request):
    # The collection filter is read from the query string even on a POST
    # (the add-card form's `action` carries it along, see review.html) so
    # that adding a card while a filter is active redirects back into the
    # same filtered view instead of silently dropping the filter.
    selected_collection = None
    collection_id = request.GET.get('collection')
    if collection_id:
        selected_collection = get_object_or_404(Collection, pk=collection_id, owner=request.user)

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
            return redirect(_review_url(selected_collection))
    else:
        initial = {'collection': selected_collection.pk} if selected_collection else None
        form = CardForm(user=request.user, initial=initial)

    cards = Card.objects.filter(user=request.user, next_review_at__lte=timezone.now())
    if selected_collection:
        cards = cards.filter(collection=selected_collection)

    card = cards.order_by('next_review_at').first()
    has_history = ReviewLog.objects.filter(user=request.user).exists()
    return render(request, 'cards/review.html', {
        'card': card,
        'has_history': has_history,
        'collections': Collection.objects.filter(owner=request.user),
        'selected_collection': selected_collection,
        'form': form,
    })


def _review_url(selected_collection):
    """The review screen's URL, carrying the active ?collection= filter
    (if any) along -- shared by the add-card redirect here and by
    _review_redirect below (grade/undo)."""
    if selected_collection:
        return f"{reverse('cards:review')}?collection={selected_collection.pk}"
    return reverse('cards:review')


def _review_redirect(request):
    """Redirect back to the review screen, preserving the ?collection=
    filter (if any) that was active when the grade/undo form was submitted."""
    collection_id = request.POST.get('collection')
    if collection_id:
        return redirect(f"{reverse('cards:review')}?collection={collection_id}")
    return redirect(reverse('cards:review'))


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
        'cards': collection.cards.all(),
        'form': form,
    })


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


SESSION_QUIZ_KEY = 'quiz'


@login_required
def study_topics(request):
    """Topic picker: the user's own collections, each leading to
    study_choose. "Add topics" sends them to the library to make/take more."""
    collections = Collection.objects.filter(owner=request.user)
    return render(request, 'cards/study_topics.html', {'collections': collections})


@login_required
def study_choose(request, pk):
    """Ask how to study one topic: the whole thing (an ungraded quiz, see
    quiz_start) or just what's not learned yet (the ordinary spaced-repetition
    review, filtered to this collection -- same as the collection filter on
    the review screen)."""
    collection = get_object_or_404(Collection, pk=pk, owner=request.user)
    return render(request, 'cards/study_choose.html', {'collection': collection})


@login_required
def quiz_start(request, pk):
    """Start an ad-hoc, ungraded run through every card in one topic.

    This deliberately never touches Card.stage/next_review_at or writes a
    ReviewLog -- it's a practice pass, not a spaced-repetition session.
    All of its state (which cards are left, which were missed) lives only
    in the session, under SESSION_QUIZ_KEY.
    """
    if request.method != 'POST':
        return redirect('cards:study_topics')

    collection = get_object_or_404(Collection, pk=pk, owner=request.user)
    card_ids = list(collection.cards.filter(user=request.user).values_list('pk', flat=True))
    random.shuffle(card_ids)

    request.session[SESSION_QUIZ_KEY] = {
        'collection_id': collection.pk,
        'collection_name': collection.name,
        'queue': card_ids,
        'wrong': [],
        'total': len(card_ids),
        'correct_count': 0,
    }
    return redirect('cards:quiz')


@login_required
def quiz(request):
    state = request.session.get(SESSION_QUIZ_KEY)
    if not state:
        return redirect('cards:study_topics')

    if state['queue']:
        card = get_object_or_404(Card, pk=state['queue'][0], user=request.user)
        return render(request, 'cards/quiz.html', {
            'card': card,
            'collection_name': state['collection_name'],
            'remaining': len(state['queue']),
            'total': state['total'],
        })

    # Queue empty -- this pass is done, show the summary/retry screen.
    return render(request, 'cards/quiz.html', {
        'finished': True,
        'collection_name': state['collection_name'],
        'correct_count': state['correct_count'],
        'wrong_count': len(state['wrong']),
        'total': state['total'],
    })


@login_required
def quiz_grade(request):
    """Mark the current quiz card right/wrong and advance -- session-only,
    no Card/ReviewLog write (see quiz_start's docstring for why)."""
    if request.method != 'POST':
        return redirect('cards:quiz')

    state = request.session.get(SESSION_QUIZ_KEY)
    if not state or not state['queue']:
        return redirect('cards:quiz')

    card_id = state['queue'].pop(0)
    if request.POST.get('correct') == '1':
        state['correct_count'] += 1
    else:
        state['wrong'].append(card_id)
    request.session[SESSION_QUIZ_KEY] = state

    return redirect('cards:quiz')


@login_required
def quiz_retry(request):
    """Start a new pass through only the cards missed in the previous one."""
    if request.method != 'POST':
        return redirect('cards:quiz')

    state = request.session.get(SESSION_QUIZ_KEY)
    if not state:
        return redirect('cards:study_topics')

    wrong = state['wrong']
    request.session[SESSION_QUIZ_KEY] = {
        'collection_id': state['collection_id'],
        'collection_name': state['collection_name'],
        'queue': wrong,
        'wrong': [],
        'total': len(wrong),
        'correct_count': 0,
    }
    return redirect('cards:quiz')


@login_required
def quiz_exit(request):
    if request.method == 'POST':
        request.session.pop(SESSION_QUIZ_KEY, None)
    return redirect('cards:list')
