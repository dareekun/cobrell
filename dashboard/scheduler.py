"""
Bell Scheduler — plays audio files at scheduled times.

Works on:
  - Desktop (macOS / Linux) with standard audio output
  - Raspberry Pi via 3.5 mm audio jack

Usage:
  python manage.py runscheduler
"""

import os
import sys
import time
import signal
import logging
import threading
from datetime import date, datetime, timedelta

import django
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('cobrell.scheduler')

# ---------------------------------------------------------------------------
# Audio playback backend
# ---------------------------------------------------------------------------

_current_player_lock = threading.Lock()
_current_playback_thread: threading.Thread | None = None
_stop_playback = threading.Event()
_current_playing_name: str = ''  # nama musik yang sedang diputar


def is_playing() -> bool:
    """Return True if audio is currently being played."""
    return (
        _current_playback_thread is not None
        and _current_playback_thread.is_alive()
    )


def get_playback_status() -> dict:
    """Return current playback status as a dict."""
    playing = is_playing()
    return {
        'is_playing': playing,
        'current_name': _current_playing_name if playing else '',
    }


def _play_with_pygame(file_path: str):
    """Play audio using pygame.mixer (preferred, supports MP3/OGG/WAV)."""
    import pygame

    pygame.mixer.init()
    try:
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        # Wait for playback to finish or stop signal
        while pygame.mixer.music.get_busy():
            if _stop_playback.is_set():
                pygame.mixer.music.stop()
                break
            time.sleep(0.1)
    finally:
        pygame.mixer.music.stop()
        pygame.mixer.quit()


def _play_with_subprocess(file_path: str):
    """
    Fallback: play audio via system command.
    - Linux/RPi: aplay (WAV) or mpg123/ffplay
    - macOS: afplay
    """
    import subprocess
    import shutil

    ext = os.path.splitext(file_path)[1].lower()

    if sys.platform == 'darwin':
        cmd = ['afplay', file_path]
    elif ext == '.wav' and shutil.which('aplay'):
        cmd = ['aplay', file_path]
    elif ext == '.mp3' and shutil.which('mpg123'):
        cmd = ['mpg123', '-q', file_path]
    elif shutil.which('ffplay'):
        cmd = ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet', file_path]
    elif shutil.which('cvlc'):
        cmd = ['cvlc', '--play-and-exit', '--no-video', file_path]
    else:
        raise RuntimeError(
            f'Tidak ada player audio yang tersedia di sistem. '
            f'Install pygame, mpg123, ffplay, atau vlc.'
        )

    proc = subprocess.Popen(cmd)
    while proc.poll() is None:
        if _stop_playback.is_set():
            proc.terminate()
            proc.wait(timeout=5)
            break
        time.sleep(0.1)


def play_audio(file_path: str, name: str = ''):
    """
    Play an audio file through the default audio output (3.5 mm jack).
    Tries pygame first, then falls back to system commands.
    """
    global _current_playback_thread, _current_playing_name
    _stop_playback.clear()

    if not os.path.isfile(file_path):
        logger.error('File audio tidak ditemukan: %s', file_path)
        return

    def _play():
        global _current_playing_name
        logger.info('▶  Memutar: %s', file_path)
        try:
            _play_with_pygame(file_path)
        except Exception as e:
            logger.debug('pygame tidak tersedia (%s), menggunakan fallback', e)
            try:
                _play_with_subprocess(file_path)
            except Exception as e2:
                logger.error('Gagal memutar audio: %s', e2)
        _current_playing_name = ''
        logger.info('■  Selesai memutar')

    with _current_player_lock:
        # Stop any currently playing audio
        if _current_playback_thread and _current_playback_thread.is_alive():
            logger.info('Menghentikan pemutaran sebelumnya...')
            _stop_playback.set()
            _current_playback_thread.join(timeout=10)
            _stop_playback.clear()

        _current_playing_name = name or os.path.basename(file_path)
        t = threading.Thread(target=_play, daemon=True, name='audio-playback')
        t.start()
        _current_playback_thread = t


def stop_audio():
    """Stop any currently playing audio."""
    global _current_playback_thread, _current_playing_name
    with _current_player_lock:
        if _current_playback_thread and _current_playback_thread.is_alive():
            _stop_playback.set()
            _current_playback_thread.join(timeout=10)
            _current_playback_thread = None
            _current_playing_name = ''
            logger.info('Pemutaran dihentikan')


# ---------------------------------------------------------------------------
# Raspberry Pi audio output helpers
# ---------------------------------------------------------------------------

def setup_audio_output():
    """
    Configure audio output to the 3.5 mm jack on Raspberry Pi.
    On non-RPi systems this is a no-op.
    """
    import shutil
    import subprocess

    if sys.platform != 'linux':
        logger.info('Platform: %s — menggunakan audio output default', sys.platform)
        return

    # Try to force 3.5 mm jack on Raspberry Pi using raspi-config or amixer
    if shutil.which('amixer'):
        try:
            # numid=3: 0=auto, 1=3.5mm jack, 2=HDMI
            subprocess.run(
                ['amixer', 'cset', 'numid=3', '1'],
                capture_output=True, text=True, timeout=5,
            )
            logger.info('Audio output diatur ke 3.5 mm jack (amixer numid=3 → 1)')
        except Exception as e:
            logger.debug('amixer tidak dapat mengatur output: %s', e)

    # Set volume to 90%
    if shutil.which('amixer'):
        try:
            subprocess.run(
                ['amixer', 'sset', 'PCM', '90%'],
                capture_output=True, text=True, timeout=5,
            )
            logger.info('Volume diatur ke 90%%')
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Schedule checker
# ---------------------------------------------------------------------------

WEEKDAY_MAP = {
    0: 'senin', 1: 'selasa', 2: 'rabu', 3: 'kamis',
    4: 'jumat', 5: 'sabtu', 6: 'minggu',
}


def _get_due_schedules(now_local):
    """
    Return JadwalBel objects that should ring RIGHT NOW.
    Matches current weekday + current HH:MM.
    Excludes schedules that have a Pengecualian for today's date.
    """
    from dashboard.models import JadwalBel, Pengecualian

    today_key = WEEKDAY_MAP[now_local.weekday()]
    current_time_str = now_local.strftime('%H:%M')

    # Active schedules matching this day and this exact minute
    schedules = list(
        JadwalBel.objects
        .filter(
            aktif=True,
            hari=today_key,
            jam__hour=now_local.hour,
            jam__minute=now_local.minute,
        )
        .select_related('musik')
    )

    if not schedules:
        return []

    # Filter out exceptions
    today = now_local.date()
    exception_jadwal_ids = set(
        Pengecualian.objects
        .filter(tanggal=today, jadwal__in=schedules)
        .values_list('jadwal_id', flat=True)
    )

    return [s for s in schedules if s.pk not in exception_jadwal_ids]


class BellScheduler:
    """
    Main scheduler loop — checks every second if any bell should ring.
    Only triggers once per minute per schedule.
    """

    def __init__(self):
        self._running = False
        self._played_this_minute: set[int] = set()  # jadwal PKs already played
        self._last_minute: str = ''

    def start(self):
        """Start the scheduler loop (blocking)."""
        self._running = True

        # Configure audio output (RPi 3.5 mm)
        setup_audio_output()

        logger.info('=' * 60)
        logger.info('  COBRELL Bell Scheduler dimulai')
        logger.info('  Timezone: %s', settings.TIME_ZONE)
        logger.info('=' * 60)

        # Graceful shutdown
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        try:
            self._loop()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        stop_audio()
        logger.info('Scheduler dihentikan')

    def _handle_signal(self, signum, frame):
        logger.info('Signal %s diterima, menghentikan scheduler...', signum)
        self._running = False

    def _loop(self):
        while self._running:
            try:
                now = timezone.localtime(timezone.now())
                current_minute = now.strftime('%H:%M')

                # Reset played set when minute changes
                if current_minute != self._last_minute:
                    self._played_this_minute.clear()
                    self._last_minute = current_minute

                # Check for due schedules
                due = _get_due_schedules(now)
                for jadwal in due:
                    if jadwal.pk in self._played_this_minute:
                        continue

                    self._played_this_minute.add(jadwal.pk)
                    self._ring_bell(jadwal, now)

            except Exception:
                logger.exception('Error dalam scheduler loop')

            # Sleep briefly — check every 0.5 seconds for precision
            time.sleep(0.5)

    def _ring_bell(self, jadwal, now):
        """Ring the bell for a given schedule."""
        logger.info(
            '🔔  BEL! %s — %s %s (%s)',
            jadwal.nama,
            jadwal.get_hari_display(),
            jadwal.jam.strftime('%H:%M'),
            now.strftime('%H:%M:%S'),
        )

        if jadwal.musik and jadwal.musik.file:
            file_path = os.path.join(settings.MEDIA_ROOT, jadwal.musik.file.name)
            play_audio(file_path, name=f'{jadwal.nama} — {jadwal.musik.nama}')
        else:
            logger.warning(
                '   Jadwal "%s" tidak memiliki musik — bel tidak berbunyi', jadwal.nama
            )
