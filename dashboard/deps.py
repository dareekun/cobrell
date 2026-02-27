"""
Dependency checker & auto-installer for Cobrell Bell Scheduler.

Checks for required Python packages and system-level audio tools,
and installs any that are missing.
"""

import os
import sys
import subprocess
import shutil
import logging

logger = logging.getLogger('cobrell.scheduler')


# ---------------------------------------------------------------------------
# Python package requirements
# ---------------------------------------------------------------------------

REQUIRED_PYTHON_PACKAGES = [
    # (import_name, pip_name, min_version_or_None)
    ('pygame', 'pygame', '2.5.0'),
    ('mutagen', 'mutagen', '1.47.0'),
]


# ---------------------------------------------------------------------------
# System-level audio tools (Linux / Raspberry Pi)
# ---------------------------------------------------------------------------

LINUX_AUDIO_PACKAGES = [
    # (binary_name, apt_package_name, description)
    ('aplay', 'alsa-utils', 'ALSA audio playback utility'),
    ('amixer', 'alsa-utils', 'ALSA mixer control'),
]

LINUX_SDL_PACKAGES = [
    # Required for pygame audio on Linux/RPi
    'libsdl2-mixer-2.0-0',
    'libsdl2-2.0-0',
]


def _is_raspberry_pi():
    """Detect if running on a Raspberry Pi."""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            return 'raspberry pi' in f.read().lower()
    except (FileNotFoundError, PermissionError):
        return False


def _pip_install(package_spec: str, stdout_writer=None):
    """Install a Python package using pip."""
    cmd = [sys.executable, '-m', 'pip', 'install', package_spec]
    msg = f'  → pip install {package_spec} ...'
    logger.info(msg)
    if stdout_writer:
        stdout_writer(msg)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            ok = f'  ✓ {package_spec} berhasil diinstall'
            logger.info(ok)
            if stdout_writer:
                stdout_writer(ok)
            return True
        else:
            err = f'  ✗ Gagal install {package_spec}: {result.stderr.strip()}'
            logger.error(err)
            if stdout_writer:
                stdout_writer(err)
            return False
    except subprocess.TimeoutExpired:
        err = f'  ✗ Timeout saat install {package_spec}'
        logger.error(err)
        if stdout_writer:
            stdout_writer(err)
        return False


def _apt_install(packages: list[str], stdout_writer=None):
    """Install system packages using apt (Linux only)."""
    if not shutil.which('apt-get'):
        return False

    cmd = ['sudo', 'apt-get', 'install', '-y'] + packages
    msg = f'  → sudo apt-get install -y {" ".join(packages)} ...'
    logger.info(msg)
    if stdout_writer:
        stdout_writer(msg)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            ok = f'  ✓ System packages berhasil diinstall'
            logger.info(ok)
            if stdout_writer:
                stdout_writer(ok)
            return True
        else:
            err = f'  ✗ Gagal install system packages: {result.stderr.strip()}'
            logger.error(err)
            if stdout_writer:
                stdout_writer(err)
            return False
    except subprocess.TimeoutExpired:
        err = f'  ✗ Timeout saat install system packages'
        logger.error(err)
        if stdout_writer:
            stdout_writer(err)
        return False


def _check_python_package(import_name: str):
    """Check if a Python package is importable. Returns True if available."""
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False


def _check_apt_package_installed(package_name: str):
    """Check if an apt package is installed (Linux only)."""
    if not shutil.which('dpkg'):
        return True  # Can't check, assume OK
    try:
        result = subprocess.run(
            ['dpkg', '-s', package_name],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return True  # Can't check, assume OK


def check_and_install_dependencies(stdout_writer=None, auto_install=True):
    """
    Check all required dependencies and install missing ones.

    Args:
        stdout_writer: Optional callable(str) for writing status messages.
        auto_install: If True, automatically install missing packages.

    Returns:
        dict with keys:
            'ready': bool — True if all critical deps are available
            'installed': list of newly installed packages
            'failed': list of packages that failed to install
            'warnings': list of non-critical warning messages
    """
    result = {
        'ready': True,
        'installed': [],
        'failed': [],
        'warnings': [],
    }

    def _log(msg):
        logger.info(msg)
        if stdout_writer:
            stdout_writer(msg)

    _log('─' * 50)
    _log('Memeriksa dependensi Cobrell Bell Scheduler...')
    _log('─' * 50)

    # ==========================================================
    # 1) Check & install SYSTEM dependencies first
    #    (needed before Python packages like pygame)
    # ==========================================================
    _log('\n[1/3] Memeriksa audio tools & library sistem...')

    if sys.platform == 'linux':
        missing_apt = []

        # Check audio binaries
        for binary, apt_pkg, desc in LINUX_AUDIO_PACKAGES:
            if shutil.which(binary):
                _log(f'  ✓ {binary} ({desc}) — tersedia')
            else:
                _log(f'  ✗ {binary} ({desc}) — TIDAK DITEMUKAN')
                if apt_pkg not in missing_apt:
                    missing_apt.append(apt_pkg)

        # Check SDL2 libraries (required for pygame)
        for sdl_pkg in LINUX_SDL_PACKAGES:
            if _check_apt_package_installed(sdl_pkg):
                _log(f'  ✓ {sdl_pkg} — tersedia')
            else:
                _log(f'  ✗ {sdl_pkg} — TIDAK DITEMUKAN')
                if sdl_pkg not in missing_apt:
                    missing_apt.append(sdl_pkg)

        # Also need SDL2 dev headers to build pygame from source
        sdl_dev_pkgs = ['libsdl2-dev', 'libsdl2-image-dev', 'libsdl2-mixer-dev',
                        'libsdl2-ttf-dev', 'libfreetype6-dev']
        for devpkg in sdl_dev_pkgs:
            if not _check_apt_package_installed(devpkg):
                if devpkg not in missing_apt:
                    missing_apt.append(devpkg)

        if missing_apt and auto_install:
            _log('  → Mengupdate apt cache...')
            try:
                subprocess.run(
                    ['sudo', 'apt-get', 'update', '-qq'],
                    capture_output=True, text=True, timeout=120,
                )
            except Exception:
                pass

            if _apt_install(missing_apt, stdout_writer):
                result['installed'].extend(missing_apt)
            else:
                result['failed'].extend(missing_apt)
                result['warnings'].append(
                    f'Gagal install system packages: {", ".join(missing_apt)}. '
                    f'Jalankan manual: sudo apt-get install -y {" ".join(missing_apt)}'
                )
        elif missing_apt:
            result['warnings'].append(
                f'System packages yang perlu diinstall: {", ".join(missing_apt)}. '
                f'Jalankan: sudo apt-get install -y {" ".join(missing_apt)}'
            )

    elif sys.platform == 'darwin':
        # macOS — need SDL2 for pygame
        if shutil.which('afplay'):
            _log('  ✓ afplay (macOS audio) — tersedia')
        else:
            _log('  ⚠ afplay tidak ditemukan')

        # Check if SDL2 is available (needed for pygame build)
        sdl2_available = (
            os.path.exists('/opt/homebrew/include/SDL2')
            or os.path.exists('/usr/local/include/SDL2')
            or _check_python_package('pygame')  # already built = OK
        )
        if not sdl2_available and auto_install and shutil.which('brew'):
            _log('  ✗ SDL2 — TIDAK DITEMUKAN (dibutuhkan untuk pygame)')
            _log('  → brew install sdl2 sdl2_mixer sdl2_image sdl2_ttf ...')
            try:
                subprocess.run(
                    ['brew', 'install', 'sdl2', 'sdl2_mixer', 'sdl2_image', 'sdl2_ttf'],
                    capture_output=True, text=True, timeout=300,
                )
                _log('  ✓ SDL2 berhasil diinstall via Homebrew')
                result['installed'].append('sdl2 (brew)')
            except Exception as e:
                _log(f'  ⚠ Gagal install SDL2 via Homebrew: {e}')
                result['warnings'].append(
                    'SDL2 gagal diinstall. Jalankan manual: brew install sdl2 sdl2_mixer sdl2_image sdl2_ttf'
                )
        elif not sdl2_available and not shutil.which('brew'):
            result['warnings'].append(
                'SDL2 tidak ditemukan dan Homebrew tidak tersedia. '
                'Install Homebrew lalu: brew install sdl2 sdl2_mixer sdl2_image sdl2_ttf'
            )
    else:
        _log(f'  ⚠ Platform "{sys.platform}" — pastikan audio output berfungsi')

    # ==========================================================
    # 2) Check & install Python packages
    # ==========================================================
    _log('\n[2/3] Memeriksa Python packages...')

    for import_name, pip_name, min_version in REQUIRED_PYTHON_PACKAGES:
        if _check_python_package(import_name):
            _log(f'  ✓ {pip_name} — tersedia')
        else:
            _log(f'  ✗ {pip_name} — TIDAK DITEMUKAN')
            if auto_install:
                pip_spec = f'{pip_name}>={min_version}' if min_version else pip_name
                if _pip_install(pip_spec, stdout_writer):
                    result['installed'].append(pip_name)
                    # Verify it actually works now
                    if not _check_python_package(import_name):
                        result['failed'].append(pip_name)
                        result['warnings'].append(
                            f'{pip_name} terinstall tapi gagal diimport. '
                            f'Mungkin perlu system library tambahan.'
                        )
                else:
                    result['failed'].append(pip_name)
            else:
                result['failed'].append(pip_name)

    # ==========================================================
    # 3) Verify audio output capability
    # ==========================================================
    _log('\n[3/3] Memeriksa kemampuan audio playback...')

    audio_ok = False

    # Try pygame
    if _check_python_package('pygame'):
        try:
            import pygame
            pygame.mixer.init()
            pygame.mixer.quit()
            _log('  ✓ pygame.mixer — siap digunakan')
            audio_ok = True
        except Exception as e:
            _log(f'  ⚠ pygame.mixer gagal init: {e}')
            result['warnings'].append(
                f'pygame.mixer tidak bisa diinisialisasi: {e}. '
                f'Akan menggunakan fallback (aplay/mpg123/ffplay).'
            )

    # Check fallback players
    fallback_players = {
        'darwin': ['afplay'],
        'linux': ['aplay', 'mpg123', 'ffplay', 'cvlc'],
    }
    available = fallback_players.get(sys.platform, [])
    found_fallback = []
    for player in available:
        if shutil.which(player):
            found_fallback.append(player)

    if found_fallback:
        _log(f'  ✓ Fallback player tersedia: {", ".join(found_fallback)}')
        audio_ok = True

    if not audio_ok:
        result['ready'] = False
        result['warnings'].append(
            'TIDAK ADA audio player yang tersedia! '
            'Install pygame atau salah satu: mpg123, ffplay, vlc'
        )

    # Check Raspberry Pi specifics
    if _is_raspberry_pi():
        _log('\n  🍓 Raspberry Pi terdeteksi!')
        _log('  → Audio output akan diatur ke 3.5 mm jack')

    # ==========================================================
    # Summary
    # ==========================================================
    _log('\n' + '─' * 50)
    if result['installed']:
        _log(f'Baru diinstall: {", ".join(result["installed"])}')
    if result['failed']:
        _log(f'GAGAL diinstall: {", ".join(result["failed"])}')
        result['ready'] = False
    if result['warnings']:
        for w in result['warnings']:
            _log(f'⚠  {w}')

    # pygame is critical — if it failed AND no fallback, not ready
    if 'pygame' in result['failed'] and not found_fallback:
        result['ready'] = False

    if result['ready']:
        _log('✓ Semua dependensi siap!')
    else:
        _log('✗ Ada dependensi yang belum terpenuhi.')

    _log('─' * 50)

    return result
