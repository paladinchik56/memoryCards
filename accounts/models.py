from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import CheckConstraint, F, Q, UniqueConstraint

# Letters (any language), digits, underscore and hyphen; 3-30 characters.
# `\w` is unicode-aware in Python 3, so this also allows e.g. Cyrillic nicknames.
nickname_validator = RegexValidator(
    regex=r'^[\w-]{3,30}$',
    message='Никнейм: 3-30 символов, буквы/цифры/подчёркивание/дефис, без пробелов.',
)


class Profile(models.Model):
    """Extra per-user data that Django's built-in User model doesn't have.

    A separate one-to-one model (rather than a custom AUTH_USER_MODEL) so
    this can be bolted onto the existing `auth.User` table without a
    disruptive user-model swap. `nickname` is the public identity used for
    login and for display in the friends list — `User.username` still holds
    the account's email (see accounts/views.py:register) and stays purely
    internal/administrative.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    # unique=True is a DB-level backstop against exact duplicates; the
    # case-insensitive check that actually stops "Bob" vs "bob" happens in
    # EmailRegisterForm.clean_nickname (SQLite unique is byte-exact).
    nickname = models.CharField(max_length=30, unique=True, validators=[nickname_validator])
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nickname


def get_display_name(user) -> str:
    """The name to show for `user` in the UI: their nickname if they have a
    Profile, otherwise their username as a fallback.

    The fallback covers accounts that predate the nickname feature or were
    created outside the registration flow (e.g. `createsuperuser`). Django
    makes the missing-reverse-OneToOne exception a subclass of
    AttributeError specifically so getattr(..., default) works here.
    """
    profile = getattr(user, 'profile', None)
    return profile.nickname if profile is not None else user.username


class Friendship(models.Model):
    """A friend request/relationship between two users.

    One row covers both directions of the relationship: `from_user` is
    whoever sent the request, `to_user` is whoever received it, and once
    `status` is ACCEPTED both users consider each other friends. Storing a
    single row per pair (instead of two mirrored rows, one per direction)
    means there is nothing that can ever go out of sync between "my view of
    the friendship" and "their view of it".
    """

    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_DECLINED = 'declined'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_DECLINED, 'Declined'),
    ]

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='friendship_requests_sent',
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='friendship_requests_received',
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # At most one row per ordered (from_user, to_user) pair. The
            # opposite-direction pair is still a separate row as far as the
            # database is concerned — application code (see forms.py) is
            # what stops A->B and B->A from both existing at once.
            UniqueConstraint(fields=['from_user', 'to_user'], name='unique_friendship_pair'),
            # A user can never send a friend request to themselves.
            CheckConstraint(condition=~Q(from_user=F('to_user')), name='friendship_no_self_friend'),
        ]

    def __str__(self):
        return f'{self.from_user} -> {self.to_user} ({self.status})'

    @classmethod
    def are_friends(cls, user_a, user_b) -> bool:
        """Whether two users have an accepted friendship, in either direction."""
        return cls.objects.filter(
            Q(from_user=user_a, to_user=user_b) | Q(from_user=user_b, to_user=user_a),
            status=cls.STATUS_ACCEPTED,
        ).exists()

    @classmethod
    def friends_of(cls, user):
        """Queryset of User objects who are `user`'s accepted friends.

        Accepted friendships are symmetric, so this looks on both sides of
        the relationship: rows where `user` sent the original request and
        rows where `user` received it.
        """
        sent_to = cls.objects.filter(from_user=user, status=cls.STATUS_ACCEPTED).values_list('to_user_id', flat=True)
        received_from = cls.objects.filter(to_user=user, status=cls.STATUS_ACCEPTED).values_list('from_user_id', flat=True)
        User = get_user_model()
        return User.objects.filter(Q(pk__in=sent_to) | Q(pk__in=received_from))

    @classmethod
    def pending_received_by(cls, user):
        """Queryset of pending Friendship requests waiting on `user` to answer."""
        return cls.objects.filter(to_user=user, status=cls.STATUS_PENDING).select_related('from_user__profile')

    @classmethod
    def pending_sent_by(cls, user):
        """Queryset of pending Friendship requests `user` is waiting on a reply to."""
        return cls.objects.filter(from_user=user, status=cls.STATUS_PENDING).select_related('to_user__profile')