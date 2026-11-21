"""JSON API for the mobile app.

Auth: POST /api/auth/token/ with {login, password} (nickname or email)
returns a token; every other call sends `Authorization: Token <token>`.

The app is offline-first: it keeps its own copy of the user's collections,
cards and topic runs, and calls POST /api/sync/ whenever it's online. One
sync call both pushes the device's local changes and pulls everything that
changed on the server since the device's last sync -- see `sync` below for
the exact payload and conflict rules.
"""
import uuid as uuid_lib
from datetime import datetime, timezone as dt_timezone

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from accounts.models import Profile, get_display_name, nickname_validator
from cards.models import Card, Collection, PoolEvent, ReviewLog, Tombstone, TopicRun, TopicSubscription
from cards.scheduler import REQUIRED_CORRECT, STAGE_INTERVALS
from cards.services import (
    add_foreign_to_pool, apply_review, copy_cards, copy_into_topic, remove_from_pool, reset_into_pool, take_into_own_copy,
)

VIEWABLE_BY_OTHERS = [Collection.VISIBILITY_PUBLIC, Collection.VISIBILITY_UNLISTED]
VISIBILITIES = {value for value, _ in Collection.VISIBILITY_CHOICES}
MAX_COLLECTION_NAME = Collection._meta.get_field('name').max_length
MAX_DESCRIPTION = Collection._meta.get_field('description').max_length
MAX_TAGS = 10


# ---------------------------------------------------------------- helpers

def _iso(dt):
    return dt.isoformat() if dt else None


def _uuid(value):
    try:
        return uuid_lib.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _datetime(value):
    if not isinstance(value, str):
        return None
    try:
        dt = parse_datetime(value)
    except ValueError:
        return None
    if dt is not None and timezone.is_naive(dt):
        return None  # require an explicit offset, e.g. "...Z"
    return dt


def _user_json(user):
    return {'nickname': get_display_name(user), 'email': user.email}


def _collection_json(c):
    return {
        'uuid': str(c.uuid),
        'name': c.name,
        'description': c.description,
        'visibility': c.visibility,
        'tags': c.tags,
        'share_token': str(c.share_token),
        'created_at': _iso(c.created_at),
        'updated_at': _iso(c.updated_at),
    }


def _card_json(card):
    return {
        'uuid': str(card.uuid),
        'question': card.question,
        'answer': card.answer,
        'collection': str(card.collection.uuid) if card.collection_id else None,
        # Where a copy came from: lets the blitz filter by an added topic.
        'source_collection': str(card.source_collection.uuid) if card.source_collection_id else None,
        'in_pool': card.in_pool,
        'stage': card.stage,
        'correct_count': card.correct_count,
        'is_reviewed': card.is_reviewed,
        'next_review_at': _iso(card.next_review_at),
        'content_updated_at': _iso(card.content_updated_at),
        'created_at': _iso(card.created_at),
        'updated_at': _iso(card.updated_at),
    }


def _run_json(run, uuid_by_pk):
    return {
        'collection': str(run.collection.uuid),
        'round': run.round,
        'queue': [uuid_by_pk[pk] for pk in run.queue if pk in uuid_by_pk],
        'wrong': [uuid_by_pk[pk] for pk in run.wrong if pk in uuid_by_pk],
        'round_total': run.round_total,
        'correct_count': run.correct_count,
        'updated_at': _iso(run.updated_at),
    }


def _viewable_collection(user, token):
    return get_object_or_404(
        Collection.objects.filter(Q(visibility__in=VIEWABLE_BY_OTHERS) | Q(owner=user)),
        share_token=token,
    )


# ------------------------------------------------------------------- auth

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def auth_token(request):
    """{login, password} -> {token, user}. `login` is nickname or email."""
    user = authenticate(request, username=request.data.get('login'), password=request.data.get('password'))
    if user is None:
        return Response({'error': 'invalid_credentials'}, status=400)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'user': _user_json(user)})


auth_token.cls.throttle_scope = 'login'


@api_view(['POST'])
def auth_logout(request):
    Token.objects.filter(user=request.user).delete()
    return Response(status=204)


@api_view(['GET'])
def me(request):
    return Response(_user_json(request.user))


@api_view(['GET'])
@permission_classes([AllowAny])
def scheduler(request):
    """The review rules, so the app can check its built-in copy is current."""
    return Response({
        'intervals_seconds': [int(i.total_seconds()) for i in STAGE_INTERVALS],
        'required_correct': REQUIRED_CORRECT,
    })


# ---------------------------------------------------------------- library

def _topic_list(collections):
    collections = collections.select_related('owner__profile').annotate(card_count=Count('cards')).order_by('-created_at')
    return [
        {
            'share_token': str(c.share_token),
            'name': c.name,
            'description': c.description,
            'tags': c.tags,
            'owner': get_display_name(c.owner),
            'card_count': c.card_count,
        }
        for c in collections
    ]


@api_view(['GET'])
def library(request):
    """Public topics of other users (the shared library)."""
    public = Collection.objects.filter(visibility=Collection.VISIBILITY_PUBLIC).exclude(owner=request.user)
    return Response(_topic_list(public))


@api_view(['GET'])
def author(request, nickname):
    """An author and all their public topics."""
    owner = get_object_or_404(Profile, nickname__iexact=nickname).user
    public = Collection.objects.filter(owner=owner, visibility=Collection.VISIBILITY_PUBLIC)
    return Response({'nickname': get_display_name(owner), 'topics': _topic_list(public)})


@api_view(['GET'])
def shared_collection(request, token):
    """One collection by share token (public, unlisted, or the user's own)."""
    collection = _viewable_collection(request.user, token)
    is_owner = collection.owner_id == request.user.id
    cards = list(collection.cards.all().order_by('created_at'))
    if is_owner:
        in_blitz = {c.pk for c in cards if c.in_pool}
    else:
        in_blitz = set(
            Card.objects.filter(user=request.user, in_pool=True, source_card__in=cards).values_list('source_card_id', flat=True)
        )
    return Response({
        'uuid': str(collection.uuid),
        'share_token': str(collection.share_token),
        'name': collection.name,
        'description': collection.description,
        'tags': collection.tags,
        'owner': get_display_name(collection.owner),
        'is_owner': is_owner,
        'is_added': TopicSubscription.objects.filter(user=request.user, collection=collection).exists(),
        'cards': [
            {'uuid': str(c.uuid), 'question': c.question, 'answer': c.answer, 'in_blitz': c.pk in in_blitz}
            for c in cards
        ],
    })


def _picked_cards(collection, data):
    """The cards of `collection` named in data['cards'] (uuids), or None if invalid."""
    wanted = [_uuid(u) for u in data.get('cards') or []]
    if not wanted or None in wanted:
        return None
    return list(collection.cards.filter(uuid__in=wanted))


@api_view(['POST', 'DELETE'])
def subscribe(request, token):
    """POST: "add the topic to myself" (read-only, in Added topics). DELETE: remove it."""
    collection = _viewable_collection(request.user, token)
    if collection.owner_id == request.user.id:
        return Response({'error': 'own_topic'}, status=400)
    if request.method == 'POST':
        TopicSubscription.objects.get_or_create(user=request.user, collection=collection)
    else:
        TopicSubscription.objects.filter(user=request.user, collection=collection).delete()
    return Response({'is_added': request.method == 'POST'})


@api_view(['POST'])
def add_to_blitz(request, token):
    """Put cards of a viewable topic into the user's blitz.

    Body: {"cards": [uuid...], "reset": [uuid...]} -- cards already in the
    blitz are skipped unless listed in "reset" (then their progress restarts).
    Someone else's cards become linked personal copies (decision 15).
    """
    collection = _viewable_collection(request.user, token)
    cards = _picked_cards(collection, request.data)
    if cards is None:
        return Response({'error': 'bad_cards'}, status=400)
    reset_uuids = {u for u in map(_uuid, request.data.get('reset') or []) if u}
    with transaction.atomic():
        added, reset, skipped = add_foreign_to_pool(request.user, cards, reset_uuids)
    return Response({'added': added, 'reset': reset, 'skipped': skipped})


@api_view(['POST'])
def copy_to_topic(request, token):
    """Copy cards of a viewable topic into one of the user's own topics
    (independent copies, not in the blitz). Body: {"cards": [...], "target": uuid}."""
    collection = _viewable_collection(request.user, token)
    cards = _picked_cards(collection, request.data)
    target = Collection.objects.filter(owner=request.user, uuid=_uuid(request.data.get('target'))).first()
    if cards is None or target is None:
        return Response({'error': 'bad_request'}, status=400)
    return Response({'copied': copy_into_topic(request.user, cards, target)})


@api_view(['POST'])
def account(request):
    """Change nickname and/or password. Body: {current_password, nickname?, new_password?}."""
    user = request.user
    if not user.check_password(request.data.get('current_password') or ''):
        return Response({'error': 'wrong_password'}, status=400)
    nickname = (request.data.get('nickname') or '').strip()
    new_password = request.data.get('new_password') or ''
    errors = {}
    if nickname:
        try:
            nickname_validator(nickname)
        except ValidationError as e:
            errors['nickname'] = e.messages
        else:
            if Profile.objects.filter(nickname__iexact=nickname).exclude(user=user).exists():
                errors['nickname'] = ['taken']
    if new_password:
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            errors['new_password'] = e.messages
    if errors:
        return Response({'error': 'invalid', 'fields': errors}, status=400)
    if nickname:
        Profile.objects.update_or_create(user=user, defaults={'nickname': nickname})
    if new_password:
        user.set_password(new_password)
        user.save(update_fields=['password'])
    return Response(_user_json(user))


@api_view(['POST'])
def take(request, token):
    """Copy cards of a viewable collection into the user's own cards.

    Body: {"target": "new" | null | "<own collection uuid>",
           "cards": ["<card uuid>", ...]   # optional: only these cards}
    "new" (default) = the user's earlier copy of this collection, or a new
    private one; null = no collection. Copies start at stage 0; questions the
    user already has are skipped. Run a sync afterwards to download them.
    """
    source = _viewable_collection(request.user, token)
    target_value = request.data.get('target', 'new')
    if target_value == 'new':
        target = None  # resolved after validation, so a bad request creates nothing
    elif target_value is None:
        target = None
    else:
        target = Collection.objects.filter(owner=request.user, uuid=_uuid(target_value)).first()
        if target is None:
            return Response({'error': 'unknown_target'}, status=400)

    cards = source.cards.all()
    if 'cards' in request.data:
        wanted = [_uuid(u) for u in request.data.get('cards') or []]
        if not wanted or None in wanted:
            return Response({'error': 'bad_cards'}, status=400)
        cards = cards.filter(uuid__in=wanted)

    with transaction.atomic():
        if target_value == 'new':
            target = take_into_own_copy(request.user, source)
        added, skipped = copy_cards(request.user, cards, source, target)
    return Response({'added': added, 'skipped': skipped, 'collection': str(target.uuid) if target else None})


# ------------------------------------------------------------------- sync

class _Push:
    """Applies one sync request's pushed changes; collects rejections and
    the uuids it touched (always echoed back, so the device ends up with
    the server's version even when the server's copy won the conflict)."""

    def __init__(self, user):
        self.user = user
        self.rejected = []
        self.touched_collections = set()
        self.touched_cards = set()
        self.tombstoned = {
            (kind, u) for kind, u in Tombstone.objects.filter(user_id=user.id).values_list('kind', 'uuid')
        }

    def reject(self, kind, item_uuid, reason):
        self.rejected.append({'kind': kind, 'uuid': str(item_uuid) if item_uuid else None, 'reason': reason})

    # -- collections: last write wins on updated_at
    def collection(self, item):
        cu = _uuid(item.get('uuid'))
        updated_at = _datetime(item.get('updated_at'))
        name = (item.get('name') or '').strip()
        description = item.get('description') or ''
        visibility = item.get('visibility', Collection.VISIBILITY_PRIVATE)
        tags = item.get('tags', [])
        if not isinstance(tags, list) or len(tags) > MAX_TAGS or not all(isinstance(t, str) and 0 < len(t.strip()) <= 30 for t in tags):
            return self.reject('collection', cu, 'invalid')
        tags = [t.strip() for t in tags]
        if cu is None or updated_at is None:
            return self.reject('collection', cu, 'invalid')
        if not name or len(name) > MAX_COLLECTION_NAME or len(description) > MAX_DESCRIPTION or visibility not in VISIBILITIES:
            return self.reject('collection', cu, 'invalid')
        if (Tombstone.KIND_COLLECTION, cu) in self.tombstoned:
            return self.reject('collection', cu, 'deleted')

        existing = Collection.objects.filter(uuid=cu).first()
        if existing is None:
            Collection.objects.create(owner=self.user, uuid=cu, name=name, description=description, visibility=visibility, tags=tags)
        elif existing.owner_id != self.user.id:
            return self.reject('collection', cu, 'not_owner')
        elif updated_at > existing.updated_at:
            existing.name, existing.description, existing.visibility, existing.tags = name, description, visibility, tags
            existing.save()
        self.touched_collections.add(cu)

    # -- cards: content (question/answer/collection) only, last write wins on
    #    content_updated_at. Stage is never pushed: it follows from reviews.
    def card(self, item):
        cu = _uuid(item.get('uuid'))
        changed_at = _datetime(item.get('content_updated_at'))
        question = (item.get('question') or '').strip() if isinstance(item.get('question'), str) else ''
        answer = (item.get('answer') or '').strip() if isinstance(item.get('answer'), str) else ''
        if cu is None or changed_at is None or not question or not answer:
            return self.reject('card', cu, 'invalid')
        if (Tombstone.KIND_CARD, cu) in self.tombstoned:
            return self.reject('card', cu, 'deleted')

        collection = None
        if item.get('collection'):
            col_uuid = _uuid(item['collection'])
            collection = Collection.objects.filter(owner=self.user, uuid=col_uuid).first()
            if collection is None and (Tombstone.KIND_COLLECTION, col_uuid) not in self.tombstoned:
                return self.reject('card', cu, 'unknown_collection')

        existing = Card.objects.filter(uuid=cu).first()
        if existing is None:
            # New cards made on the device: in the blitz unless they are a copy
            # into a topic (in_pool: false), due right away.
            Card.objects.create(
                user=self.user, uuid=cu, question=question, answer=answer,
                collection=collection, content_updated_at=changed_at,
                in_pool=item.get('in_pool', True) is not False,
            )
        elif existing.user_id != self.user.id:
            return self.reject('card', cu, 'not_owner')
        elif changed_at > existing.content_updated_at:
            existing.question, existing.answer, existing.collection = question, answer, collection
            existing.content_updated_at = changed_at
            existing.save()
        self.touched_cards.add(cu)

    def review(self, item):
        eu = _uuid(item.get('uuid'))
        reviewed_at = _datetime(item.get('reviewed_at'))
        correct = item.get('correct')
        if eu is None or reviewed_at is None or not isinstance(correct, bool):
            return self.reject('review', eu, 'invalid')
        card = Card.objects.filter(user=self.user, uuid=_uuid(item.get('card'))).first()
        if card is None:
            # Card deleted meanwhile (or never synced): drop the event.
            return self.reject('review', eu, 'unknown_card')
        apply_review(card, correct, reviewed_at=reviewed_at, event_uuid=eu)
        self.touched_cards.add(card.uuid)

    def pool(self, item):
        """{uuid, card, action: 'reset'|'remove', at}: blitz membership change."""
        eu, at, action = _uuid(item.get('uuid')), _datetime(item.get('at')), item.get('action')
        if eu is None or at is None or action not in (PoolEvent.ACTION_RESET, PoolEvent.ACTION_REMOVE):
            return self.reject('pool', eu, 'invalid')
        card = Card.objects.filter(user=self.user, uuid=_uuid(item.get('card'))).first()
        if card is None:
            return self.reject('pool', eu, 'unknown_card')
        if PoolEvent.objects.filter(uuid=eu).exists():
            return
        at = min(at, timezone.now())
        PoolEvent.objects.create(uuid=eu, user=self.user, card=card, action=action, at=at)
        if action == PoolEvent.ACTION_RESET:
            reset_into_pool(card, at)
        else:
            remove_from_pool(card)
        self.touched_cards.add(card.uuid)

    def delete(self, item):
        kind, du = item.get('kind'), _uuid(item.get('uuid'))
        if kind == Tombstone.KIND_CARD:
            Card.objects.filter(user=self.user, uuid=du).delete()
        elif kind == Tombstone.KIND_COLLECTION:
            Collection.objects.filter(owner=self.user, uuid=du).delete()
        elif kind == Tombstone.KIND_TOPIC_RUN:
            TopicRun.objects.filter(user=self.user, collection__uuid=du).delete()
        else:
            self.reject('delete', du, 'invalid')

    # -- topic runs: one per (user, collection), last write wins on updated_at
    def topic_run(self, item):
        collection = Collection.objects.filter(
            Q(owner=self.user) | Q(subscriptions__user=self.user), uuid=_uuid(item.get('collection')),
        ).distinct().first()
        updated_at = _datetime(item.get('updated_at'))
        if collection is None or updated_at is None:
            return self.reject('topic_run', _uuid(item.get('collection')), 'invalid')
        try:
            fields = {
                'round': max(1, int(item.get('round', 1))),
                'round_total': max(0, int(item.get('round_total', 0))),
                'correct_count': max(0, int(item.get('correct_count', 0))),
            }
        except (TypeError, ValueError):
            return self.reject('topic_run', collection.uuid, 'invalid')
        pk_by_uuid = dict(collection.cards.values_list('uuid', 'pk'))
        fields['queue'] = [pk_by_uuid[u] for u in map(_uuid, item.get('queue') or []) if u in pk_by_uuid]
        fields['wrong'] = [pk_by_uuid[u] for u in map(_uuid, item.get('wrong') or []) if u in pk_by_uuid]

        run = TopicRun.objects.filter(user=self.user, collection=collection).first()
        if run is None:
            TopicRun.objects.create(user=self.user, collection=collection, **fields)
        elif updated_at > run.updated_at:
            for key, value in fields.items():
                setattr(run, key, value)
            run.save()


def _added_topics(user):
    topics = (
        Collection.objects.filter(subscriptions__user=user, visibility__in=VIEWABLE_BY_OTHERS)
        .select_related('owner__profile').prefetch_related('cards')
    )
    return [
        {
            'uuid': str(c.uuid), 'share_token': str(c.share_token), 'name': c.name,
            'description': c.description, 'tags': c.tags, 'owner': get_display_name(c.owner),
            'cards': [{'uuid': str(k.uuid), 'question': k.question, 'answer': k.answer}
                      for k in sorted(c.cards.all(), key=lambda k: k.created_at)],
        }
        for c in topics
    ]


@api_view(['POST'])
def sync(request):
    """Push local changes and pull server changes in one call.

    Request (every list optional):
      since        ISO time from the previous sync's `server_time`; omit/null
                   for a first, full download
      collections  [{uuid, name, description, visibility, updated_at}]
      cards        [{uuid, question, answer, collection, content_updated_at, in_pool?}]
                   (in_pool only matters when the card is created)
      collections also take `tags` (list of strings)
      reviews      [{uuid, card, correct, reviewed_at}]   -- each grading done
                   on the device; applied in time order, idempotent by uuid
      pool         [{uuid, card, action: reset|remove, at}] -- blitz membership
                   changes (reset = into the blitz from scratch); applied in
                   time order together with reviews, idempotent by uuid
      deleted      [{kind: card|collection|topic_run, uuid}]  (topic_run: uuid
                   of its collection = "reset this run")
      topic_runs   [{collection, round, queue, wrong, round_total,
                     correct_count, updated_at}]  (queue/wrong: card uuids)

    Response:
      server_time  store it and send it as `since` next time
      collections, cards, topic_runs   everything changed since `since`
                   (plus everything pushed in this call), in full
      added_topics the user's added (subscribed) topics with their cards, always
                   in full: [{uuid, share_token, name, description, tags, owner, cards}]
      deleted      [{kind, uuid}] deleted since `since`; when a collection is
                   deleted its cards stay and lose their collection
      rejected     [{kind, uuid, reason}] pushed items not applied
    All times are ISO 8601 with an offset. On a conflict the later edit wins;
    progress never conflicts because it's rebuilt from review events.
    """
    since = None
    if request.data.get('since'):
        since = _datetime(request.data['since'])
        if since is None:
            return Response({'error': 'bad_since'}, status=400)
    for key in ('collections', 'cards', 'reviews', 'pool', 'deleted', 'topic_runs'):
        if not isinstance(request.data.get(key, []), list):
            return Response({'error': f'bad_{key}'}, status=400)

    user = request.user
    server_time = timezone.now()
    push = _Push(user)
    with transaction.atomic():
        for item in request.data.get('collections', []):
            push.collection(item if isinstance(item, dict) else {})
        for item in request.data.get('cards', []):
            push.card(item if isinstance(item, dict) else {})
        epoch = datetime.min.replace(tzinfo=dt_timezone.utc)
        events = [(_datetime(r.get('reviewed_at')) or epoch, 0, r) for r in request.data.get('reviews', []) if isinstance(r, dict)]
        events += [(_datetime(p.get('at')) or epoch, 1, p) for p in request.data.get('pool', []) if isinstance(p, dict)]
        for _, kind, item in sorted(events, key=lambda e: (e[0], e[1])):
            push.pool(item) if kind else push.review(item)
        for item in request.data.get('deleted', []):
            push.delete(item if isinstance(item, dict) else {})
        for item in request.data.get('topic_runs', []):
            push.topic_run(item if isinstance(item, dict) else {})

    collections = Collection.objects.filter(owner=user)
    cards = Card.objects.filter(user=user).select_related('collection', 'source_collection')
    runs = TopicRun.objects.filter(user=user).select_related('collection')
    tombstones = Tombstone.objects.filter(user_id=user.id)
    if since is not None:
        collections = collections.filter(Q(updated_at__gt=since) | Q(uuid__in=push.touched_collections))
        cards = cards.filter(Q(updated_at__gt=since) | Q(uuid__in=push.touched_cards))
        runs = runs.filter(updated_at__gt=since)
        tombstones = tombstones.filter(deleted_at__gt=since)
    else:
        tombstones = tombstones.none()

    runs = list(runs)
    run_pks = {pk for r in runs for pk in r.queue + r.wrong}
    uuid_by_pk = {pk: str(u) for pk, u in Card.objects.filter(pk__in=run_pks).values_list('pk', 'uuid')}

    # The same uuid can be tombstoned and later re-pushed as invalid; only
    # report each deletion once.
    deleted = {(t.kind, str(t.uuid)) for t in tombstones}
    return Response({
        'server_time': _iso(server_time),
        'collections': [_collection_json(c) for c in collections],
        'cards': [_card_json(c) for c in cards],
        'topic_runs': [_run_json(r, uuid_by_pk) for r in runs],
        'added_topics': _added_topics(user),
        'deleted': [{'kind': k, 'uuid': u} for k, u in sorted(deleted)],
        'rejected': push.rejected,
    })
