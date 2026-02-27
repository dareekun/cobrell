"""
Django management command to run the bell scheduler.

Usage:
    python manage.py runscheduler

This will start a long-running process that checks the schedule every second
and plays audio files through the default audio output (3.5 mm jack on RPi)
when a bell is due.

On first run, it automatically checks and installs missing dependencies
(pygame, mutagen, and system audio tools on Linux/RPi).

For production on Raspberry Pi, run this as a systemd service.
"""

import logging

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Menjalankan scheduler bel otomatis. '
        'Memainkan file audio sesuai jadwal melalui audio output (3.5 mm jack).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose', '-v',
            action='count',
            default=1,
            help='Tingkat verbosity (gunakan -vv untuk debug)',
        )
        parser.add_argument(
            '--skip-deps',
            action='store_true',
            default=False,
            help='Lewati pemeriksaan dependensi saat startup',
        )
        parser.add_argument(
            '--no-auto-install',
            action='store_true',
            default=False,
            help='Hanya periksa dependensi, jangan install otomatis',
        )

    def handle(self, *args, **options):
        # Configure logging
        verbosity = options['verbosity']
        level = {0: logging.WARNING, 1: logging.INFO}.get(verbosity, logging.DEBUG)

        logging.basicConfig(
            level=level,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )

        # Also set Django's logger
        logging.getLogger('cobrell.scheduler').setLevel(level)

        # ----------------------------------------------------------
        # Step 1: Check & install dependencies
        # ----------------------------------------------------------
        if not options['skip_deps']:
            from dashboard.deps import check_and_install_dependencies

            def writer(msg):
                self.stdout.write(msg)

            dep_result = check_and_install_dependencies(
                stdout_writer=writer,
                auto_install=not options['no_auto_install'],
            )

            if not dep_result['ready']:
                self.stderr.write(self.style.ERROR(
                    '\nScheduler tidak dapat dimulai karena dependensi belum terpenuhi.\n'
                    'Periksa pesan error di atas dan install secara manual, atau jalankan:\n'
                    '  python manage.py runscheduler\n'
                    'untuk mencoba auto-install lagi.\n'
                ))
                return
            self.stdout.write('')  # blank line
        else:
            self.stdout.write(self.style.WARNING(
                'Pemeriksaan dependensi dilewati (--skip-deps)\n'
            ))

        # ----------------------------------------------------------
        # Step 2: Start the scheduler
        # ----------------------------------------------------------
        from dashboard.scheduler import BellScheduler

        self.stdout.write(self.style.SUCCESS(
            'Memulai Cobrell Bell Scheduler...\n'
            'Tekan Ctrl+C untuk menghentikan.\n'
        ))

        scheduler = BellScheduler()
        scheduler.start()

        self.stdout.write(self.style.WARNING('Scheduler dihentikan.'))
