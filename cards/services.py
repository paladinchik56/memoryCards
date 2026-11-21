"""Card operations shared by the website views and the mobile API, so both
apply exactly the same rules."""
from django.utils import timezone

from .models import Card, Collection, ReviewLog
from .scheduler import schedule_next_review


def apply_review(card, correct, reviewed_at=None, event_uuid=None, fixed_interval=None):
    """Grade `card` once with the scheduler (scheduler.py) and append a
    ReviewLog row.

    `reviewed_at` lets an offline review from the phone keep the time it
    happened; the next review is scheduled from that moment. If the card has
    already been reviewed *later* than that elsewhere (web while the phone
    was offline), the answer still counts but the due date never goes
    backwards. `event_uuid` makes a pushed review idempotent: the same
    event sent twice is applied once. Returns the new ReviewLog, or None if
    the event was already applied.
    """
    now = timezone.now()
    reviewed_at = min(reviewed_at or now, now)  # a fast phone clock can't push reviews into the future
    if event_uuid is not None and ReviewLog.objects.filter(uuid=event_uuid).exists():
        return None

    previous_stage = card.stage
    previous_correct_count = card.correct_count
    previous_is_reviewed = card.is_reviewed
    previous_next_review_at = card.next_review_at if previous_is_reviewed else None

    new_stage, new_count, next_at = schedule_next_review(
        card.stage, card.correct_count, correct, now=reviewed_at, fixed_interval=fixed_interval,
    )
    reviewed_later = ReviewLog.objects.filter(card=card, reviewed_at__gt=reviewed_at).exists()
    if reviewed_later and card.next_review_at > next_at:
        next_at = card.next_review_at

    extra = {'uuid': event_uuid} if event_uuid is not None else {}
    log = ReviewLog.objects.create(
        card=card,
        user=card.user,
        was_correct=correct,
        previous_stage=previous_stage,
        new_stage=new_stage,
        previous_correct_count=previous_correct_count,
        new_correct_count=new_count,
        previous_is_reviewed=previous_is_reviewed,
        previous_next_review_at=previous_next_review_at,
        new_next_review_at=next_at,
        reviewed_at=reviewed_at,
        **extra,
    )
    card.stage = new_stage
    card.correct_count = new_count
    card.next_review_at = next_at
    card.is_reviewed = True
    card.save(update_fields=['stage', 'correct_count', 'next_review_at', 'is_reviewed', 'updated_at'])
    return log


def copy_cards(user, source_cards, source_collection, target_collection):
    """Copy `source_cards` into `user`'s own cards (new rows, stage 0),
    skipping questions the user already has. Returns (added, skipped)."""
    existing = set(Card.objects.filter(user=user).values_list('question', flat=True))
    new_cards, seen = [], set()
    source_cards = list(source_cards)
    for card in source_cards:
        if card.question in existing or card.question in seen:
            continue
        seen.add(card.question)
        new_cards.append(Card(
            user=user, question=card.question, answer=card.answer,
            collection=target_collection, source_collection=source_collection,
        ))
    Card.objects.bulk_create(new_cards)
    return len(new_cards), len(source_cards) - len(new_cards)


def take_into_own_copy(user, source):
    """Where "add the whole collection as my own" lands: the user's
    collection that already holds earlier copies from `source` if there is
    one (so taking again only adds new cards), otherwise a new private
    collection named after it."""
    earlier = (
        Card.objects.filter(user=user, source_collection=source, collection__owner=user)
        .values_list('collection_id', flat=True).first()
    )
    if earlier:
        return Collection.objects.get(pk=earlier)
    return Collection.objects.create(owner=user, name=source.name, description=source.description)


def reset_into_pool(card, at=None):
    """Put `card` into the blitz from scratch (or reset its progress there)."""
    card.in_pool = True
    card.stage = 0
    card.correct_count = 0
    card.is_reviewed = False
    card.next_review_at = at or timezone.now()
    card.save(update_fields=['in_pool', 'stage', 'correct_count', 'is_reviewed', 'next_review_at', 'updated_at'])


def remove_from_pool(card):
    card.in_pool = False
    card.save(update_fields=['in_pool', 'updated_at'])


def add_foreign_to_pool(user, source_cards, reset_uuids=()):
    """Decision 15 ("A'"): someone else's card enters the user's blitz as a
    personal copy linked to the original. Returns (added, reset, skipped).

    Already in the blitz -> skipped, or progress reset if its original's uuid
    is in `reset_uuids`. A copy that was taken out of the blitz comes back
    from scratch. The user's own cards are handled the same way, in place.
    """
    added = reset = skipped = 0
    reset_uuids = set(reset_uuids)
    for src in source_cards:
        if src.user_id == user.id:
            mine = src
        else:
            mine = Card.objects.filter(user=user, source_card=src).first()
        if mine is None:
            Card.objects.create(
                user=user, question=src.question, answer=src.answer, collection=None,
                source_collection=src.collection, source_card=src, in_pool=True,
            )
            added += 1
        elif not mine.in_pool:
            reset_into_pool(mine)
            added += 1
        elif src.uuid in reset_uuids:
            reset_into_pool(mine)
            reset += 1
        else:
            skipped += 1
    return added, reset, skipped


def copy_into_topic(user, source_cards, target):
    """Independent copies in one of the user's own topics, not in the blitz."""
    copies = [
        Card(user=user, question=c.question, answer=c.answer, collection=target,
             source_collection=c.collection, in_pool=False)
        for c in source_cards
    ]
    Card.objects.bulk_create(copies)
    return len(copies)
