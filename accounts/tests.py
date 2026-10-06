from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from cards.models import Card
from cards.scheduler import MAX_STAGE

from .forms import EmailRegisterForm
from .models import Friendship, Profile


def _make_card(user, stage=0, question='q'):
    """Helper: create a Card for `user` at a given stage (used to make the
    user "learn" cards so their level goes up)."""
    return Card.objects.create(user=user, question=question, answer='a', stage=stage)


def _make_user(username, nickname, email=None, password='pw12345'):
    """Helper: create a User with a Profile/nickname attached, the way the
    real registration flow does."""
    user = User.objects.create_user(username, email=email or f'{username}@example.com', password=password)
    Profile.objects.create(user=user, nickname=nickname)
    return user


class FriendshipModelTests(TestCase):
    """Tests for the Friendship model itself: the symmetric helpers and the
    database constraints that keep the data consistent."""

    def setUp(self):
        self.alice = _make_user('alice', 'Alice')
        self.bob = _make_user('bob', 'Bobby')
        self.carol = _make_user('carol', 'Carol')

    def test_are_friends_is_false_before_any_request(self):
        self.assertFalse(Friendship.are_friends(self.alice, self.bob))

    def test_are_friends_is_false_while_request_is_pending(self):
        Friendship.objects.create(from_user=self.alice, to_user=self.bob)
        self.assertFalse(Friendship.are_friends(self.alice, self.bob))

    def test_are_friends_is_true_once_accepted_and_symmetric(self):
        Friendship.objects.create(from_user=self.alice, to_user=self.bob, status=Friendship.STATUS_ACCEPTED)
        # Symmetric: true regardless of which user is passed first.
        self.assertTrue(Friendship.are_friends(self.alice, self.bob))
        self.assertTrue(Friendship.are_friends(self.bob, self.alice))

    def test_friends_of_includes_both_directions(self):
        # Alice sent the request to Bob, Carol sent the request to Alice --
        # both should show up in Alice's friend list.
        Friendship.objects.create(from_user=self.alice, to_user=self.bob, status=Friendship.STATUS_ACCEPTED)
        Friendship.objects.create(from_user=self.carol, to_user=self.alice, status=Friendship.STATUS_ACCEPTED)

        friends = set(Friendship.friends_of(self.alice))
        self.assertEqual(friends, {self.bob, self.carol})

    def test_friends_of_excludes_pending_and_declined(self):
        Friendship.objects.create(from_user=self.alice, to_user=self.bob)  # pending
        Friendship.objects.create(from_user=self.alice, to_user=self.carol, status=Friendship.STATUS_DECLINED)

        self.assertEqual(list(Friendship.friends_of(self.alice)), [])

    def test_pending_received_and_sent_helpers(self):
        Friendship.objects.create(from_user=self.alice, to_user=self.bob)

        self.assertEqual(list(Friendship.pending_received_by(self.bob)), [
            Friendship.objects.get(from_user=self.alice, to_user=self.bob),
        ])
        self.assertEqual(list(Friendship.pending_sent_by(self.alice)), [
            Friendship.objects.get(from_user=self.alice, to_user=self.bob),
        ])
        # Bob didn't send anything, Alice isn't waiting on anything received.
        self.assertEqual(list(Friendship.pending_sent_by(self.bob)), [])
        self.assertEqual(list(Friendship.pending_received_by(self.alice)), [])

    def test_duplicate_ordered_pair_is_rejected_by_db_constraint(self):
        Friendship.objects.create(from_user=self.alice, to_user=self.bob)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Friendship.objects.create(from_user=self.alice, to_user=self.bob)

    def test_self_friendship_is_rejected_by_db_constraint(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Friendship.objects.create(from_user=self.alice, to_user=self.alice)


class ProfileModelTests(TestCase):
    """Tests for the Profile model: the nickname that identifies a user."""

    def test_nickname_uniqueness_is_enforced_at_db_level(self):
        _make_user('alice', 'Nick')
        bob = User.objects.create_user('bob', email='bob@example.com', password='pw12345')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Profile.objects.create(user=bob, nickname='Nick')  # exact duplicate

    def test_display_name_falls_back_to_username_without_a_profile(self):
        from .models import get_display_name
        # A user created outside the registration flow (e.g. createsuperuser)
        # has no Profile -- display should still work, falling back to username.
        legacy_user = User.objects.create_user('legacy', password='pw12345')
        self.assertEqual(get_display_name(legacy_user), 'legacy')

    def test_display_name_uses_nickname_when_present(self):
        from .models import get_display_name
        alice = _make_user('alice', 'Alice')
        self.assertEqual(get_display_name(alice), 'Alice')


class EmailRegisterFormNicknameTests(TestCase):
    """Tests for the nickname field added to registration."""

    def _valid_data(self, **overrides):
        data = {
            'nickname': 'newbie',
            'email': 'newbie@example.com',
            'password1': 'a-very-strong-pw-92',
            'password2': 'a-very-strong-pw-92',
        }
        data.update(overrides)
        return data

    def test_valid_nickname_is_accepted(self):
        form = EmailRegisterForm(self._valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_nickname_too_short_is_rejected(self):
        form = EmailRegisterForm(self._valid_data(nickname='ab'))
        self.assertFalse(form.is_valid())
        self.assertIn('nickname', form.errors)

    def test_nickname_with_spaces_is_rejected(self):
        form = EmailRegisterForm(self._valid_data(nickname='has space'))
        self.assertFalse(form.is_valid())
        self.assertIn('nickname', form.errors)

    def test_duplicate_nickname_case_insensitive_is_rejected(self):
        _make_user('someone', 'TakenNick')
        form = EmailRegisterForm(self._valid_data(nickname='takennick'))
        self.assertFalse(form.is_valid())
        self.assertIn('nickname', form.errors)


class RegistrationFlowTests(TestCase):
    """End-to-end registration: nickname is captured at step one and a
    Profile is created once the email code is confirmed."""

    def test_registering_creates_a_profile_with_the_chosen_nickname(self):
        self.client.post(reverse('register'), {
            'nickname': 'freshuser',
            'email': 'fresh@example.com',
            'password1': 'a-very-strong-pw-92',
            'password2': 'a-very-strong-pw-92',
        })
        code = mail.outbox[-1].body.split('confirmation code: ')[1].split('\n')[0]

        self.client.post(reverse('verify_email'), {'code': code})

        user = User.objects.get(email='fresh@example.com')
        self.assertEqual(user.profile.nickname, 'freshuser')


class AuthenticationBackendTests(TestCase):
    """Login must accept either the account's email or its nickname."""

    def setUp(self):
        self.user = _make_user('loginuser', 'CoolNick', email='login@example.com', password='pw12345')

    def test_authenticate_with_email(self):
        self.assertEqual(authenticate(username='login@example.com', password='pw12345'), self.user)

    def test_authenticate_with_nickname(self):
        self.assertEqual(authenticate(username='CoolNick', password='pw12345'), self.user)

    def test_authenticate_with_nickname_is_case_insensitive(self):
        self.assertEqual(authenticate(username='coolnick', password='pw12345'), self.user)

    def test_authenticate_with_wrong_password_fails(self):
        self.assertIsNone(authenticate(username='CoolNick', password='wrong'))

    def test_authenticate_with_unknown_identifier_fails(self):
        self.assertIsNone(authenticate(username='nobody', password='pw12345'))

    def test_login_view_accepts_nickname(self):
        response = self.client.post(reverse('login'), {'username': 'CoolNick', 'password': 'pw12345'})
        self.assertRedirects(response, reverse('home'))

    def test_login_view_accepts_email(self):
        response = self.client.post(reverse('login'), {'username': 'login@example.com', 'password': 'pw12345'})
        self.assertRedirects(response, reverse('home'))


class FriendsViewTests(TestCase):
    """Tests for the friend-request/list views reachable from the UI."""

    def setUp(self):
        self.alice = _make_user('alice', 'Alice', email='alice@example.com')
        self.bob = _make_user('bob', 'Bobby', email='bob@example.com')
        self.client.login(username='alice', password='pw12345')

    def test_friends_page_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('friends'))
        self.assertNotEqual(response.status_code, 200)  # redirected to login

    def test_sending_a_friend_request_by_nickname(self):
        response = self.client.post(reverse('friends'), {'identifier': 'Bobby'})
        self.assertRedirects(response, reverse('friends'))
        friendship = Friendship.objects.get(from_user=self.alice, to_user=self.bob)
        self.assertEqual(friendship.status, Friendship.STATUS_PENDING)

    def test_sending_a_friend_request_by_nickname_is_case_insensitive(self):
        response = self.client.post(reverse('friends'), {'identifier': 'bobby'})
        self.assertRedirects(response, reverse('friends'))
        self.assertTrue(Friendship.objects.filter(from_user=self.alice, to_user=self.bob).exists())

    def test_sending_a_friend_request_by_email(self):
        response = self.client.post(reverse('friends'), {'identifier': 'bob@example.com'})
        self.assertRedirects(response, reverse('friends'))
        self.assertTrue(Friendship.objects.filter(from_user=self.alice, to_user=self.bob).exists())

    def test_cannot_send_friend_request_to_self(self):
        response = self.client.post(reverse('friends'), {'identifier': 'Alice'})
        self.assertEqual(response.status_code, 200)  # re-renders the form with an error
        self.assertFalse(Friendship.objects.exists())

    def test_cannot_send_friend_request_to_unknown_identifier(self):
        response = self.client.post(reverse('friends'), {'identifier': 'ghost'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Friendship.objects.exists())

    def test_cannot_send_duplicate_pending_request(self):
        Friendship.objects.create(from_user=self.alice, to_user=self.bob)
        response = self.client.post(reverse('friends'), {'identifier': 'Bobby'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Friendship.objects.count(), 1)

    def test_resending_after_a_decline_reactivates_the_same_row_as_pending(self):
        declined = Friendship.objects.create(
            from_user=self.alice, to_user=self.bob, status=Friendship.STATUS_DECLINED,
        )
        self.client.post(reverse('friends'), {'identifier': 'Bobby'})

        declined.refresh_from_db()
        self.assertEqual(declined.status, Friendship.STATUS_PENDING)
        # Still exactly one row for this pair -- no unique constraint clash.
        self.assertEqual(Friendship.objects.count(), 1)

    def test_accepting_a_request_makes_the_users_friends(self):
        friendship = Friendship.objects.create(from_user=self.bob, to_user=self.alice)
        response = self.client.post(reverse('friend_request_accept', args=[friendship.pk]))
        self.assertRedirects(response, reverse('friends'))
        friendship.refresh_from_db()
        self.assertEqual(friendship.status, Friendship.STATUS_ACCEPTED)
        self.assertTrue(Friendship.are_friends(self.alice, self.bob))

    def test_only_the_recipient_can_accept_a_request(self):
        # Alice sent the request to Bob, so Alice may not accept it herself.
        friendship = Friendship.objects.create(from_user=self.alice, to_user=self.bob)
        response = self.client.post(reverse('friend_request_accept', args=[friendship.pk]))
        self.assertEqual(response.status_code, 404)
        friendship.refresh_from_db()
        self.assertEqual(friendship.status, Friendship.STATUS_PENDING)

    def test_declining_a_request_marks_it_declined_not_friends(self):
        friendship = Friendship.objects.create(from_user=self.bob, to_user=self.alice)
        self.client.post(reverse('friend_request_decline', args=[friendship.pk]))
        friendship.refresh_from_db()
        self.assertEqual(friendship.status, Friendship.STATUS_DECLINED)
        self.assertFalse(Friendship.are_friends(self.alice, self.bob))

    def test_removing_an_accepted_friendship_deletes_it(self):
        friendship = Friendship.objects.create(
            from_user=self.alice, to_user=self.bob, status=Friendship.STATUS_ACCEPTED,
        )
        response = self.client.post(reverse('friend_remove', args=[friendship.pk]))
        self.assertRedirects(response, reverse('friends'))
        self.assertFalse(Friendship.objects.filter(pk=friendship.pk).exists())

    def test_either_side_can_remove_the_friendship(self):
        # Bob (the request recipient) should also be able to remove it, not
        # just Alice (who originally sent it).
        friendship = Friendship.objects.create(
            from_user=self.alice, to_user=self.bob, status=Friendship.STATUS_ACCEPTED,
        )
        self.client.logout()
        self.client.login(username='bob', password='pw12345')
        response = self.client.post(reverse('friend_remove', args=[friendship.pk]))
        self.assertRedirects(response, reverse('friends'))
        self.assertFalse(Friendship.objects.filter(pk=friendship.pk).exists())

    def test_friends_list_shows_each_friends_nickname_and_level(self):
        # Bob has mastered enough cards to be level 2 (see cards/progress.py:
        # LEVEL_SIZE = 5 mastered cards per level).
        for i in range(5):
            _make_card(self.bob, stage=MAX_STAGE, question=f'bob-q{i}')
        Friendship.objects.create(from_user=self.alice, to_user=self.bob, status=Friendship.STATUS_ACCEPTED)

        response = self.client.get(reverse('friends'))
        self.assertEqual(response.status_code, 200)
        entry = response.context['friends'][0]
        self.assertEqual(entry['user'], self.bob)
        self.assertEqual(entry['nickname'], 'Bobby')
        self.assertEqual(entry['progress']['level'], 2)
        self.assertContains(response, 'Bobby')
        self.assertContains(response, 'Level 2')
