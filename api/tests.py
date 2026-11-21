import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from accounts.models import Profile
from cards.models import Card, Collection, ReviewLog, Tombstone, TopicRun
from cards.scheduler import STAGE_INTERVALS

FAST_HASHER = override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])


def iso(dt):
    return dt.isoformat()


@FAST_HASHER
class ApiTestCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice@example.com', email='alice@example.com', password='pw12345')
        Profile.objects.create(user=self.alice, nickname='Alice')
        self.bob = User.objects.create_user('bob@example.com', email='bob@example.com', password='pw12345')
        Profile.objects.create(user=self.bob, nickname='Bob')
        self.client = self.as_user(self.alice)

    def as_user(self, user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.get_or_create(user=user)[0].key)
        return client

    def sync(self, client=None, **payload):
        response = (client or self.client).post(reverse('api:sync'), payload, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()


class AuthTests(ApiTestCase):
    def test_login_by_nickname_or_email_returns_token(self):
        anon = APIClient()
        for login in ('Alice', 'alice@example.com'):
            response = anon.post(reverse('api:token'), {'login': login, 'password': 'pw12345'}, format='json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['token'], Token.objects.get(user=self.alice).key)
            self.assertEqual(response.json()['user']['nickname'], 'Alice')

    def test_wrong_password(self):
        response = APIClient().post(reverse('api:token'), {'login': 'Alice', 'password': 'nope'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_endpoints_require_token(self):
        self.assertEqual(APIClient().post(reverse('api:sync'), {}, format='json').status_code, 401)
        self.assertEqual(APIClient().get(reverse('api:library')).status_code, 401)

    def test_logout_revokes_token(self):
        self.client.post(reverse('api:logout'))
        self.assertEqual(self.client.get(reverse('api:me')).status_code, 401)

    def test_scheduler_endpoint(self):
        response = APIClient().get(reverse('api:scheduler'))
        self.assertEqual(response.json()['intervals_seconds'][0], int(STAGE_INTERVALS[0].total_seconds()))


class LibraryAndTakeTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.public = Collection.objects.create(owner=self.bob, name='Spanish', visibility='public')
        self.unlisted = Collection.objects.create(owner=self.bob, name='Hidden', visibility='unlisted')
        self.private = Collection.objects.create(owner=self.bob, name='Mine', visibility='private')
        self.c1 = Card.objects.create(user=self.bob, question='hola', answer='hello', collection=self.public, stage=4)
        self.c2 = Card.objects.create(user=self.bob, question='adios', answer='bye', collection=self.public)
        Card.objects.create(user=self.bob, question='x', answer='y', collection=self.unlisted)

    def test_library_lists_only_public_collections_of_others(self):
        names = [c['name'] for c in self.client.get(reverse('api:library')).json()]
        self.assertEqual(names, ['Spanish'])

    def test_shared_view_by_token(self):
        ok = self.client.get(reverse('api:shared', args=[self.unlisted.share_token]))
        self.assertEqual(ok.json()['cards'][0]['question'], 'x')
        self.assertEqual(self.client.get(reverse('api:shared', args=[self.private.share_token])).status_code, 404)

    def test_take_whole_collection_as_own_then_sync_downloads_it(self):
        response = self.client.post(reverse('api:take', args=[self.public.share_token]), {'target': 'new'}, format='json')
        self.assertEqual(response.json()['added'], 2)
        data = self.sync()
        self.assertEqual([c['name'] for c in data['collections']], ['Spanish'])
        self.assertEqual({c['question'] for c in data['cards']}, {'hola', 'adios'})
        self.assertTrue(all(c['stage'] == 0 and c['collection'] == response.json()['collection'] for c in data['cards']))

    def test_take_single_card_without_collection(self):
        response = self.client.post(
            reverse('api:take', args=[self.public.share_token]),
            {'target': None, 'cards': [str(self.c1.uuid)]}, format='json',
        )
        self.assertEqual(response.json(), {'added': 1, 'skipped': 0, 'collection': None})
        self.assertFalse(Collection.objects.filter(owner=self.alice).exists())

    def test_take_into_someone_elses_collection_is_refused(self):
        response = self.client.post(
            reverse('api:take', args=[self.public.share_token]), {'target': str(self.private.uuid)}, format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Card.objects.filter(user=self.alice).exists())

    def test_cannot_take_private(self):
        response = self.client.post(reverse('api:take', args=[self.private.share_token]), {}, format='json')
        self.assertEqual(response.status_code, 404)


class SyncTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.col = Collection.objects.create(owner=self.alice, name='German')
        self.card = Card.objects.create(user=self.alice, question='Hund', answer='dog', collection=self.col)
        Card.objects.create(user=self.bob, question='bobs', answer='card')

    def test_first_sync_downloads_only_own_data(self):
        data = self.sync()
        self.assertEqual([c['question'] for c in data['cards']], ['Hund'])
        self.assertEqual(data['cards'][0]['collection'], str(self.col.uuid))
        self.assertEqual(data['deleted'], [])
        self.assertIn('server_time', data)

    def test_incremental_sync_returns_only_changes(self):
        since = self.sync()['server_time']
        self.assertEqual(self.sync(since=since)['cards'], [])
        Card.objects.create(user=self.alice, question='Katze', answer='cat')
        self.assertEqual([c['question'] for c in self.sync(since=since)['cards']], ['Katze'])

    def test_offline_reviews_move_the_stage_like_the_website(self):
        t0 = timezone.now() - timedelta(hours=2)
        events = [
            {'uuid': str(uuid.uuid4()), 'card': str(self.card.uuid), 'correct': True, 'reviewed_at': iso(t0)},
            {'uuid': str(uuid.uuid4()), 'card': str(self.card.uuid), 'correct': True, 'reviewed_at': iso(t0 + timedelta(minutes=5))},
        ]
        data = self.sync(reviews=list(reversed(events)))  # order in the payload doesn't matter
        card = data['cards'][0]
        self.assertEqual((card['stage'], card['correct_count']), (0, 2))
        self.card.refresh_from_db()
        self.assertEqual(self.card.next_review_at, t0 + timedelta(minutes=5) + STAGE_INTERVALS[0])
        self.assertEqual(ReviewLog.objects.filter(card=self.card).count(), 2)

    def test_pushing_the_same_review_twice_applies_it_once(self):
        event = {'uuid': str(uuid.uuid4()), 'card': str(self.card.uuid), 'correct': True, 'reviewed_at': iso(timezone.now())}
        self.sync(reviews=[event])
        self.sync(reviews=[event])
        self.card.refresh_from_db()
        self.assertEqual(self.card.correct_count, 1)

    def test_late_offline_review_never_moves_due_date_backwards(self):
        # Web review now -> due in 90 s. Phone pushes an older wrong answer
        # from yesterday afterwards (a wrong answer alone would make it due at once).
        from cards.services import apply_review
        apply_review(self.card, True)
        self.card.refresh_from_db()
        due = self.card.next_review_at
        self.sync(reviews=[{
            'uuid': str(uuid.uuid4()), 'card': str(self.card.uuid), 'correct': False,
            'reviewed_at': iso(timezone.now() - timedelta(days=1)),
        }])
        self.card.refresh_from_db()
        self.assertEqual((self.card.stage, self.card.correct_count), (0, 1))
        self.assertEqual(self.card.next_review_at, due)

    def test_review_from_the_future_is_clamped_to_now(self):
        self.sync(reviews=[{
            'uuid': str(uuid.uuid4()), 'card': str(self.card.uuid), 'correct': True,
            'reviewed_at': iso(timezone.now() + timedelta(days=30)),
        }])
        self.assertLessEqual(ReviewLog.objects.get().reviewed_at, timezone.now())

    def test_cannot_review_someone_elses_card(self):
        bobs = Card.objects.get(user=self.bob)
        data = self.sync(reviews=[{'uuid': str(uuid.uuid4()), 'card': str(bobs.uuid), 'correct': True, 'reviewed_at': iso(timezone.now())}])
        self.assertEqual(data['rejected'][0]['reason'], 'unknown_card')
        bobs.refresh_from_db()
        self.assertEqual(bobs.stage, 0)

    def test_create_collection_and_card_offline(self):
        cu, ku, now = uuid.uuid4(), uuid.uuid4(), timezone.now()
        data = self.sync(
            collections=[{'uuid': str(cu), 'name': 'Offline', 'description': '', 'visibility': 'private', 'updated_at': iso(now)}],
            cards=[{'uuid': str(ku), 'question': 'Q', 'answer': 'A', 'collection': str(cu), 'content_updated_at': iso(now)}],
            reviews=[{'uuid': str(uuid.uuid4()), 'card': str(ku), 'correct': True, 'reviewed_at': iso(now)}],
        )
        self.assertEqual(data['rejected'], [])
        card = Card.objects.get(uuid=ku)
        self.assertEqual((card.user, card.collection.uuid, card.correct_count), (self.alice, cu, 1))

    def test_same_question_is_allowed_for_copies(self):
        data = self.sync(cards=[{'uuid': str(uuid.uuid4()), 'question': 'Hund', 'answer': 'x', 'content_updated_at': iso(timezone.now())}])
        self.assertEqual(data['rejected'], [])
        self.assertEqual(Card.objects.filter(user=self.alice, question='Hund').count(), 2)

    def test_card_created_as_topic_copy_is_not_in_blitz(self):
        ku = uuid.uuid4()
        self.sync(cards=[{'uuid': str(ku), 'question': 'Q', 'answer': 'A', 'in_pool': False, 'content_updated_at': iso(timezone.now())}])
        self.assertFalse(Card.objects.get(uuid=ku).in_pool)

    def test_pool_events_remove_and_reset_idempotently(self):
        from cards.services import apply_review
        apply_review(self.card, True)
        remove = {'uuid': str(uuid.uuid4()), 'card': str(self.card.uuid), 'action': 'remove', 'at': iso(timezone.now())}
        data = self.sync(pool=[remove])
        self.assertFalse(data['cards'][0]['in_pool'])
        reset = {'uuid': str(uuid.uuid4()), 'card': str(self.card.uuid), 'action': 'reset', 'at': iso(timezone.now())}
        self.sync(pool=[reset])
        self.card.refresh_from_db()
        self.assertEqual((self.card.in_pool, self.card.correct_count), (True, 0))
        apply_review(self.card, True)
        self.sync(pool=[reset])  # re-sent: must not wipe the newer review
        self.card.refresh_from_db()
        self.assertEqual(self.card.correct_count, 1)

    def test_later_content_edit_wins_and_review_does_not_count_as_edit(self):
        edited_on_phone = timezone.now()
        from cards.services import apply_review
        apply_review(self.card, True)  # review on web after the phone edit
        data = self.sync(cards=[{
            'uuid': str(self.card.uuid), 'question': 'Hund', 'answer': 'the dog',
            'collection': str(self.col.uuid), 'content_updated_at': iso(edited_on_phone),
        }])
        self.card.refresh_from_db()
        self.assertEqual((self.card.answer, self.card.correct_count), ('the dog', 1))
        stale = self.sync(cards=[{
            'uuid': str(self.card.uuid), 'question': 'Hund', 'answer': 'old',
            'collection': str(self.col.uuid), 'content_updated_at': iso(edited_on_phone - timedelta(hours=1)),
        }])
        self.card.refresh_from_db()
        self.assertEqual(self.card.answer, 'the dog')
        self.assertEqual(stale['cards'][0]['answer'], 'the dog')  # server version echoed back

    def test_cannot_overwrite_someone_elses_card(self):
        bobs = Card.objects.get(user=self.bob)
        data = self.sync(cards=[{'uuid': str(bobs.uuid), 'question': 'hacked', 'answer': 'x', 'content_updated_at': iso(timezone.now() + timedelta(days=1))}])
        self.assertEqual(data['rejected'][0]['reason'], 'not_owner')
        bobs.refresh_from_db()
        self.assertEqual(bobs.question, 'bobs')

    def test_deletions_propagate_both_ways(self):
        since = self.sync()['server_time']
        other = Card.objects.create(user=self.alice, question='Maus', answer='mouse')
        # Phone deletes a card; web deletes the collection.
        data = self.sync(since=since, deleted=[{'kind': 'card', 'uuid': str(other.uuid)}])
        self.assertFalse(Card.objects.filter(pk=other.pk).exists())
        self.col.delete()
        data = self.sync(since=since)
        self.assertIn({'kind': 'collection', 'uuid': str(self.col.uuid)}, data['deleted'])
        self.assertIn({'kind': 'card', 'uuid': str(other.uuid)}, data['deleted'])

    def test_deleted_card_cannot_be_resurrected_by_a_stale_device(self):
        u = self.card.uuid
        self.card.delete()
        data = self.sync(cards=[{'uuid': str(u), 'question': 'Hund', 'answer': 'dog', 'content_updated_at': iso(timezone.now())}])
        self.assertEqual(data['rejected'][0]['reason'], 'deleted')
        self.assertFalse(Card.objects.filter(uuid=u).exists())

    def test_topic_run_round_trip_and_reset(self):
        now = timezone.now()
        self.sync(topic_runs=[{
            'collection': str(self.col.uuid), 'round': 2, 'queue': [str(self.card.uuid)], 'wrong': [],
            'round_total': 1, 'correct_count': 0, 'updated_at': iso(now),
        }])
        run = TopicRun.objects.get(user=self.alice)
        self.assertEqual((run.round, run.queue), (2, [self.card.pk]))
        since = self.sync()['server_time']
        run.delete()  # reset on the website
        data = self.sync(since=since)
        self.assertIn({'kind': 'topic_run', 'uuid': str(self.col.uuid)}, data['deleted'])

    def test_sync_does_not_touch_topic_runs_progress_separation(self):
        TopicRun.objects.create(user=self.alice, collection=self.col, queue=[self.card.pk], round_total=1)
        run = self.sync()['topic_runs'][0]
        self.assertEqual(run['queue'], [str(self.card.uuid)])

    def test_bad_payload(self):
        response = self.client.post(reverse('api:sync'), {'cards': 'nope'}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.post(reverse('api:sync'), {'since': 'yesterday'}, format='json')
        self.assertEqual(response.status_code, 400)
        data = self.sync(cards=['junk', {'uuid': 'x'}], reviews=[{'card': 'x'}])
        self.assertEqual(len(data['rejected']), 3)

    def test_deleting_a_user_does_not_crash_on_tombstones(self):
        self.alice.delete()
        self.assertTrue(Tombstone.objects.filter(kind='card').exists())


class TopicsFeaturesTests(ApiTestCase):
    """Added topics, adding someone's cards to the blitz, copying, author page, account."""

    def setUp(self):
        super().setUp()
        self.topic = Collection.objects.create(owner=self.bob, name='Physics', visibility='public', tags=['physics'])
        self.k1 = Card.objects.create(user=self.bob, question='Ohm', answer='I=U/R', collection=self.topic)
        self.k2 = Card.objects.create(user=self.bob, question='Joule', answer='Q=I2Rt', collection=self.topic)
        self.mine = Collection.objects.create(owner=self.alice, name='Mine')

    def url(self, name):
        return reverse(f'api:{name}', args=[self.topic.share_token])

    def test_subscribe_shows_up_in_sync_read_only(self):
        self.assertTrue(self.client.post(self.url('subscribe')).json()['is_added'])
        added = self.sync()['added_topics']
        self.assertEqual([(t['name'], len(t['cards']), t['tags']) for t in added], [('Physics', 2, ['physics'])])
        self.assertFalse(Card.objects.filter(user=self.alice).exists())  # nothing copied
        self.client.delete(self.url('subscribe'))
        self.assertEqual(self.sync()['added_topics'], [])

    def test_add_foreign_cards_to_blitz_as_linked_copies_with_skip_and_reset(self):
        r = self.client.post(self.url('add_to_blitz'), {'cards': [str(self.k1.uuid)]}, format='json').json()
        self.assertEqual(r, {'added': 1, 'reset': 0, 'skipped': 0})
        copy = Card.objects.get(user=self.alice, source_card=self.k1)
        self.assertTrue(copy.in_pool)
        from cards.services import apply_review
        apply_review(copy, True)
        both = [str(self.k1.uuid), str(self.k2.uuid)]
        r = self.client.post(self.url('add_to_blitz'), {'cards': both}, format='json').json()
        self.assertEqual(r, {'added': 1, 'reset': 0, 'skipped': 1})
        r = self.client.post(self.url('add_to_blitz'), {'cards': both, 'reset': [str(self.k1.uuid)]}, format='json').json()
        self.assertEqual(r, {'added': 0, 'reset': 1, 'skipped': 1})
        copy.refresh_from_db()
        self.assertEqual(copy.correct_count, 0)
        flags = {c['question']: c['in_blitz'] for c in self.client.get(self.url('shared')).json()['cards']}
        self.assertEqual(flags, {'Ohm': True, 'Joule': True})
        synced = {c['question']: c['source_collection'] for c in self.sync()['cards']}
        self.assertEqual(synced['Ohm'], str(self.topic.uuid))

    def test_copy_into_own_topic_not_into_blitz(self):
        r = self.client.post(self.url('copy'), {'cards': [str(self.k1.uuid)], 'target': str(self.mine.uuid)}, format='json')
        self.assertEqual(r.json(), {'copied': 1})
        copy = Card.objects.get(user=self.alice, collection=self.mine)
        self.assertFalse(copy.in_pool)

    def test_copy_into_someone_elses_topic_is_refused(self):
        r = self.client.post(self.url('copy'), {'cards': [str(self.k1.uuid)], 'target': str(self.topic.uuid)}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_private_topic_cannot_be_added(self):
        self.topic.visibility = 'private'
        self.topic.save()
        self.assertEqual(self.client.post(self.url('subscribe')).status_code, 404)
        self.assertEqual(self.client.post(self.url('add_to_blitz'), {'cards': [str(self.k1.uuid)]}, format='json').status_code, 404)

    def test_topic_run_on_added_topic(self):
        self.client.post(self.url('subscribe'))
        self.sync(topic_runs=[{'collection': str(self.topic.uuid), 'round': 1, 'queue': [str(self.k1.uuid)], 'wrong': [],
                               'round_total': 2, 'correct_count': 1, 'updated_at': iso(timezone.now())}])
        run = self.sync()['topic_runs'][0]
        self.assertEqual(run['queue'], [str(self.k1.uuid)])

    def test_author_page_and_tags_in_library(self):
        lib = self.client.get(reverse('api:library')).json()
        self.assertEqual(lib[0]['tags'], ['physics'])
        page = self.client.get(reverse('api:author', args=['bob'])).json()
        self.assertEqual((page['nickname'], [t['name'] for t in page['topics']]), ('Bob', ['Physics']))

    def test_collection_tags_sync(self):
        cu = uuid.uuid4()
        self.sync(collections=[{'uuid': str(cu), 'name': 'T', 'tags': ['a', 'b'], 'updated_at': iso(timezone.now())}])
        self.assertEqual(Collection.objects.get(uuid=cu).tags, ['a', 'b'])

    def test_change_nickname_and_password(self):
        bad = self.client.post(reverse('api:account'), {'current_password': 'nope', 'nickname': 'Alicia'}, format='json')
        self.assertEqual(bad.status_code, 400)
        taken = self.client.post(reverse('api:account'), {'current_password': 'pw12345', 'nickname': 'bob'}, format='json')
        self.assertEqual(taken.json()['fields']['nickname'], ['taken'])
        ok = self.client.post(reverse('api:account'), {'current_password': 'pw12345', 'nickname': 'Alicia', 'new_password': 'n3w-Passw0rd!'}, format='json')
        self.assertEqual(ok.json()['nickname'], 'Alicia')
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password('n3w-Passw0rd!'))
