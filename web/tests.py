from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from cards.models import Card, Collection, ReviewLog, TopicRun, TopicSubscription

FAST = override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])


def make_user(nick):
    user = User.objects.create_user(f'{nick}@example.com', email=f'{nick}@example.com', password='pw12345')
    Profile.objects.create(user=user, nickname=nick)
    return user


@FAST
class WebTestCase(TestCase):
    def setUp(self):
        self.alice = make_user('alice')
        self.bob = make_user('bob')
        self.client.force_login(self.alice)
        self.past = timezone.now() - timedelta(minutes=5)

    def card(self, user=None, **kw):
        kw.setdefault('question', f'q{Card.objects.count()}')
        kw.setdefault('answer', 'a')
        kw.setdefault('next_review_at', self.past)
        return Card.objects.create(user=user or self.alice, **kw)


class AccessTests(WebTestCase):
    def test_anonymous_is_sent_to_login(self):
        self.client.logout()
        self.assertRedirects(self.client.get('/'), reverse('login'), fetch_redirect_response=False)
        response = self.client.get(reverse('web:study'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_home_goes_to_study(self):
        self.assertRedirects(self.client.get('/'), reverse('web:study'))

    def test_all_pages_render(self):
        topic = Collection.objects.create(owner=self.alice, name='T')
        c = self.card(collection=topic)
        for name, args in [('study', []), ('blitz', []), ('add', []), ('cards', []), ('simple', []), ('library', []),
                           ('mine', []), ('added', []), ('browse', []), ('no_topic', []), ('topic_new', []),
                           ('topic', [topic.share_token]), ('topic_edit', [topic.share_token]), ('card', [c.uuid]),
                           ('author', ['alice']), ('profile', []), ('algorithm', []), ('account', [])]:
            self.assertEqual(self.client.get(reverse(f'web:{name}', args=args)).status_code, 200, name)

    def test_language_switch(self):
        self.client.post(reverse('web:language'), {'lang': 'en'})
        self.assertContains(self.client.get(reverse('web:study')), 'Start blitz')
        self.client.post(reverse('web:language'), {'lang': 'ru'})
        self.assertContains(self.client.get(reverse('web:study')), 'Начать блитц')


class BlitzTests(WebTestCase):
    def test_only_due_cards_in_the_blitz(self):
        self.card(question='due')
        self.card(question='later', next_review_at=timezone.now() + timedelta(days=1))
        self.card(question='out', in_pool=False)
        self.assertEqual(self.client.get(reverse('web:blitz')).context['card'].question, 'due')

    def test_answer_counts_and_wrong_keeps_it_due(self):
        c = self.card()
        self.client.post(reverse('web:blitz_answer'), {'card': c.uuid, 'correct': '1'})
        c.refresh_from_db()
        self.assertEqual((c.stage, c.correct_count), (0, 1))
        self.client.post(reverse('web:blitz_answer'), {'card': c.uuid, 'correct': '0'})
        c.refresh_from_db()
        self.assertEqual(c.correct_count, 1)
        self.assertLessEqual(c.next_review_at, timezone.now())

    def test_remove_from_blitz_keeps_the_card(self):
        c = self.card()
        self.client.post(reverse('web:blitz_remove'), {'card': c.uuid})
        c.refresh_from_db()
        self.assertFalse(c.in_pool)

    def test_undo_only_the_last_web_answer(self):
        c = self.card()
        self.client.post(reverse('web:blitz_answer'), {'card': c.uuid, 'correct': '1'})
        self.client.post(reverse('web:blitz_undo'))
        c.refresh_from_db()
        self.assertEqual(c.correct_count, 0)
        self.assertFalse(ReviewLog.objects.exists())
        self.client.post(reverse('web:blitz_undo'))  # nothing left to undo: no error

    def test_filter_by_own_and_added_topic(self):
        mine = Collection.objects.create(owner=self.alice, name='Mine')
        theirs = Collection.objects.create(owner=self.bob, name='Theirs', visibility='public')
        self.card(question='in mine', collection=mine)
        self.card(question='copy of theirs', source_collection=theirs)
        self.card(question='other')
        q = self.client.get(reverse('web:blitz'), {'t': [str(theirs.uuid)]}).context['card'].question
        self.assertEqual(q, 'copy of theirs')
        q = self.client.get(reverse('web:blitz') + f'?t={mine.uuid}').context['card'].question
        self.assertEqual(q, 'in mine')

    def test_cannot_answer_someone_elses_card(self):
        c = self.card(user=self.bob)
        self.assertEqual(self.client.post(reverse('web:blitz_answer'), {'card': c.uuid, 'correct': '1'}).status_code, 404)
        self.assertEqual(self.client.post(reverse('web:blitz_answer'), {'card': 'junk', 'correct': '1'}).status_code, 404)


class AddCardTests(WebTestCase):
    def test_add_stays_open_and_remembers_topic(self):
        topic = Collection.objects.create(owner=self.alice, name='T')
        r = self.client.post(reverse('web:add'), {'question': 'Q', 'answer': 'A', 'topic': str(topic.uuid)})
        self.assertRedirects(r, reverse('web:add'))
        card = Card.objects.get(question='Q')
        self.assertEqual((card.collection, card.in_pool), (topic, True))
        self.assertEqual(self.client.get(reverse('web:add')).context['topic_uuid'], str(topic.uuid))

    def test_add_from_blitz_returns_to_blitz(self):
        r = self.client.post(reverse('web:add'), {'question': 'Q', 'answer': 'A', 'next': '/blitz/'})
        self.assertRedirects(r, '/blitz/', fetch_redirect_response=False)

    def test_duplicate_and_empty_are_refused(self):
        self.card(question='Q')
        self.assertTrue(self.client.post(reverse('web:add'), {'question': 'Q', 'answer': 'A'}).context['error'])
        self.client.post(reverse('web:add'), {'question': '', 'answer': 'A'})
        self.assertEqual(Card.objects.count(), 1)

    def test_cards_list_shows_blitz_only(self):
        self.card(question='in')
        self.card(question='out', in_pool=False)
        rows = self.client.get(reverse('web:cards')).context['rows']
        self.assertEqual([r['question'] for r in rows], ['in'])


class SimpleStudyTests(WebTestCase):
    def setUp(self):
        super().setUp()
        self.topic = Collection.objects.create(owner=self.alice, name='T')
        self.c1 = self.card(collection=self.topic)
        self.c2 = self.card(collection=self.topic)

    def answer(self, correct):
        play = self.client.get(reverse('web:simple_play', args=[self.topic.uuid])).context
        self.client.post(reverse('web:simple_answer', args=[self.topic.uuid]), {'card': play['card'].uuid, 'correct': '1' if correct else '0'})

    def test_cycle_round_by_round_without_touching_blitz(self):
        self.client.get(reverse('web:simple_topic', args=[self.topic.uuid]))  # starts round 1
        self.answer(True)
        self.answer(False)
        run = TopicRun.objects.get()
        self.assertEqual((run.queue, len(run.wrong)), ([], 1))
        self.client.post(reverse('web:simple_next', args=[self.topic.uuid]))
        run.refresh_from_db()
        self.assertEqual((run.round, len(run.queue)), (2, 1))
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.correct_count, 0)
        self.assertFalse(ReviewLog.objects.exists())

    def test_reopening_asks_continue_or_restart(self):
        self.client.get(reverse('web:simple_topic', args=[self.topic.uuid]))
        self.answer(True)
        r = self.client.get(reverse('web:simple_topic', args=[self.topic.uuid]))
        self.assertTemplateUsed(r, 'web/simple_choose.html')
        self.client.post(reverse('web:simple_restart', args=[self.topic.uuid]))
        self.assertEqual(len(TopicRun.objects.get().queue), 2)

    def test_added_topic_can_be_studied_foreign_not(self):
        theirs = Collection.objects.create(owner=self.bob, name='B', visibility='public')
        self.card(user=self.bob, collection=theirs)
        self.assertEqual(self.client.get(reverse('web:simple_topic', args=[theirs.uuid])).status_code, 404)
        TopicSubscription.objects.create(user=self.alice, collection=theirs)
        self.assertEqual(self.client.get(reverse('web:simple_topic', args=[theirs.uuid])).status_code, 302)


class LibraryTests(WebTestCase):
    def setUp(self):
        super().setUp()
        self.theirs = Collection.objects.create(owner=self.bob, name='Physik', visibility='public', tags=['physics'])
        self.k1 = self.card(user=self.bob, collection=self.theirs, question='Ohm')
        self.k2 = self.card(user=self.bob, collection=self.theirs, question='Joule')
        self.mine = Collection.objects.create(owner=self.alice, name='Mine')

    def act(self, source, action, cards, **extra):
        return self.client.post(reverse('web:topic_action'), {'source': source, 'action': action,
                                                              'cards': [str(c.uuid) for c in cards], **extra})

    def test_browse_search_by_tag_and_author(self):
        self.assertEqual(len(self.client.get(reverse('web:browse'), {'q': 'physics'}).context['rows']), 1)
        self.assertEqual(len(self.client.get(reverse('web:browse'), {'q': 'chemie'}).context['rows']), 0)
        self.assertContains(self.client.get(reverse('web:author', args=['bob'])), 'Physik')

    def test_private_foreign_topic_is_hidden_unlisted_by_link_works(self):
        self.theirs.visibility = 'private'
        self.theirs.save()
        self.assertEqual(self.client.get(reverse('web:topic', args=[self.theirs.share_token])).status_code, 404)
        self.theirs.visibility = 'unlisted'
        self.theirs.save()
        self.assertEqual(self.client.get(reverse('web:topic', args=[self.theirs.share_token])).status_code, 200)

    def test_subscribe_toggle(self):
        url = reverse('web:subscribe', args=[self.theirs.share_token])
        self.client.post(url)
        self.assertTrue(TopicSubscription.objects.filter(user=self.alice).exists())
        self.client.post(url)
        self.assertFalse(TopicSubscription.objects.exists())

    def test_foreign_cards_to_blitz_then_conflict_dialog(self):
        self.act(str(self.theirs.share_token), 'to_blitz', [self.k1])
        copy = Card.objects.get(user=self.alice, source_card=self.k1)
        copy.correct_count = 2
        copy.save()
        r = self.act(str(self.theirs.share_token), 'to_blitz', [self.k1, self.k2])
        self.assertTemplateUsed(r, 'web/conflict.html')
        self.act(str(self.theirs.share_token), 'to_blitz', [self.k1, self.k2], confirm='1', **{f'choice-{self.k1.uuid}': 'reset'})
        copy.refresh_from_db()
        self.assertEqual(copy.correct_count, 0)
        self.assertEqual(Card.objects.filter(user=self.alice).count(), 2)

    def test_own_deck_actions(self):
        a = self.card(collection=self.mine, in_pool=False)
        b = self.card(collection=self.mine)
        self.act(str(self.mine.share_token), 'to_blitz', [a])
        a.refresh_from_db()
        self.assertTrue(a.in_pool)
        other = Collection.objects.create(owner=self.alice, name='Other')
        self.act(str(self.mine.share_token), 'copy', [b], target=str(other.uuid))
        self.assertFalse(Card.objects.get(collection=other).in_pool)
        self.act(str(self.mine.share_token), 'move', [b], target=str(other.uuid))
        b.refresh_from_db()
        self.assertEqual(b.collection, other)
        self.act(str(self.mine.share_token), 'from_deck', [a])
        a.refresh_from_db()
        self.assertIsNone(a.collection)
        self.act('none', 'delete', [a])
        self.assertFalse(Card.objects.filter(pk=a.pk).exists())

    def test_cannot_move_or_delete_foreign_cards(self):
        self.assertEqual(self.act(str(self.theirs.share_token), 'move', [self.k1], target='none').status_code, 404)
        self.assertEqual(self.act(str(self.theirs.share_token), 'delete', [self.k1]).status_code, 404)
        self.assertEqual(self.act('junk', 'to_blitz', [self.k1]).status_code, 404)
        self.assertTrue(Card.objects.filter(pk=self.k1.pk).exists())

    def test_create_and_edit_topic(self):
        self.client.post(reverse('web:topic_new'), {'name': 'Neu', 'description': 'd', 'tags': 'a, b, a', 'visibility': 'public'})
        topic = Collection.objects.get(name='Neu')
        self.assertEqual((topic.tags, topic.visibility), (['a', 'b'], 'public'))
        self.client.post(reverse('web:topic_edit', args=[topic.share_token]), {'name': 'Neu2', 'visibility': 'bogus'})
        topic.refresh_from_db()
        self.assertEqual((topic.name, topic.visibility), ('Neu2', 'private'))
        self.assertEqual(self.client.get(reverse('web:topic_edit', args=[self.theirs.share_token])).status_code, 404)

    def test_card_edit_reset_delete(self):
        c = self.card(collection=self.mine, correct_count=2)
        url = reverse('web:card', args=[c.uuid])
        self.client.post(url, {'op': 'save', 'question': 'Q2', 'answer': 'A2'})
        self.client.post(url, {'op': 'blitz'})
        c.refresh_from_db()
        self.assertEqual((c.question, c.correct_count), ('Q2', 0))
        self.client.post(url, {'op': 'delete'})
        self.assertFalse(Card.objects.filter(pk=c.pk).exists())
        self.assertEqual(self.client.get(reverse('web:card', args=[self.k1.uuid])).status_code, 404)


class ProfileTests(WebTestCase):
    def test_stats_export_and_account(self):
        self.card(question='Frage, mit "Komma"', stage=6)
        r = self.client.get(reverse('web:profile'))
        self.assertEqual((r.context['total'], r.context['learned']), (1, 1))
        csv = self.client.get(reverse('web:export')).content.decode('utf-8-sig')
        self.assertIn('"Frage, mit ""Komma"""', csv)
        r = self.client.post(reverse('web:account'), {'current_password': 'wrong', 'nickname': 'alicia'})
        self.assertEqual(len(r.context['errors']), 1)
        self.client.post(reverse('web:account'), {'current_password': 'pw12345', 'nickname': 'alicia', 'new_password': 'n3w-Passw0rd!'})
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.profile.nickname, 'alicia')
        self.assertTrue(self.alice.check_password('n3w-Passw0rd!'))
        self.assertEqual(self.client.get(reverse('web:profile')).status_code, 200)  # still logged in
