from datetime import timedelta

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .models import Card
from .progress import LEVEL_SIZE, get_learned_count, get_user_level, get_user_progress
from .scheduler import (
    MAX_STAGE,
    STAGE_INTERVALS,
    STAGE_INTERVALS_TEST,
    next_stage,
    schedule_next_review,
)


class NextStageTests(SimpleTestCase):
    def test_correct_answer_advances_one_stage(self):
        self.assertEqual(next_stage(0, correct=True), 1)
        self.assertEqual(next_stage(3, correct=True), 4)

    def test_incorrect_answer_moves_back_one_stage(self):
        self.assertEqual(next_stage(5, correct=False), 4)
        self.assertEqual(next_stage(2, correct=False), 1)

    def test_incorrect_answer_does_not_reset_to_start(self):
        # At a high stage, an incorrect answer should only move the card
        # back by one stage, not reset it all the way to the beginning.
        new_stage = next_stage(4, correct=False)
        self.assertEqual(new_stage, 3)
        self.assertNotEqual(new_stage, 0)

    def test_stage_cannot_exceed_max(self):
        self.assertEqual(next_stage(MAX_STAGE, correct=True), MAX_STAGE)

    def test_stage_cannot_go_below_zero(self):
        self.assertEqual(next_stage(0, correct=False), 0)


class ScheduleNextReviewTests(SimpleTestCase):
    def test_uses_real_intervals_by_default(self):
        now = timezone.now()
        new_stage, next_at = schedule_next_review(0, correct=True, now=now)
        self.assertEqual(new_stage, 1)
        self.assertEqual(next_at, now + STAGE_INTERVALS[1])

    def test_can_use_shortened_test_intervals(self):
        now = timezone.now()
        new_stage, next_at = schedule_next_review(
            0, correct=True, now=now, intervals=STAGE_INTERVALS_TEST,
        )
        self.assertEqual(new_stage, 1)
        self.assertEqual(next_at, now + timedelta(seconds=2))

    def test_full_cycle_with_a_mistake_using_test_intervals(self):
        """Walk the whole ladder on compressed intervals with one mistake."""
        now = timezone.now()
        stage = 0

        # 4 correct answers in a row: 0 -> 1 -> 2 -> 3 -> 4
        for _ in range(4):
            stage, now = schedule_next_review(
                stage, correct=True, now=now, intervals=STAGE_INTERVALS_TEST,
            )
        self.assertEqual(stage, 4)

        # a mistake at stage 4 moves back to the last interval (3), not to 0
        stage, now = schedule_next_review(
            stage, correct=False, now=now, intervals=STAGE_INTERVALS_TEST,
        )
        self.assertEqual(stage, 3)

        # correct answers again should reach the end of the ladder
        for _ in range(20):
            stage, now = schedule_next_review(
                stage, correct=True, now=now, intervals=STAGE_INTERVALS_TEST,
            )
        self.assertEqual(stage, len(STAGE_INTERVALS_TEST) - 1)

    def test_fixed_interval_overrides_stage_interval_but_not_stage_progression(self):
        now = timezone.now()

        new_stage, next_at = schedule_next_review(
            0, correct=True, now=now, fixed_interval=timedelta(seconds=5),
        )
        self.assertEqual(new_stage, 1)
        self.assertEqual(next_at, now + timedelta(seconds=5))

        new_stage, next_at = schedule_next_review(
            3, correct=False, now=now, fixed_interval=timedelta(seconds=5),
        )
        self.assertEqual(new_stage, 2)
        self.assertEqual(next_at, now + timedelta(seconds=5))


class UserProgressTests(TestCase):
    """Tests for cards/progress.py -- the "level" shown on a user's own
    dashboard and on the friends screen."""

    def setUp(self):
        self.user = User.objects.create_user('learner', password='pw')

    def _add_card(self, stage, question='q'):
        return Card.objects.create(user=self.user, question=question, answer='a', stage=stage)

    def test_learned_count_is_zero_with_no_cards(self):
        self.assertEqual(get_learned_count(self.user), 0)

    def test_learned_count_only_counts_cards_at_max_stage(self):
        self._add_card(stage=MAX_STAGE, question='mastered')
        self._add_card(stage=MAX_STAGE - 1, question='almost')
        self._add_card(stage=0, question='fresh')
        self.assertEqual(get_learned_count(self.user), 1)

    def test_level_starts_at_one_with_no_learned_cards(self):
        self.assertEqual(get_user_level(self.user), 1)

    def test_level_increases_by_one_every_level_size_learned_cards(self):
        # Mastering fewer than LEVEL_SIZE cards should not yet bump the level.
        for i in range(LEVEL_SIZE - 1):
            self._add_card(stage=MAX_STAGE, question=f'q{i}')
        self.assertEqual(get_user_level(self.user), 1)

        # The LEVEL_SIZE-th mastered card crosses the threshold to level 2.
        self._add_card(stage=MAX_STAGE, question='the-one-that-tips-it')
        self.assertEqual(get_user_level(self.user), 2)

    def test_level_does_not_count_unmastered_cards(self):
        for i in range(LEVEL_SIZE):
            self._add_card(stage=MAX_STAGE - 1, question=f'q{i}')
        self.assertEqual(get_user_level(self.user), 1)

    def test_get_user_progress_reports_counts_and_percentage(self):
        self._add_card(stage=MAX_STAGE, question='mastered')
        self._add_card(stage=0, question='fresh')

        progress = get_user_progress(self.user)
        self.assertEqual(progress['level'], 1)
        self.assertEqual(progress['learned_count'], 1)
        self.assertEqual(progress['total_cards'], 2)
        self.assertEqual(progress['learned_pct'], 50)

    def test_get_user_progress_with_no_cards_has_zero_percent_not_a_crash(self):
        progress = get_user_progress(self.user)
        self.assertEqual(progress['total_cards'], 0)
        self.assertEqual(progress['learned_pct'], 0)
