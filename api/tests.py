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
        self.assertEqual(card['stage'], 2)
        self.card.refresh_from_db()
        self.assertEqual(self.card.next_review_at, t0 + timedelta(minutes=5) + STAGE_INTERVALS[2])
        self.assertEqual(ReviewLog.objects.filter(card=self.card).count(), 2)

    def test_pushing_the_same_review_twice_applies_it_once(self):
        event = {'uuid': str(uuid.uuid4()), 'card': str(self.card.uuid), 'correct': True, 'reviewed_at': iso(timezone.now())}
        self.sync(reviews=[event])
        self.sync(reviews=[event])
        self.card.refresh_from_db()
        self.assertEqual(self.card.stage, 1)

    def test_late_offline_review_never_moves_due_date_backwards(self):
        # Web review now -> stage 1, due in 30 min. Phone pushes an older
        # wrong answer from yesterday afterwards.
        from cards.services import apply_review
        apply_review(self.card, True)
        self.card.refresh_from_db()
        due = self.card.next_review_at
        self.sync(reviews=[{
            'uuid': str(uuid.uuid4()), 'card': str(self.card.uuid), 'correct': False,
            'reviewed_at': iso(timezone.now() - timedelta(days=1)),
        }])
        self.card.refresh_from_db()
        self.assertEqual(self.card.stage, 0)
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
        self.assertEqual((card.user, card.collection.uuid, card.stage), (self.alice, cu, 1))

    def test_duplicate_question_is_rejected(self):
        data = self.sync(cards=[{'uuid': str(uuid.uuid4()), 'question': 'Hund', 'answer': 'x', 'content_updated_at': iso(timezone.now())}])
        self.assertEqual(data['rejected'][0]['reason'], 'duplicate_question')

    def test_later_content_edit_wins_and_review_does_not_count_as_edit(self):
        edited_on_phone = timezone.now()
        from cards.services import apply_review
        apply_review(self.card, True)  # review on web after the phone edit
        data = self.sync(cards=[{
            'uuid': str(self.card.uuid), 'question': 'Hund', 'answer': 'the dog',
            'collection': str(self.col.uuid), 'content_updated_at': iso(edited_on_phone),
        }])
        self.card.refresh_from_db()
        self.assertEqual((self.card.answer, self.card.stage), ('the dog', 1))
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
