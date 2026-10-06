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
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default=VISIBILITY_PRIVATE)
    share_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Card(models.Model):
    """Current state of one card. Always exactly one row per card."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cards')
    question = models.TextField()
    answer = models.TextField()
    stage = models.PositiveSmallIntegerField(default=0)
    is_reviewed = models.BooleanField(default=False)
    next_review_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    collection = models.ForeignKey(
    Collection, on_delete=models.SET_NULL, null=True, blank=True, related_name='cards',
    )
    source_collection = models.ForeignKey(
    Collection, on_delete = models.SET_NULL, null=True, blank=True, related_name='+',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'question'], name='unique_card_question_per_user'),
        ]
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
    previous_is_reviewed = models.BooleanField()
    previous_next_review_at = models.DateTimeField(null=True, blank=True)
    new_next_review_at = models.DateTimeField()
    reviewed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-reviewed_at']


    def __str__(self):
        return f'{self.card_id} @ {self.reviewed_at}: {"correct" if self.was_correct else "incorrect"}'

