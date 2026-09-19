from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class NicknameOrEmailBackend(ModelBackend):
    """Log in with either the account's email address or its profile nickname.

    Plugged in alongside the default ModelBackend (see AUTHENTICATION_BACKENDS
    in settings.py) so both remain valid ways to identify an account; the
    login form's single "username" field is matched against whichever one
    the user typed.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(
                Q(email__iexact=username) | Q(profile__nickname__iexact=username),
            )
        except UserModel.DoesNotExist:
            # Run the password hasher anyway so login takes the same amount
            # of time whether or not the identifier exists (timing-attack
            # mitigation, same trick Django's own ModelBackend uses).
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
