"""Spaced-repetition scheduler.

A card in the blitz sits on a stage of a fixed ladder of intervals. Rules
(product decisions 16-17 in description/open-decisions.md):

- A correct answer adds one to the card's correct-answer count on its
  stage. Once the count reaches REQUIRED_CORRECT[stage], the card moves up
  one stage and the count starts again from zero. The next review is the
  interval of the stage the card is on after the answer.
- A wrong answer changes nothing about stage or count (no demotion, no
  reset); the card is due again immediately, so the study session shows it
  again a few cards later (see cards/blitz.py).
- On the last stage the card stays forever and comes back every
  STAGE_INTERVALS[MAX_STAGE].

cards/scheduler_vectors.json is the cross-platform contract for these rules;
the mobile app's TypeScript port is tested against the same file.
"""
from datetime import timedelta

from django.utils import timezone

# Stages in increasing order. The index in this list is the card's "stage".
STAGE_INTERVALS = [
    timedelta(seconds=90),   # 0
    timedelta(minutes=30),   # 1
    timedelta(hours=12),     # 2
    timedelta(days=2),       # 3
    timedelta(weeks=1),      # 4
    timedelta(weeks=2),      # 5
    timedelta(days=30),      # 6: max ("learned")
]

# Correct answers needed on each stage to move up from it. The last stage
# has no entry: there is nothing to move up to.
REQUIRED_CORRECT = [3, 3, 3, 2, 2, 2]

# Same ladder with compressed intervals -- lets you run through the whole
# cycle manually or in tests in seconds instead of months.
STAGE_INTERVALS_TEST = [timedelta(seconds=s) for s in range(1, len(STAGE_INTERVALS) + 1)]

STAGE_LABELS = [
    '90 seconds',
    '30 minutes',
    '12 hours',
    '2 days',
    '1 week',
    '2 weeks',
    '1 month',
]

MAX_STAGE = len(STAGE_INTERVALS) - 1
assert len(REQUIRED_CORRECT) == MAX_STAGE
assert len(STAGE_LABELS) == len(STAGE_INTERVALS)

# Fixed delay used when browser-side test mode is on: every correctly
# answered card comes back after this interval, regardless of stage.
TEST_MODE_INTERVAL = timedelta(seconds=5)


def next_state(stage: int, correct_count: int, correct: bool) -> tuple[int, int]:
    """Return (stage, correct_count) after one answer."""
    if not correct:
        return stage, correct_count
    if stage >= MAX_STAGE:
        return MAX_STAGE, 0
    correct_count += 1
    if correct_count >= REQUIRED_CORRECT[stage]:
        return stage + 1, 0
    return stage, correct_count


def schedule_next_review(stage: int, correct_count: int, correct: bool, now=None,
                         intervals=STAGE_INTERVALS, fixed_interval=None):
    """Apply one answer. Returns (new_stage, new_correct_count, next_review_at).

    A wrong answer makes the card due right away (`now`). `fixed_interval`
    (test mode) overrides only the wait after a correct answer.
    """
    now = now or timezone.now()
    new_stage, new_count = next_state(stage, correct_count, correct)
    if not correct:
        return new_stage, new_count, now
    interval = intervals[new_stage] if fixed_interval is None else fixed_interval
    return new_stage, new_count, now + interval
