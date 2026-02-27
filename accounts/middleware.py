import os
from django.conf import settings
from django.shortcuts import redirect
from django.contrib.auth import get_user_model


class SetupCheckMiddleware:
    """
    Middleware that checks whether the application has been set up.
    If no admin user exists yet, redirect all requests (except the
    setup/register page and static files) to the registration page.
    """

    # URLs that are always allowed (even before setup)
    ALLOWED_PATHS = ('/register/', '/static/', '/forgot-password/', '/recovery/')

    def __init__(self, get_response):
        self.get_response = get_response
        # Cache: once setup is confirmed, stop checking the DB on every request
        self._setup_done = False

    def __call__(self, request):
        if not self._setup_done:
            if self._needs_setup():
                # Allow register page and static assets through
                if not any(request.path.startswith(p) for p in self.ALLOWED_PATHS):
                    return redirect('register')
            else:
                self._setup_done = True

        return self.get_response(request)

    @staticmethod
    def _needs_setup():
        """Return True when the app has no users yet (fresh install)."""
        db_path = settings.DATABASE_PATH
        if not os.path.exists(db_path):
            return True
        User = get_user_model()
        try:
            return User.objects.count() == 0
        except Exception:
            # Table might not exist yet
            return True
