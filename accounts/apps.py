import os
from django.apps import AppConfig
from django.conf import settings


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        self._ensure_database()

    @staticmethod
    def _ensure_database():
        """
        On startup, ensure the database/ directory exists.
        If the SQLite file does not exist, automatically run migrations.
        """
        import warnings
        db_dir = settings.DATABASE_DIR
        db_path = settings.DATABASE_PATH

        # Always ensure the directory exists
        os.makedirs(db_dir, exist_ok=True)

        if not os.path.exists(db_path):
            # Run migrations programmatically
            from django.core.management import call_command
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                call_command('migrate', '--run-syncdb', verbosity=0)
