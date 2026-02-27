"""
Django management command to check and install dependencies.

Usage:
    python manage.py checkdeps            # Check & auto-install
    python manage.py checkdeps --dry-run  # Check only, don't install
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Memeriksa dan menginstall dependensi yang dibutuhkan '
        'oleh Cobrell Bell Scheduler (pygame, mutagen, audio tools).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Hanya periksa dependensi tanpa menginstall',
        )

    def handle(self, *args, **options):
        from dashboard.deps import check_and_install_dependencies

        def writer(msg):
            self.stdout.write(msg)

        result = check_and_install_dependencies(
            stdout_writer=writer,
            auto_install=not options['dry_run'],
        )

        self.stdout.write('')
        if result['ready']:
            self.stdout.write(self.style.SUCCESS(
                'Semua dependensi siap! Jalankan: python manage.py runscheduler'
            ))
        else:
            self.stderr.write(self.style.ERROR(
                'Ada dependensi yang belum terpenuhi. Lihat pesan di atas.'
            ))
