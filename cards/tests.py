from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Card, Collection, ReviewLog
from .progress import LEVEL_SIZE, get_learned_count, get_user_level, get_user_progress
from .quotes import QUOTES, get_quote_of_the_day
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
        self.assertContains(response, "Only what's not learned yet")

    def test_cannot_choose_study_mode_for_someone_elses_topic(self):
        bob = User.objects.create_user('bob', password='pw12345')
        bobs_collection = Collection.objects.create(owner=bob, name="Bob's")
        response = self.client.get(reverse('cards:study_choose', args=[bobs_collection.pk]))
        self.assertEqual(response.status_code, 404)


class QuizTests(TestCase):
    """Tests for the ungraded "whole topic" quiz: it must never touch a
    Card's stage/next_review_at or write a ReviewLog, since it's a practice
    pass, not a spaced-repetition session -- all state lives in the session."""

    def setUp(self):
        self.alice = User.objects.create_user('alice', password='pw12345')
        self.client.login(username='alice', password='pw12345')
        self.collection = Collection.objects.create(owner=self.alice, name='Spanish')
        self.card1 = Card.objects.create(user=self.alice, question='hola', answer='hello', collection=self.collection, stage=0)
        self.card2 = Card.objects.create(user=self.alice, question='gracias', answer='thanks', collection=self.collection, stage=0)

    def test_starting_a_quiz_queues_every_card_in_the_topic(self):
        self.client.post(reverse('cards:quiz_start', args=[self.collection.pk]))
        response = self.client.get(reverse('cards:quiz'))
        self.assertEqual(response.context['total'], 2)
        self.assertIn(response.context['card'], [self.card1, self.card2])

    def test_grading_in_a_quiz_does_not_touch_the_cards_stage(self):
        self.client.post(reverse('cards:quiz_start', args=[self.collection.pk]))
        first_card = self.client.get(reverse('cards:quiz')).context['card']
        self.client.post(reverse('cards:quiz_grade'), {'correct': '1'})

        first_card.refresh_from_db()
        self.assertEqual(first_card.stage, 0)

    def test_grading_in_a_quiz_does_not_write_a_review_log(self):
        self.client.post(reverse('cards:quiz_start', args=[self.collection.pk]))
        self.client.post(reverse('cards:quiz_grade'), {'correct': '0'})
        self.assertFalse(ReviewLog.objects.exists())

    def test_quiz_shows_a_summary_once_the_queue_is_empty(self):
        self.client.post(reverse('cards:quiz_start', args=[self.collection.pk]))
        self.client.post(reverse('cards:quiz_grade'), {'correct': '1'})
        self.client.post(reverse('cards:quiz_grade'), {'correct': '0'})

        response = self.client.get(reverse('cards:quiz'))
        self.assertTrue(response.context['finished'])
        self.assertEqual(response.context['correct_count'], 1)
        self.assertEqual(response.context['wrong_count'], 1)

    def test_retry_only_requeues_the_cards_missed_last_pass(self):
        self.client.post(reverse('cards:quiz_start', args=[self.collection.pk]))
        self.client.post(reverse('cards:quiz_grade'), {'correct': '1'})  # card A: right
        self.client.post(reverse('cards:quiz_grade'), {'correct': '0'})  # card B: wrong

        self.client.post(reverse('cards:quiz_retry'))
        response = self.client.get(reverse('cards:quiz'))
        self.assertEqual(response.context['total'], 1)

    def test_exiting_clears_the_quiz_session_state(self):
        self.client.post(reverse('cards:quiz_start', args=[self.collection.pk]))
        self.client.post(reverse('cards:quiz_exit'))
        response = self.client.get(reverse('cards:quiz'))
        self.assertRedirects(response, reverse('cards:study_topics'))

    def test_cannot_start_a_quiz_on_someone_elses_topic(self):
        bob = User.objects.create_user('bob', password='pw12345')
        bobs_collection = Collection.objects.create(owner=bob, name="Bob's")
        response = self.client.post(reverse('cards:quiz_start', args=[bobs_collection.pk]))
        self.assertEqual(response.status_code, 404)
