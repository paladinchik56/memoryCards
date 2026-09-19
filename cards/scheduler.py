"""Spaced-repetition interval scheduler.

A card moves along a fixed ladder of intervals. A correct answer moves the
card one stage forward; an incorrect answer moves it one stage back (not
all the way back to the start).
"""
from datetime import timedelta

from django.utils import timezone

# Stages in increasing order. The index in this list is the card's "stage".
STAGE_INTERVALS = [
    timedelta(seconds=90),   # 0: in 90 seconds
    timedelta(minutes=30),   # 1: in 30 minutes
    timedelta(hours=12),     # 2: in 12 hours
    timedelta(days=2),       # 3: in 2 days
    timedelta(weeks=2),      # 4: in 2 weeks
    timedelta(days=60),      # 5: in 2 months
]

# Same ladder, with compressed intervals — lets you run through the whole
# cycle manually or in tests in seconds instead of months.
STAGE_INTERVALS_TEST = [
    timedelta(seconds=1),
    timedelta(seconds=2),
    timedelta(seconds=3),
    timedelta(seconds=4),
    timedelta(seconds=5),
    timedelta(seconds=6),
]

STAGE_LABELS = [
    '90 секунд',
    '30 минут',
    '12 часов',
    '2 дня',
    '2 недели',
    '2 месяца',
]

MAX_STAGE = len(STAGE_INTERVALS) - 1

# Fixed delay used when browser-side test mode is on: every card comes back
# after this interval, regardless of stage or correctness.
TEST_MODE_INTERVAL = timedelta(seconds=5)


def next_stage(current_stage: int, correct: bool, max_stage: int = MAX_STAGE) -> int:
    """Return the index of the next stage.

    On a correct answer, moves one stage forward (capped at max_stage).
    On an incorrect answer, moves one stage back to the last completed
    interval (floored at 0) — never resets straight to the start.
    """
    if correct:
        return min(current_stage + 1, max_stage)
    return max(current_stage - 1, 0)


def schedule_next_review(current_stage: int, correct: bool, now=None, intervals=STAGE_INTERVALS, fixed_interval=None):
    """Compute the new stage and the timestamp of the next review.

    The stage still advances/retreats normally; `fixed_interval`, when given,
    overrides only the wait time (used by test mode's constant 5s delay).

    Returns (new_stage, next_review_at).
    """
    now = now or timezone.now()
    new_stage = next_stage(current_stage, correct, max_stage=len(intervals) - 1)
    interval = intervals[new_stage] if fixed_interval is None else fixed_interval
    return new_stage, now + interval
