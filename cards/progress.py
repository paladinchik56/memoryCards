"""User-level learning progress and the "level" shown on the friends screen.

Kept separate from views.py so both `cards` views and the `accounts` friends
views can compute the same numbers for a user without importing each
other's view modules.
"""
from .models import Card
from .scheduler import MAX_STAGE

# How many fully-learned cards it takes to gain one level. A brand new user
# (0 learned cards) is level 1; mastering LEVEL_SIZE cards bumps them to
# level 2, another LEVEL_SIZE to level 3, and so on. This is deliberately a
# simple, transparent rule rather than a separate XP/points system, since a
# card's "stage" ladder (see scheduler.py) is already the app's one source
# of truth for how well something is learned.
LEVEL_SIZE = 5


def get_learned_count(user) -> int:
    """Number of this user's cards that reached the last stage of the ladder."""
    return Card.objects.filter(user=user, stage__gte=MAX_STAGE).count()


def get_user_level(user) -> int:
    """This user's level, derived from how many cards they have mastered."""
    return get_learned_count(user) // LEVEL_SIZE + 1


def get_user_progress(user) -> dict:
    """Summary of a user's learning progress: level plus the raw counts.

    Used both for a user's own stats and, for the friends feature, to show
    a friend's progress without exposing their actual card contents.
    """
    total_cards = Card.objects.filter(user=user).count()
    learned_count = get_learned_count(user)
    return {
        'level': get_user_level(user),
        'learned_count': learned_count,
        'total_cards': total_cards,
        'learned_pct': round(learned_count / total_cards * 100) if total_cards else 0,
    }