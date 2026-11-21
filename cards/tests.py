from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Card, Collection, ReviewLog, TopicRun
from .progress import LEVEL_SIZE, get_learned_count, get_user_level, get_user_progress
from .quotes import QUOTES, get_quote_of_the_day
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


class CollectionViewTests(TestCase):
    """Tests for creating collections and viewing them as the owner."""

    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pw12345')
        self.client.login(username='alice', password='pw12345')

    def test_creating_a_collection_sets_the_owner_from_the_logged_in_user(self):
        response = self.client.post(reverse('cards:collections'), {
            'name': 'Spanish verbs', 'description': '', 'visibility': Collection.VISIBILITY_PRIVATE,
        })
        self.assertRedirects(response, reverse('cards:collections'))
        collection = Collection.objects.get(name='Spanish verbs')
        self.assertEqual(collection.owner, self.alice)

    def test_description_can_be_left_blank(self):
        response = self.client.post(reverse('cards:collections'), {
            'name': 'No description', 'description': '', 'visibility': Collection.VISIBILITY_PRIVATE,
        })
        self.assertRedirects(response, reverse('cards:collections'))
        self.assertTrue(Collection.objects.filter(name='No description').exists())

    def test_owner_can_open_their_own_collection_detail_page(self):
        collection = Collection.objects.create(owner=self.alice, name='Mine')
        response = self.client.get(reverse('cards:collection_detail', args=[collection.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mine')

    def test_non_owner_cannot_open_someone_elses_collection_detail_page(self):
        bob = User.objects.create_user('bob', password='pw12345')
        collection = Collection.objects.create(owner=bob, name="Bob's private notes")
        response = self.client.get(reverse('cards:collection_detail', args=[collection.pk]))
        self.assertEqual(response.status_code, 404)


class CollectionVisibilityTests(TestCase):
    """Tests for who can reach a collection through collection_view (the
    share-token-based URL) and through the public library listing."""

    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pw12345')
        self.bob = User.objects.create_user('bob', password='pw12345')
        self.client.login(username='bob', password='pw12345')

    def test_owner_can_always_view_their_own_collection_by_token(self):
        self.client.logout()
        self.client.login(username='alice', password='pw12345')
        collection = Collection.objects.create(owner=self.alice, name='Mine', visibility=Collection.VISIBILITY_PRIVATE)
        response = self.client.get(reverse('cards:collection_view', args=[collection.share_token]))
        self.assertEqual(response.status_code, 200)

    def test_other_user_cannot_view_a_private_collection(self):
        collection = Collection.objects.create(owner=self.alice, name='Secret', visibility=Collection.VISIBILITY_PRIVATE)
        response = self.client.get(reverse('cards:collection_view', args=[collection.share_token]))
        self.assertEqual(response.status_code, 404)

    def test_other_user_can_view_an_unlisted_collection_via_its_token(self):
        collection = Collection.objects.create(owner=self.alice, name='Shared by link', visibility=Collection.VISIBILITY_UNLISTED)
        response = self.client.get(reverse('cards:collection_view', args=[collection.share_token]))
        self.assertEqual(response.status_code, 200)

    def test_other_user_can_view_a_public_collection(self):
        collection = Collection.objects.create(owner=self.alice, name='Open to all', visibility=Collection.VISIBILITY_PUBLIC)
        response = self.client.get(reverse('cards:collection_view', args=[collection.share_token]))
        self.assertEqual(response.status_code, 200)

    def test_library_lists_public_collections_from_other_users(self):
        Collection.objects.create(owner=self.alice, name='Public one', visibility=Collection.VISIBILITY_PUBLIC)
        response = self.client.get(reverse('cards:library'))
        self.assertContains(response, 'Public one')

    def test_library_excludes_unlisted_and_private_collections(self):
        Collection.objects.create(owner=self.alice, name='Unlisted one', visibility=Collection.VISIBILITY_UNLISTED)
        Collection.objects.create(owner=self.alice, name='Private one', visibility=Collection.VISIBILITY_PRIVATE)
        response = self.client.get(reverse('cards:library'))
        self.assertNotContains(response, 'Unlisted one')
        self.assertNotContains(response, 'Private one')

    def test_library_excludes_the_current_users_own_public_collections(self):
        # Bob's own public collections belong on "My collections", not on
        # the library page (which is for discovering other people's).
        Collection.objects.create(owner=self.bob, name="Bob's own public one", visibility=Collection.VISIBILITY_PUBLIC)
        response = self.client.get(reverse('cards:library'))
        self.assertNotContains(response, "Bob's own public one")


class CardTakeTests(TestCase):
    """Tests for copying a card out of someone else's collection."""

    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pw12345')
        self.bob = User.objects.create_user('bob', password='pw12345')
        self.collection = Collection.objects.create(owner=self.alice, name='Spanish', visibility=Collection.VISIBILITY_PUBLIC)
        self.source_card = Card.objects.create(
            user=self.alice, question='hola', answer='hello', collection=self.collection,
        )
        self.client.login(username='bob', password='pw12345')

    def test_taking_a_card_creates_a_new_row_for_the_taker(self):
        self.client.post(reverse('cards:card_take', args=[self.source_card.pk]), {'collection': ''})
        taken = Card.objects.get(user=self.bob, question='hola')
        self.assertEqual(taken.answer, 'hello')
        self.assertNotEqual(taken.pk, self.source_card.pk)

    def test_taken_card_starts_at_stage_zero_regardless_of_the_source_stage(self):
        self.source_card.stage = MAX_STAGE
        self.source_card.save()
        self.client.post(reverse('cards:card_take', args=[self.source_card.pk]), {'collection': ''})
        taken = Card.objects.get(user=self.bob, question='hola')
        self.assertEqual(taken.stage, 0)

    def test_taken_card_records_its_source_collection(self):
        self.client.post(reverse('cards:card_take', args=[self.source_card.pk]), {'collection': ''})
        taken = Card.objects.get(user=self.bob, question='hola')
        self.assertEqual(taken.source_collection, self.collection)

    def test_taken_card_can_be_filed_into_one_of_the_takers_own_collections(self):
        my_collection = Collection.objects.create(owner=self.bob, name='My Spanish practice')
        self.client.post(
            reverse('cards:card_take', args=[self.source_card.pk]), {'collection': my_collection.pk},
        )
        taken = Card.objects.get(user=self.bob, question='hola')
        self.assertEqual(taken.collection, my_collection)

    def test_cannot_take_a_card_from_a_private_collection(self):
        private_collection = Collection.objects.create(owner=self.alice, name='Private', visibility=Collection.VISIBILITY_PRIVATE)
        private_card = Card.objects.create(user=self.alice, question='secret', answer='shh', collection=private_collection)
        response = self.client.post(reverse('cards:card_take', args=[private_card.pk]), {'collection': ''})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Card.objects.filter(user=self.bob, question='secret').exists())

    def test_taking_the_same_card_twice_does_not_duplicate_it(self):
        self.client.post(reverse('cards:card_take', args=[self.source_card.pk]), {'collection': ''})
        self.client.post(reverse('cards:card_take', args=[self.source_card.pk]), {'collection': ''})
        self.assertEqual(Card.objects.filter(user=self.bob, question='hola').count(), 1)


class CollectionTakeTests(TestCase):
    """Tests for copying a whole collection into the taker's own cards."""

    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pw12345')
        self.bob = User.objects.create_user('bob', password='pw12345')
        self.collection = Collection.objects.create(
            owner=self.alice, name='Spanish', description='basics', visibility=Collection.VISIBILITY_PUBLIC,
        )
        for q, a in [('hola', 'hello'), ('adios', 'bye'), ('gracias', 'thanks')]:
            Card.objects.create(user=self.alice, question=q, answer=a, collection=self.collection, stage=MAX_STAGE)
        self.url = reverse('cards:collection_take', args=[self.collection.share_token])
        self.client.login(username='bob', password='pw12345')

    def test_default_creates_own_collection_with_all_cards_at_stage_zero(self):
        self.client.post(self.url, {'collection': 'new'})
        mine = Collection.objects.get(owner=self.bob)
        self.assertEqual(mine.name, 'Spanish')
        self.assertEqual(mine.visibility, Collection.VISIBILITY_PRIVATE)
        cards = Card.objects.filter(user=self.bob)
        self.assertEqual(cards.count(), 3)
        self.assertTrue(all(c.stage == 0 and c.collection == mine and c.source_collection == self.collection for c in cards))

    def test_taking_again_reuses_earlier_copy_and_adds_only_new_cards(self):
        self.client.post(self.url, {'collection': 'new'})
        Card.objects.create(user=self.alice, question='perro', answer='dog', collection=self.collection)
        self.client.post(self.url, {'collection': 'new'})
        self.assertEqual(Collection.objects.filter(owner=self.bob).count(), 1)
        self.assertEqual(Card.objects.filter(user=self.bob).count(), 4)

    def test_without_collection(self):
        self.client.post(self.url, {'collection': ''})
        self.assertFalse(Collection.objects.filter(owner=self.bob).exists())
        self.assertEqual(Card.objects.filter(user=self.bob, collection=None).count(), 3)

    def test_into_existing_own_collection_skipping_duplicates(self):
        mine = Collection.objects.create(owner=self.bob, name='Mine')
        Card.objects.create(user=self.bob, question='hola', answer='hi', stage=3)
        self.client.post(self.url, {'collection': mine.pk})
        self.assertEqual(Card.objects.filter(user=self.bob, collection=mine).count(), 2)
        self.assertEqual(Card.objects.get(user=self.bob, question='hola').stage, 3)

    def test_cannot_file_into_someone_elses_collection(self):
        other = Collection.objects.create(owner=self.alice, name='Alice other')
        response = self.client.post(self.url, {'collection': other.pk})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Card.objects.filter(user=self.bob).exists())

    def test_cannot_take_private_collection(self):
        self.collection.visibility = Collection.VISIBILITY_PRIVATE
        self.collection.save()
        response = self.client.post(self.url, {'collection': 'new'})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Card.objects.filter(user=self.bob).exists())


class PrivateSharingFlowTests(TestCase):
    """End to end: make a private set, share it by link, someone copies it."""

    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pw12345')
        self.bob = User.objects.create_user('bob', password='pw12345')

    def test_private_set_shared_by_link(self):
        self.client.login(username='alice', password='pw12345')
        self.client.post(reverse('cards:collections'), {'name': 'Secret set', 'description': '', 'visibility': 'private'})
        collection = Collection.objects.get(owner=self.alice, name='Secret set')
        self.assertEqual(collection.visibility, Collection.VISIBILITY_PRIVATE)
        self.client.post(reverse('cards:collection_detail', args=[collection.pk]),
                         {'question': 'q1', 'answer': 'a1', 'collection': collection.pk})
        link = reverse('cards:collection_view', args=[collection.share_token])

        self.assertNotContains(self.client.get(reverse('cards:collection_detail', args=[collection.pk])), link)
        self.client.logout()
        self.client.login(username='bob', password='pw12345')
        self.assertEqual(self.client.get(link).status_code, 404)

        self.client.logout()
        self.client.login(username='alice', password='pw12345')
        self.client.post(reverse('cards:collection_set_visibility', args=[collection.pk]), {'visibility': 'unlisted'})
        self.assertContains(self.client.get(reverse('cards:collection_detail', args=[collection.pk])), link)

        self.client.logout()
        self.client.login(username='bob', password='pw12345')
        self.assertContains(self.client.get(link), 'q1')
        self.assertNotContains(self.client.get(reverse('cards:library')), 'Secret set')
        self.client.post(reverse('cards:collection_take', args=[collection.share_token]), {'collection': 'new'})
        self.assertTrue(Card.objects.filter(user=self.bob, question='q1', collection__name='Secret set').exists())

        self.client.logout()
        self.client.login(username='alice', password='pw12345')
        self.client.post(reverse('cards:collection_set_visibility', args=[collection.pk]), {'visibility': 'private'})
        self.client.logout()
        self.client.login(username='bob', password='pw12345')
        self.assertEqual(self.client.get(link).status_code, 404)

    def test_cannot_change_visibility_of_someone_elses_set(self):
        collection = Collection.objects.create(owner=self.alice, name='A')
        self.client.login(username='bob', password='pw12345')
        response = self.client.post(reverse('cards:collection_set_visibility', args=[collection.pk]), {'visibility': 'public'})
        self.assertEqual(response.status_code, 404)
        collection.refresh_from_db()
        self.assertEqual(collection.visibility, Collection.VISIBILITY_PRIVATE)


class CardSetCollectionTests(TestCase):
    """Tests for moving one of a user's own cards between their own
    collections, without disturbing its review progress."""

    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pw12345')
        self.client.login(username='alice', password='pw12345')
        self.card = Card.objects.create(user=self.alice, question='q', answer='a', stage=3)

    def test_moving_a_card_into_a_collection_sets_it(self):
        target = Collection.objects.create(owner=self.alice, name='Target')
        self.client.post(reverse('cards:card_set_collection', args=[self.card.pk]), {'collection': target.pk})
        self.card.refresh_from_db()
        self.assertEqual(self.card.collection, target)

    def test_moving_a_card_does_not_reset_its_stage(self):
        target = Collection.objects.create(owner=self.alice, name='Target')
        self.client.post(reverse('cards:card_set_collection', args=[self.card.pk]), {'collection': target.pk})
        self.card.refresh_from_db()
        self.assertEqual(self.card.stage, 3)

    def test_submitting_no_collection_clears_it(self):
        target = Collection.objects.create(owner=self.alice, name='Target')
        self.card.collection = target
        self.card.save()
        self.client.post(reverse('cards:card_set_collection', args=[self.card.pk]), {'collection': ''})
        self.card.refresh_from_db()
        self.assertIsNone(self.card.collection)

    def test_cannot_move_a_card_into_someone_elses_collection(self):
        bob = User.objects.create_user('bob', password='pw12345')
        bobs_collection = Collection.objects.create(owner=bob, name="Bob's")
        response = self.client.post(
            reverse('cards:card_set_collection', args=[self.card.pk]), {'collection': bobs_collection.pk},
        )
        self.assertEqual(response.status_code, 404)


class ReviewCollectionFilterTests(TestCase):
    """Tests for filtering the review queue down to a single collection."""

    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pw12345')
        self.client.login(username='alice', password='pw12345')
        self.spanish = Collection.objects.create(owner=self.alice, name='Spanish')
        self.french = Collection.objects.create(owner=self.alice, name='French')
        self.spanish_card = Card.objects.create(
            user=self.alice, question='hola', answer='hello', collection=self.spanish,
            next_review_at=timezone.now(),
        )
        self.french_card = Card.objects.create(
            user=self.alice, question='bonjour', answer='hello', collection=self.french,
            next_review_at=timezone.now(),
        )

    def test_without_a_filter_any_due_card_can_come_up(self):
        response = self.client.get(reverse('cards:review'))
        self.assertIn(response.context['card'], [self.spanish_card, self.french_card])

    def test_filtering_by_collection_only_offers_cards_from_it(self):
        response = self.client.get(reverse('cards:review'), {'collection': self.spanish.pk})
        self.assertEqual(response.context['card'], self.spanish_card)

    def test_grading_a_card_preserves_the_active_filter(self):
        response = self.client.post(
            reverse('cards:grade', args=[self.spanish_card.pk]),
            {'correct': '1', 'collection': self.spanish.pk},
        )
        self.assertRedirects(response, f"{reverse('cards:review')}?collection={self.spanish.pk}")


class CardFormCollectionFieldTests(TestCase):
    """Tests for the `collection` field added to CardForm: a user should
    only ever be offered (or able to submit) their own collections."""

    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pw12345')
        self.bob = User.objects.create_user('bob', password='pw12345')
        self.alices_collection = Collection.objects.create(owner=self.alice, name="Alice's")
        self.bobs_collection = Collection.objects.create(owner=self.bob, name="Bob's")

    def test_collection_field_only_offers_the_given_users_own_collections(self):
        from .forms import CardForm
        form = CardForm(user=self.alice)
        offered = set(form.fields['collection'].queryset)
        self.assertEqual(offered, {self.alices_collection})

    def test_collection_field_is_optional(self):
        from .forms import CardForm
        form = CardForm(
            data={'question': 'q', 'answer': 'a', 'collection': ''}, user=self.alice,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_cannot_submit_someone_elses_collection_id(self):
        from .forms import CardForm
        form = CardForm(
            data={'question': 'q', 'answer': 'a', 'collection': self.bobs_collection.pk}, user=self.alice,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('collection', form.errors)


class AddCardWithCollectionTests(TestCase):
    """Tests for choosing a collection at card-creation time, from each of
    the three places a card can now be created: the main card list, a
    collection's own page, and the review screen."""

    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pw12345')
        self.client.login(username='alice', password='pw12345')
        self.collection = Collection.objects.create(owner=self.alice, name='Spanish')

    def test_creating_a_card_from_the_card_list_can_set_its_collection(self):
        self.client.post(reverse('cards:list'), {
            'question': 'hola', 'answer': 'hello', 'collection': self.collection.pk,
        })
        card = Card.objects.get(user=self.alice, question='hola')
        self.assertEqual(card.collection, self.collection)

    def test_creating_a_card_on_a_collections_own_page_defaults_into_it(self):
        response = self.client.get(reverse('cards:collection_detail', args=[self.collection.pk]))
        self.assertEqual(response.context['form'].initial.get('collection'), self.collection.pk)

        self.client.post(reverse('cards:collection_detail', args=[self.collection.pk]), {
            'question': 'hola', 'answer': 'hello', 'collection': self.collection.pk,
        })
        card = Card.objects.get(user=self.alice, question='hola')
        self.assertEqual(card.collection, self.collection)

    def test_adding_a_card_during_review_makes_it_due_immediately(self):
        self.client.post(reverse('cards:review'), {
            'question': 'hola', 'answer': 'hello', 'collection': '',
        })
        card = Card.objects.get(user=self.alice, question='hola')
        self.assertLessEqual(card.next_review_at, timezone.now())
        self.assertTrue(Card.objects.filter(
            user=self.alice, question='hola', next_review_at__lte=timezone.now(),
        ).exists())

    def test_adding_a_card_during_review_can_set_its_collection(self):
        self.client.post(reverse('cards:review'), {
            'question': 'hola', 'answer': 'hello', 'collection': self.collection.pk,
        })
        card = Card.objects.get(user=self.alice, question='hola')
        self.assertEqual(card.collection, self.collection)

    def test_adding_a_card_during_a_filtered_review_session_keeps_the_filter_on_redirect(self):
        response = self.client.post(
            f"{reverse('cards:review')}?collection={self.collection.pk}",
            {'question': 'hola', 'answer': 'hello', 'collection': ''},
        )
        self.assertRedirects(response, f"{reverse('cards:review')}?collection={self.collection.pk}")


class QuoteOfTheDayTests(SimpleTestCase):
    """Tests for the daily quote shown on the card list page."""

    def test_same_quote_all_day(self):
        today = date(2026, 1, 1)
        self.assertEqual(get_quote_of_the_day(today), get_quote_of_the_day(today))

    def test_quote_changes_on_a_different_day(self):
        # Not guaranteed mathematically for every possible pair of dates,
        # but true for this specific pair -- good enough to catch "the
        # function ignores its argument and always returns the same thing".
        self.assertNotEqual(get_quote_of_the_day(date(2026, 1, 1)), get_quote_of_the_day(date(2026, 1, 2)))

    def test_quote_is_one_of_the_known_quotes(self):
        self.assertIn(get_quote_of_the_day(date(2026, 1, 1)), QUOTES)


class QuoteOnCardListPageTests(TestCase):
    """This one needs a real logged-in user/DB, hence a separate TestCase
    from the pure-function tests above (which deliberately stay SimpleTestCase)."""

    def test_card_list_page_shows_todays_quote(self):
        user = User.objects.create_user('quoteuser', password='pw12345')
        self.client.force_login(user)
        text, author = get_quote_of_the_day()
        response = self.client.get(reverse('cards:list'))
        self.assertContains(response, text)
        self.assertContains(response, author)


class StudyByTopicsTests(TestCase):
    """Tests for the topic picker and the choice between the two study modes."""

    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pw12345')
        self.client.login(username='alice', password='pw12345')
        self.collection = Collection.objects.create(owner=self.alice, name='Spanish')

    def test_study_topics_lists_the_users_own_collections(self):
        response = self.client.get(reverse('cards:study_topics'))
        self.assertContains(response, 'Spanish')

    def test_study_choose_shows_both_modes_for_the_topic(self):
        response = self.client.get(reverse('cards:study_choose', args=[self.collection.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Go through the whole topic')
        self.assertContains(response, "Only what's due")

    def test_cannot_choose_study_mode_for_someone_elses_topic(self):
        bob = User.objects.create_user('bob', password='pw12345')
        bobs_collection = Collection.objects.create(owner=bob, name="Bob's")
        response = self.client.get(reverse('cards:study_choose', args=[bobs_collection.pk]))
        self.assertEqual(response.status_code, 404)


class TopicRunTests(TestCase):
    """The whole-topic run: DB-backed, round after round of only the missed
    cards, never touching Card.stage/next_review_at or ReviewLog."""

    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pw12345')
        self.client.login(username='alice', password='pw12345')
        self.collection = Collection.objects.create(owner=self.alice, name='Spanish')
        self.card1 = Card.objects.create(user=self.alice, question='hola', answer='hello', collection=self.collection)
        self.card2 = Card.objects.create(user=self.alice, question='gracias', answer='thanks', collection=self.collection)
        self.pk = self.collection.pk

    def _start(self):
        self.client.post(reverse('cards:run_start', args=[self.pk]))

    def _current(self):
        return self.client.get(reverse('cards:topic_run', args=[self.pk])).context.get('card')

    def _grade(self, correct):
        card = self._current()
        self.client.post(reverse('cards:run_grade', args=[self.pk]), {'card': card.pk, 'correct': '1' if correct else '0'})
        return card

    def _run(self):
        return TopicRun.objects.get(user=self.alice, collection=self.collection)

    def test_start_queues_every_card_in_the_topic(self):
        self._start()
        run = self._run()
        self.assertEqual(sorted(run.queue), sorted([self.card1.pk, self.card2.pk]))
        self.assertEqual(run.round, 1)

    def test_grading_does_not_touch_stage_or_review_log(self):
        self._start()
        card = self._grade(True)
        self._grade(False)
        card.refresh_from_db()
        self.assertEqual(card.stage, 0)
        self.assertFalse(ReviewLog.objects.exists())

    def test_progress_is_stored_in_db_and_survives_a_new_login(self):
        self._start()
        first = self._grade(False)
        self.client.logout()
        self.client.login(username='alice', password='pw12345')
        self.assertNotEqual(self._current(), first)
        self.assertEqual(self._run().wrong, [first.pk])

    def test_starting_again_continues_instead_of_restarting(self):
        self._start()
        self._grade(True)
        self._start()
        self.assertEqual(len(self._run().queue), 1)

    def test_next_round_has_only_the_missed_cards(self):
        self._start()
        self._grade(True)
        missed = self._grade(False)
        self.client.post(reverse('cards:run_next_round', args=[self.pk]))
        run = self._run()
        self.assertEqual((run.round, run.queue, run.wrong), (2, [missed.pk], []))

    def test_all_correct_completes_the_run(self):
        self._start()
        self._grade(True)
        self._grade(True)
        self.assertTrue(self._run().completed)

    def test_stale_grade_for_a_different_card_is_ignored(self):
        self._start()
        card = self._grade(True)
        self.client.post(reverse('cards:run_grade', args=[self.pk]), {'card': card.pk, 'correct': '0'})
        self.assertEqual(len(self._run().queue), 1)
        self.assertEqual(self._run().wrong, [])

    def test_reset_deletes_only_the_run(self):
        self.card1.stage = 3
        self.card1.save()
        self._start()
        self._grade(False)
        self.client.post(reverse('cards:run_reset', args=[self.pk]))
        self.assertFalse(TopicRun.objects.exists())
        self.card1.refresh_from_db()
        self.assertEqual(self.card1.stage, 3)

    def test_reset_with_restart_begins_a_fresh_round_one(self):
        self._start()
        self._grade(True)
        self._grade(True)
        self.client.post(reverse('cards:run_reset', args=[self.pk]), {'restart': '1'})
        run = self._run()
        self.assertEqual((run.round, len(run.queue)), (1, 2))

    def test_runs_of_different_topics_are_independent(self):
        other = Collection.objects.create(owner=self.alice, name='French')
        Card.objects.create(user=self.alice, question='bonjour', answer='hi', collection=other)
        self._start()
        self.client.post(reverse('cards:run_start', args=[other.pk]))
        self.assertEqual(TopicRun.objects.filter(user=self.alice).count(), 2)

    def test_deleted_card_is_dropped_from_the_queue(self):
        self._start()
        Card.objects.get(pk=self._run().queue[0]).delete()
        self.assertIsNotNone(self._current())
        self.assertEqual(len(self._run().queue), 1)

    def test_cannot_start_a_run_on_someone_elses_topic(self):
        bob = User.objects.create_user('bob', password='pw12345')
        bobs_collection = Collection.objects.create(owner=bob, name="Bob's")
        response = self.client.post(reverse('cards:run_start', args=[bobs_collection.pk]))
        self.assertEqual(response.status_code, 404)


class ReviewMultiTopicFilterTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pw12345')
        self.client.login(username='alice', password='pw12345')
        self.a = Collection.objects.create(owner=self.alice, name='A')
        self.b = Collection.objects.create(owner=self.alice, name='B')
        self.c = Collection.objects.create(owner=self.alice, name='C')
        past = timezone.now() - timedelta(hours=1)
        self.card_a = Card.objects.create(user=self.alice, question='a', answer='a', collection=self.a, next_review_at=past - timedelta(minutes=3))
        self.card_c = Card.objects.create(user=self.alice, question='c', answer='c', collection=self.c, next_review_at=past - timedelta(minutes=2))
        self.card_none = Card.objects.create(user=self.alice, question='n', answer='n', next_review_at=past - timedelta(minutes=1))
        self.card_b = Card.objects.create(user=self.alice, question='b', answer='b', collection=self.b, next_review_at=past)

    def _card(self, *values):
        return self.client.get(reverse('cards:review'), {'collection': list(values)}).context['card']

    def test_several_topics_at_once(self):
        self.assertIn(self._card(self.b.pk, self.c.pk), [self.card_b, self.card_c])

    def test_no_collection_option(self):
        self.assertEqual(self._card('none'), self.card_none)
        self.assertIn(self._card('none', self.b.pk), [self.card_none, self.card_b])

    def test_grade_keeps_the_filter(self):
        response = self.client.post(
            reverse('cards:grade', args=[self.card_c.pk]),
            {'correct': '1', 'collection': [self.b.pk, self.c.pk]},
        )
        self.assertEqual(response.url, f"{reverse('cards:review')}?collection={self.b.pk}&collection={self.c.pk}")
        self.assertEqual(self.client.get(response.url).context['card'], self.card_b)

    def test_foreign_collection_ids_are_ignored(self):
        bob = User.objects.create_user('bob', password='pw12345')
        foreign = Collection.objects.create(owner=bob, name='X')
        self.assertIn(self._card(foreign.pk), [self.card_a, self.card_b, self.card_c, self.card_none])  # = no filter


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
