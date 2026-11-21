from django.conf import settings
from django.db import models
from django.utils import timezone
import uuid


class Collection(models.Model):
    """A named group of cards, owned by one user, optionally shared with others.

          `visibility` controls who can see it: PRIVATE — only the owner;
          UNLISTED — anyone with the direct link (via `share_token`); PUBLIC —
          listed for everyone in the shared library.
          """

    VISIBILITY_PRIVATE = 'private'
    VISIBILITY_UNLISTED = 'unlisted'
    VISIBILITY_PUBLIC = 'public'
    VISIBILITY_CHOICES = [
    (VISIBILITY_PRIVATE, 'Private'),
    (VISIBILITY_UNLISTED, 'Unlisted (by link)'),
    (VISIBILITY_PUBLIC, 'Public'),
      ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='collections')
    name = models.CharField(max_length=100)
    description = models.TextField(max_length=700, blank=True)
    # Free-form labels used by the library search, e.g. ["physics", "formulas"].
    tags = models.JSONField(default=list, blank=True)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default=VISIBILITY_PRIVATE)
    share_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    # Stable id shared with the mobile app (which creates rows offline, so it
    # can't wait for the server's integer pk). Never exposed as a share link.
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Card(models.Model):
    """Current state of one card. Always exactly one row per card."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cards')
    question = models.TextField()
    answer = models.TextField()
    # Whether the card is in the user's blitz (the set of cards being learned).
    # A card can sit in a topic without being in the blitz.
    in_pool = models.BooleanField(default=True)
    stage = models.PositiveSmallIntegerField(default=0)
    # Correct answers collected on the current stage (see scheduler.py).
    correct_count = models.PositiveSmallIntegerField(default=0)
    is_reviewed = models.BooleanField(default=False)
    next_review_at = models.DateTimeField(default=timezone.now)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Bumped on every save, including every review -- the sync "changed
    # since" cursor. Question/answer/collection edits also set
    # content_updated_at, so an offline edit is compared (last write wins)
    # against the last *content* change, not against the last review.
    updated_at = models.DateTimeField(auto_now=True)
    content_updated_at = models.DateTimeField(default=timezone.now)
    collection = models.ForeignKey(
    Collection, on_delete=models.SET_NULL, null=True, blank=True, related_name='cards',
    )
    source_collection = models.ForeignKey(
    Collection, on_delete = models.SET_NULL, null=True, blank=True, related_name='+',
    )
    # For a copy of someone else's card added to the blitz (decision 15, "A'"):
    # the original, so adding it again is recognised as "already in blitz".
    source_card = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )

    class Meta:
        # No unique question per user: copying a card into another topic makes
        # an independent card with the same text (decision 3). Adding a new
        # card by hand still warns about duplicates (forms / the app).
        ordering = ['next_review_at']

    def __str__(self):
        return self.question[:50]


class ReviewLog(models.Model):
    """Append-only log: one row per grading event on a card.

    Stores the card's state both before and after the event — needed so the
    "previous card" undo feature can roll a card back to its state before
    the last grade, without ever touching or deleting log rows themselves.
    """

    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='review_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='review_logs')
    was_correct = models.BooleanField()
    previous_stage = models.PositiveSmallIntegerField()
    new_stage = models.PositiveSmallIntegerField()
    previous_correct_count = models.PositiveSmallIntegerField(default=0)
    new_correct_count = models.PositiveSmallIntegerField(default=0)
    previous_is_reviewed = models.BooleanField()
    previous_next_review_at = models.DateTimeField(null=True, blank=True)
    new_next_review_at = models.DateTimeField()
    # Settable (not auto_now_add): reviews done offline on the phone keep
    # the time they actually happened.
    reviewed_at = models.DateTimeField(default=timezone.now, db_index=True)
    # Client-generated event id: pushing the same review twice is a no-op.
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        ordering = ['-reviewed_at']


    def __str__(self):
        return f'{self.card_id} @ {self.reviewed_at}: {"correct" if self.was_correct else "incorrect"}'



class TopicRun(models.Model):
    """A "go through the whole topic" pass, separate from spaced repetition.

    Never touches Card.stage/next_review_at and isn't time-based: the first
    round queues every card of the topic; each next round queues only the
    cards answered wrong in the previous one, until nothing is left. Kept in
    the DB (one row per user+topic) so it survives logout and other devices,
    and several topics can be in progress at once. Reset = delete the row.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='topic_runs')
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='runs')
    round = models.PositiveSmallIntegerField(default=1)
    queue = models.JSONField(default=list)        # card ids still to show this round, in order
    wrong = models.JSONField(default=list)        # card ids missed this round -> next round
    round_total = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)  # correct answers this round
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'collection'], name='unique_topic_run_per_user'),
        ]

    @property
    def round_finished(self):
        return not self.queue

    @property
    def completed(self):
        """Whole run done: the last round had no mistakes."""
        return not self.queue and not self.wrong

    def __str__(self):
        return f'{self.user} / {self.collection} round {self.round}'


class Tombstone(models.Model):
    """Record that a card/collection was deleted, so devices that synced it
    earlier learn to delete their local copy (see api sync)."""

    KIND_CARD = 'card'
    KIND_COLLECTION = 'collection'
    KIND_TOPIC_RUN = 'topic_run'  # uuid = the run's collection uuid

    # Plain id, not a FK: tombstones are also written while a whole user is
    # being deleted (cascade), when a FK to that user would fail.
    user_id = models.IntegerField(db_index=True)
    kind = models.CharField(max_length=10, choices=[(KIND_CARD, 'Card'), (KIND_COLLECTION, 'Collection'), (KIND_TOPIC_RUN, 'Topic run')])
    uuid = models.UUIDField()
    deleted_at = models.DateTimeField(default=timezone.now, db_index=True)


class TopicSubscription(models.Model):
    """Someone else's topic the user "added to themselves": read-only, always
    the author's current version (decision 2)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='subscriptions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'collection'], name='unique_subscription')]


class PoolEvent(models.Model):
    """A change of a card's blitz membership pushed by a device: 'reset'
    (put into the blitz from scratch / reset progress) or 'remove' (take out
    of the blitz). Kept so a re-sent event is applied only once."""

    ACTION_RESET = 'reset'
    ACTION_REMOVE = 'remove'

    uuid = models.UUIDField(unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='pool_events')
    action = models.CharField(max_length=10, choices=[(ACTION_RESET, 'Reset'), (ACTION_REMOVE, 'Remove')])
    at = models.DateTimeField()
