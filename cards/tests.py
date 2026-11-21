from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Card, Collection, ReviewLog, TopicRun
from .progress import LEVEL_SIZE, get_learned_count, get_user_level, get_user_progress
from . import blitz
from .scheduler import (
    MAX_STAGE,
    REQUIRED_CORRECT,
    STAGE_INTERVALS,
    STAGE_INTERVALS_TEST,
    next_state,
    schedule_next_review,
)


class NextStateTests(SimpleTestCase):
    """The rules from description/open-decisions.md #16-17."""

    def test_correct_answers_collect_until_the_stage_requirement(self):
        self.assertEqual(next_state(0, 0, True), (0, 1))
        self.assertEqual(next_state(0, 1, True), (0, 2))
        self.assertEqual(next_state(0, 2, True), (1, 0))  # 3 needed on short stages

    def test_long_stages_need_two(self):
        self.assertEqual(next_state(3, 0, True), (3, 1))
        self.assertEqual(next_state(3, 1, True), (4, 0))
        self.assertEqual(REQUIRED_CORRECT, [3, 3, 3, 2, 2, 2])

    def test_wrong_answer_changes_nothing(self):
        for stage, count in [(0, 0), (2, 2), (5, 1), (MAX_STAGE, 0)]:
            self.assertEqual(next_state(stage, count, False), (stage, count))

    def test_max_stage_is_sticky(self):
        self.assertEqual(next_state(MAX_STAGE, 0, True), (MAX_STAGE, 0))

    def test_ladder(self):
        self.assertEqual(
            [int(i.total_seconds()) for i in STAGE_INTERVALS],
            [90, 1800, 43200, 172800, 604800, 1209600, 2592000],
        )


class ScheduleNextReviewTests(SimpleTestCase):
    def test_correct_answer_waits_the_interval_of_the_resulting_stage(self):
        now = timezone.now()
        self.assertEqual(schedule_next_review(0, 0, True, now=now), (0, 1, now + STAGE_INTERVALS[0]))
        self.assertEqual(schedule_next_review(0, 2, True, now=now), (1, 0, now + STAGE_INTERVALS[1]))

    def test_wrong_answer_is_due_right_away(self):
        now = timezone.now()
        self.assertEqual(schedule_next_review(6, 0, False, now=now), (6, 0, now))

    def test_fixed_interval_only_overrides_the_wait(self):
        now = timezone.now()
        stage, count, at = schedule_next_review(1, 2, True, now=now, fixed_interval=timedelta(seconds=5))
        self.assertEqual((stage, count, at), (2, 0, now + timedelta(seconds=5)))

    def test_full_ladder_takes_the_expected_number_of_answers(self):
        now = timezone.now()
        stage, count, answers = 0, 0, 0
        while stage < MAX_STAGE:
            stage, count, now = schedule_next_review(stage, count, True, now=now, intervals=STAGE_INTERVALS_TEST)
            answers += 1
            if answers % 4 == 0:  # mistakes along the way change nothing
                stage, count, now = schedule_next_review(stage, count, False, now=now, intervals=STAGE_INTERVALS_TEST)
        self.assertEqual(answers, sum(REQUIRED_CORRECT))


class BlitzOrderTests(SimpleTestCase):
    """cards/blitz.py: random, overdue first, comeback after 5-6 cards."""

    class C:
        def __init__(self, pk, stage=0, late=timedelta(0)):
            self.pk, self.stage = pk, stage
            self.next_review_at = timezone.now() - late

    def test_badly_overdue_cards_go_first(self):
        import random as r
        now = timezone.now()
        fresh = [self.C(i, stage=6, late=timedelta(hours=1)) for i in range(10)]
        overdue = self.C(99, stage=1, late=timedelta(hours=1))  # 2 intervals late
        for seed in range(20):
            pick = blitz.choose_next(fresh + [overdue], now, blitz.new_state(), rng=r.Random(seed))
            self.assertEqual(pick.pk, 99)

    def test_order_is_random_among_equals(self):
        import random as r
        now = timezone.now()
        cards = [self.C(i) for i in range(20)]
        picks = {blitz.choose_next(cards, now, blitz.new_state(), rng=r.Random(s)).pk for s in range(30)}
        self.assertGreater(len(picks), 5)

    def test_never_the_same_card_twice_in_a_row(self):
        now = timezone.now()
        cards = [self.C(1), self.C(2)]
        state = blitz.after_answer(blitz.new_state(), 1, True)
        for _ in range(10):
            self.assertEqual(blitz.choose_next(cards, now, state).pk, 2)

    def test_wrong_card_comes_back_after_five_or_six_others(self):
        import random as r
        rng = r.Random(1)
        now = timezone.now()
        cards = [self.C(i) for i in range(1, 20)]
        state = blitz.after_answer(blitz.new_state(), 1, False, rng=rng)
        gap = 0
        while True:
            card = blitz.choose_next(cards, now, state, rng=rng)
            if card.pk == 1:
                break
            gap += 1
            state = blitz.after_answer(state, card.pk, True, rng=rng)
        self.assertIn(gap, (5, 6))

    def test_wrong_card_comes_back_sooner_when_few_cards_left(self):
        now = timezone.now()
        cards = [self.C(1), self.C(2)]
        state = blitz.after_answer(blitz.new_state(), 1, False)
        self.assertEqual(blitz.choose_next(cards, now, state).pk, 2)
        state = blitz.after_answer(state, 2, True)
        self.assertEqual(blitz.choose_next(cards, now, state).pk, 1)


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


class SchedulerContractTests(SimpleTestCase):
    """cards/scheduler_vectors.json is what the mobile app is tested
    against; the server's scheduler must keep matching it."""

    def test_scheduler_matches_the_shared_vectors(self):
        import json
        from pathlib import Path
        vectors = json.loads((Path(__file__).parent / 'scheduler_vectors.json').read_text())
        self.assertEqual(vectors['intervals_seconds'], [int(i.total_seconds()) for i in STAGE_INTERVALS])
        self.assertEqual(vectors['required_correct'], REQUIRED_CORRECT)
        now = timezone.now()
        for case in vectors['cases']:
            stage, count, next_at = schedule_next_review(case['stage'], case['correct_count'], case['correct'], now=now)
            self.assertEqual((stage, count), (case['new_stage'], case['new_correct_count']), case)
            self.assertEqual((next_at - now).total_seconds(), case['wait_seconds'], case)


class SeedElectricalTests(TestCase):
    def test_seed_is_public_has_30_cards_and_is_idempotent(self):
        from django.core.management import call_command
        from accounts.models import Profile
        user = User.objects.create_user('a@example.com', password='pw')
        Profile.objects.create(user=user, nickname='admin')
        call_command('seed_electrical', stdout=open('/dev/null', 'w'))
        call_command('seed_electrical', stdout=open('/dev/null', 'w'))
        topic = Collection.objects.get(owner=user, name='Электротехника')
        self.assertEqual(topic.visibility, Collection.VISIBILITY_PUBLIC)
        self.assertEqual(topic.cards.count(), 30)


class ImportTopicTests(TestCase):
    def test_import_creates_then_updates_without_duplicates(self):
        import json
        import tempfile
        from django.core.management import call_command
        from accounts.models import Profile
        user = User.objects.create_user('a@example.com', password='pw')
        Profile.objects.create(user=user, nickname='admin')
        data = {'name': 'T', 'description': 'd', 'tags': ['x'], 'visibility': 'public',
                'cards': [{'q': 'q1', 'a': 'a1'}, {'q': 'q2', 'a': 'a2'}]}
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(data, f)
        call_command('import_topic', f.name, stdout=open('/dev/null', 'w'))
        data['cards'][0]['a'] = 'changed'
        data['cards'].append({'q': 'q3', 'a': 'a3'})
        with open(f.name, 'w', encoding='utf-8') as g:
            json.dump(data, g)
        call_command('import_topic', f.name, stdout=open('/dev/null', 'w'))
        topic = Collection.objects.get(owner=user, name='T')
        self.assertEqual((topic.visibility, topic.tags, topic.cards.count()), ('public', ['x'], 3))
        self.assertEqual(topic.cards.get(question='q1').answer, 'changed')
