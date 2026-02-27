import os
import math
import calendar as cal_mod
from collections import OrderedDict
from datetime import datetime, timedelta, time as dt_time, date as dt_date
from urllib.parse import quote, unquote

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from django.utils import timezone
from django.conf import settings

from .models import JadwalBel, Musik, Pengecualian

# Audio formats that Python (pygame / playsound / pydub) can handle
ALLOWED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.wma', '.m4a'}
ALLOWED_AUDIO_MIMETYPES = {
    'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav',
    'audio/ogg', 'audio/flac', 'audio/aac', 'audio/x-ms-wma',
    'audio/mp4', 'audio/x-m4a',
}
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB


# Mapping Python weekday (0=Monday) → model hari field
WEEKDAY_MAP = {
    0: 'senin', 1: 'selasa', 2: 'rabu', 3: 'kamis',
    4: 'jumat', 5: 'sabtu', 6: 'minggu',
}

HARI_ORDER = {
    'senin': 0, 'selasa': 1, 'rabu': 2, 'kamis': 3,
    'jumat': 4, 'sabtu': 5, 'minggu': 6,
}


def _get_next_bell(now_local):
    """
    Return the next upcoming JadwalBel relative to `now_local`,
    or None if there are no active schedules.
    """
    today_key = WEEKDAY_MAP[now_local.weekday()]
    current_time = now_local.time()

    # 1) Try to find the next bell today
    next_today = (
        JadwalBel.objects
        .filter(aktif=True, hari=today_key, jam__gt=current_time)
        .order_by('jam')
        .first()
    )
    if next_today:
        return next_today

    # 2) Search the next 7 days
    for offset in range(1, 8):
        future = now_local + timedelta(days=offset)
        day_key = WEEKDAY_MAP[future.weekday()]
        bell = (
            JadwalBel.objects
            .filter(aktif=True, hari=day_key)
            .order_by('jam')
            .first()
        )
        if bell:
            return bell

    return None


@login_required(login_url='login')
def dashboard_view(request):
    now_local = timezone.localtime(timezone.now())

    total_jadwal = JadwalBel.objects.filter(aktif=True).count()
    total_musik = Musik.objects.count()

    next_bell = _get_next_bell(now_local)
    if next_bell:
        next_bell_time = next_bell.jam.strftime('%H:%M')
        next_bell_day = next_bell.get_hari_display()
        next_bell_name = next_bell.nama
    else:
        next_bell_time = '--:--'
        next_bell_day = ''
        next_bell_name = 'Tidak ada jadwal'

    # All active schedules sorted by day-order then time
    jadwal_list = sorted(
        JadwalBel.objects.filter(aktif=True).select_related('musik'),
        key=lambda j: (HARI_ORDER.get(j.hari, 99), j.jam),
    )

    # ── Build calendar grid for the current month ──
    year = now_local.year
    month = now_local.month
    day_today = now_local.day

    MONTH_NAMES_ID = [
        'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
    ]

    _, days_in_month = cal_mod.monthrange(year, month)

    # bell counts per weekday
    day_counts = dict(
        JadwalBel.objects
        .filter(aktif=True)
        .values_list('hari')
        .annotate(c=Count('id'))
        .values_list('hari', 'c')
    )

    # exception counts per calendar day
    exc_counts = {}
    for p in Pengecualian.objects.filter(tanggal__year=year, tanggal__month=month):
        exc_counts[p.tanggal.day] = exc_counts.get(p.tanggal.day, 0) + 1

    # leading blank cells (Monday = 0)
    first_date = dt_date(year, month, 1)
    leading_blanks = (first_date.weekday())  # Mon=0 … Sun=6

    cal_days = []
    for d in range(1, days_in_month + 1):
        date_obj = dt_date(year, month, d)
        wk = WEEKDAY_MAP[date_obj.weekday()]
        cal_days.append({
            'day': d,
            'weekday': wk,
            'bell_count': day_counts.get(wk, 0),
            'exc_count': exc_counts.get(d, 0),
            'is_today': d == day_today,
            'is_weekend': wk in ('sabtu', 'minggu'),
        })

    context = {
        'server_time': now_local.strftime('%H:%M:%S'),
        'server_date': now_local.strftime('%A, %d %B %Y'),
        'total_jadwal': total_jadwal,
        'total_musik': total_musik,
        'next_bell_time': next_bell_time,
        'next_bell_day': next_bell_day,
        'next_bell_name': next_bell_name,
        'jadwal_list': jadwal_list,
        'today_year': year,
        'today_month': month,
        'today_day': day_today,
        'cal_month_label': f'{MONTH_NAMES_ID[month - 1]} {year}',
        'cal_leading_blanks': range(leading_blanks),
        'cal_days': cal_days,
        'active_menu': 'dashboard',
    }
    return render(request, 'dashboard/index.html', context)


@login_required(login_url='login')
def server_time_api(request):
    """
    JSON endpoint returning the Raspberry Pi server time.
    The dashboard JS polls this every second so the clock
    is always server-authoritative, not client-side.
    """
    now_local = timezone.localtime(timezone.now())

    next_bell = _get_next_bell(now_local)

    return JsonResponse({
        'time': now_local.strftime('%H:%M:%S'),
        'date': now_local.strftime('%A, %d %B %Y'),
        'next_bell_time': next_bell.jam.strftime('%H:%M') if next_bell else '--:--',
        'next_bell_day': next_bell.get_hari_display() if next_bell else '',
        'next_bell_name': next_bell.nama if next_bell else 'Tidak ada jadwal',
    })


@login_required(login_url='login')
def calendar_data_api(request):
    """
    JSON endpoint for the dashboard calendar view.

    GET ?year=2025&month=6          → month overview (bell counts & exception counts per day)
    GET ?year=2025&month=6&day=15   → day detail (schedules + exceptions for that date)
    """
    try:
        year = int(request.GET.get('year', 0))
        month = int(request.GET.get('month', 0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid year/month'}, status=400)

    if not (1 <= month <= 12) or year < 1:
        return JsonResponse({'error': 'Invalid year/month'}, status=400)

    day_param = request.GET.get('day')

    if day_param is not None:
        # ---------- Day detail ----------
        try:
            day = int(day_param)
            target_date = dt_date(year, month, day)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid day'}, status=400)

        day_key = WEEKDAY_MAP[target_date.weekday()]

        schedules = (
            JadwalBel.objects
            .filter(aktif=True, hari=day_key)
            .select_related('musik')
            .order_by('jam')
        )

        exceptions = {
            p.jadwal_id: p.alasan
            for p in Pengecualian.objects.filter(tanggal=target_date)
        }

        items = []
        for s in schedules:
            exc_reason = exceptions.get(s.pk)
            items.append({
                'nama': s.nama,
                'jam': s.jam.strftime('%H:%M'),
                'musik': s.musik.nama if s.musik else 'Default',
                'excluded': exc_reason is not None,
                'alasan': exc_reason or '',
            })

        return JsonResponse({
            'date': target_date.strftime('%A, %d %B %Y'),
            'day_key': day_key,
            'items': items,
        })

    # ---------- Month overview ----------
    _, days_in_month = cal_mod.monthrange(year, month)

    # Build a map: weekday_key → count of active schedules
    day_counts = dict(
        JadwalBel.objects
        .filter(aktif=True)
        .values_list('hari')
        .annotate(c=Count('id'))
        .values_list('hari', 'c')
    )

    # Exception counts per day-of-month
    exc_counts = {}
    exceptions_qs = Pengecualian.objects.filter(
        tanggal__year=year, tanggal__month=month
    )
    for p in exceptions_qs:
        exc_counts[p.tanggal.day] = exc_counts.get(p.tanggal.day, 0) + 1

    days = []
    for d in range(1, days_in_month + 1):
        date_obj = dt_date(year, month, d)
        wk = WEEKDAY_MAP[date_obj.weekday()]
        days.append({
            'day': d,
            'weekday': wk,
            'bell_count': day_counts.get(wk, 0),
            'exc_count': exc_counts.get(d, 0),
        })

    return JsonResponse({
        'year': year,
        'month': month,
        'days': days,
    })


# ================================================================
#  Musik Management Views
# ================================================================

def _validate_audio_file(f):
    """Validate uploaded file is a playable audio format. Returns error string or None."""
    # Check extension
    _, ext = os.path.splitext(f.name)
    if ext.lower() not in ALLOWED_AUDIO_EXTENSIONS:
        allowed = ', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))
        return f'Format file "{ext}" tidak didukung. Format yang diizinkan: {allowed}'

    # Check MIME type
    if f.content_type and f.content_type not in ALLOWED_AUDIO_MIMETYPES:
        return f'Tipe file "{f.content_type}" tidak didukung. Hanya file audio yang diizinkan.'

    # Check file size
    if f.size > MAX_UPLOAD_SIZE:
        max_mb = MAX_UPLOAD_SIZE // (1024 * 1024)
        return f'Ukuran file terlalu besar ({f.size // (1024*1024)} MB). Maksimal {max_mb} MB.'

    return None


def _get_audio_duration(file_path):
    """
    Return audio duration in seconds using mutagen.
    Returns 0.0 if duration cannot be determined.
    """
    try:
        import mutagen
        audio = mutagen.File(file_path)
        if audio is not None and audio.info is not None:
            return round(audio.info.length, 1)
    except Exception:
        pass
    return 0.0


def _time_to_seconds(time_obj):
    return time_obj.hour * 3600 + time_obj.minute * 60 + time_obj.second


def _music_duration_seconds(musik_obj):
    if not musik_obj or not musik_obj.durasi:
        return 0
    return math.ceil(musik_obj.durasi)


def _interval_overlaps(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a


def _validate_schedule_conflicts(hari_list, jam_list, musik_obj, exclude_pks=None):
    """
    Validate all proposed schedules before save.

    Rules:
    - No two active schedules may start at the same time on the same day.
    - No bell may start while another bell's audio is still playing.
    - Applies to conflicts against existing active schedules and
      conflicts within the new batch itself.
    """
    hari_labels = dict(JadwalBel.HARI_CHOICES)
    new_duration = _music_duration_seconds(musik_obj)
    musik_label = musik_obj.nama if musik_obj else 'Tanpa Musik'

    proposed_by_day = {}
    for hari in hari_list:
        for jam_str in jam_list:
            jam_obj = datetime.strptime(jam_str, '%H:%M').time()
            start = _time_to_seconds(jam_obj)
            proposed_by_day.setdefault(hari, []).append({
                'hari': hari,
                'jam': jam_str,
                'start': start,
                'end': start + new_duration,
            })

    existing_qs = JadwalBel.objects.filter(aktif=True).select_related('musik')
    if exclude_pks:
        existing_qs = existing_qs.exclude(pk__in=exclude_pks)

    existing_by_day = {}
    for schedule in existing_qs:
        start = _time_to_seconds(schedule.jam)
        durasi = _music_duration_seconds(schedule.musik)
        existing_by_day.setdefault(schedule.hari, []).append({
            'nama': schedule.nama,
            'jam': schedule.jam.strftime('%H:%M'),
            'start': start,
            'end': start + durasi,
            'musik': schedule.musik.nama if schedule.musik else 'Tanpa Musik',
        })

    errors = []
    seen = set()

    def add_error(message):
        if message not in seen:
            seen.add(message)
            errors.append(message)

    for hari, proposed_items in proposed_by_day.items():
        day_label = hari_labels.get(hari, hari)
        existing_items = existing_by_day.get(hari, [])

        for item in proposed_items:
            for existing in existing_items:
                if item['start'] == existing['start']:
                    add_error(
                        f'{day_label} {item["jam"]} bentrok dengan jadwal "{existing["nama"]}" '
                        f'karena waktu mulai sama.'
                    )
                    continue

                if _interval_overlaps(item['start'], item['end'], existing['start'], existing['end']):
                    existing_end = _seconds_to_time_str(existing['end'])
                    add_error(
                        f'{day_label} {item["jam"]} bentrok dengan "{existing["nama"]}" '
                        f'({existing["jam"]}–{existing_end}) karena suara bell masih diputar.'
                    )

        sorted_items = sorted(proposed_items, key=lambda x: x['start'])
        for idx in range(len(sorted_items)):
            left = sorted_items[idx]
            for right in sorted_items[idx + 1:]:
                if left['start'] == right['start']:
                    add_error(
                        f'{day_label} {left["jam"]} dan {right["jam"]} bentrok karena waktu mulai sama.'
                    )
                    continue

                if _interval_overlaps(left['start'], left['end'], right['start'], right['end']):
                    left_end = _seconds_to_time_str(left['end'])
                    add_error(
                        f'{day_label} {left["jam"]}–{left_end} bentrok dengan {right["jam"]} '
                        f'karena musik "{musik_label}" masih diputar.'
                    )

    return errors


def _seconds_to_time_str(total_seconds):
    """Convert seconds-of-day to HH:MM:SS string."""
    total_seconds = min(total_seconds, 86399)
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f'{h:02d}:{m:02d}:{s:02d}'


@login_required(login_url='login')
def musik_list_view(request):
    """List all uploaded music files + handle upload form."""
    musik_list = Musik.objects.all()

    if request.method == 'POST':
        nama = request.POST.get('nama', '').strip()
        audio_file = request.FILES.get('file')

        if not nama:
            messages.error(request, 'Nama musik tidak boleh kosong.')
        elif not audio_file:
            messages.error(request, 'Pilih file audio untuk diunggah.')
        else:
            error = _validate_audio_file(audio_file)
            if error:
                messages.error(request, error)
            else:
                musik_obj = Musik.objects.create(nama=nama, file=audio_file)
                # Calculate and save duration
                try:
                    file_path = musik_obj.file.path
                    musik_obj.durasi = _get_audio_duration(file_path)
                    musik_obj.save(update_fields=['durasi'])
                except Exception:
                    pass
                messages.success(request, f'Musik "{nama}" berhasil diunggah.')
                return redirect('musik_list')

        # Re-render with form data preserved
        return render(request, 'dashboard/musik.html', {
            'musik_list': musik_list,
            'form_nama': nama,
            'active_menu': 'musik',
        })

    return render(request, 'dashboard/musik.html', {
        'musik_list': musik_list,
        'active_menu': 'musik',
    })


@login_required(login_url='login')
def musik_delete_view(request, pk):
    """Delete a music file."""
    musik = get_object_or_404(Musik, pk=pk)
    if request.method == 'POST':
        # Delete the physical file
        if musik.file:
            file_path = os.path.join(settings.MEDIA_ROOT, str(musik.file))
            if os.path.exists(file_path):
                os.remove(file_path)
        nama = musik.nama
        musik.delete()
        messages.success(request, f'Musik "{nama}" berhasil dihapus.')
    return redirect('musik_list')


# ================================================================
#  Jadwal Bel Management Views
# ================================================================

@login_required(login_url='login')
def jadwal_list_view(request):
    """List all bell schedules, grouped by name."""
    all_jadwal = sorted(
        JadwalBel.objects.select_related('musik').all(),
        key=lambda j: (HARI_ORDER.get(j.hari, 99), j.jam),
    )

    # Group by nama (preserve insertion order)
    groups_dict = OrderedDict()
    hari_display = dict(JadwalBel.HARI_CHOICES)
    for j in all_jadwal:
        if j.nama not in groups_dict:
            groups_dict[j.nama] = {
                'nama': j.nama,
                'nama_encoded': quote(j.nama),
                'hari_set': [],
                'jam_set': [],
                'musik': j.musik,
                'aktif': True,
                'schedules': [],
            }
        g = groups_dict[j.nama]
        g['schedules'].append(j)
        hari_label = hari_display.get(j.hari, j.hari)
        if hari_label not in g['hari_set']:
            g['hari_set'].append(hari_label)
        jam_str = j.jam.strftime('%H:%M')
        if jam_str not in g['jam_set']:
            g['jam_set'].append(jam_str)
        if not j.aktif:
            g['aktif'] = False

    grouped_jadwal = list(groups_dict.values())
    total_count = len(all_jadwal)

    return render(request, 'dashboard/jadwal.html', {
        'grouped_jadwal': grouped_jadwal,
        'total_count': total_count,
        'hari_choices': JadwalBel.HARI_CHOICES,
        'active_menu': 'jadwal',
    })


@login_required(login_url='login')
def jadwal_create_view(request):
    """Create new bell schedules (batch: multiple days × multiple times)."""
    musik_list = Musik.objects.all()
    hari_dict = dict(JadwalBel.HARI_CHOICES)

    if request.method == 'POST':
        nama = request.POST.get('nama', '').strip()
        hari_list = request.POST.getlist('hari')
        jam_list = request.POST.getlist('jam')
        musik_id = request.POST.get('musik', '').strip()
        aktif = request.POST.get('aktif') == 'on'

        # Deduplicate & sort
        hari_list = list(dict.fromkeys(hari_list))  # preserve order, remove dupes
        jam_list = sorted(set(jam_list))

        errors = []
        if not nama:
            errors.append('Nama jadwal tidak boleh kosong.')
        if not hari_list:
            errors.append('Pilih setidaknya satu hari.')
        else:
            for h in hari_list:
                if h not in hari_dict:
                    errors.append(f'Hari "{h}" tidak valid.')
                    break
        if not jam_list:
            errors.append('Tambahkan setidaknya satu waktu bel.')
        else:
            for j in jam_list:
                try:
                    datetime.strptime(j, '%H:%M')
                except ValueError:
                    errors.append(f'Format waktu "{j}" tidak valid. Gunakan HH:MM.')
                    break

        if not errors:
            hari_labels = dict(JadwalBel.HARI_CHOICES)
            existing_same_slot = (
                JadwalBel.objects
                .filter(hari__in=hari_list, jam__in=jam_list)
                .order_by('hari', 'jam')
            )
            for schedule in existing_same_slot:
                errors.append(
                    f'Jadwal untuk {hari_labels.get(schedule.hari, schedule.hari)} '
                    f'pukul {schedule.jam.strftime("%H:%M")} sudah ada.'
                )

        musik_obj = None
        if musik_id:
            try:
                musik_obj = Musik.objects.get(pk=int(musik_id))
            except (Musik.DoesNotExist, ValueError):
                errors.append('Musik yang dipilih tidak ditemukan.')

        # Schedule conflict validation for every combination
        if not errors and aktif:
            errors.extend(_validate_schedule_conflicts(hari_list, jam_list, musik_obj))

        # Build form_data with lists so the template can re-check boxes
        form_data = {
            'nama': nama,
            'hari_list': hari_list,
            'jam_list': jam_list,
            'musik': musik_id,
            'aktif': 'on' if aktif else '',
        }

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'dashboard/jadwal_create_form.html', {
                'form_data': form_data,
                'musik_list': musik_list,
                'hari_choices': JadwalBel.HARI_CHOICES,
                'active_menu': 'jadwal',
            })

        # Batch create all combinations
        created = 0
        for h in hari_list:
            for j in jam_list:
                JadwalBel.objects.create(
                    nama=nama,
                    hari=h,
                    jam=j,
                    musik=musik_obj,
                    aktif=aktif,
                )
                created += 1

        messages.success(request, f'{created} jadwal "{nama}" berhasil ditambahkan.')
        return redirect('jadwal_list')

    form_data = {'hari_list': [], 'jam_list': [], 'aktif': 'on'}

    return render(request, 'dashboard/jadwal_create_form.html', {
        'form_data': form_data,
        'musik_list': musik_list,
        'hari_choices': JadwalBel.HARI_CHOICES,
        'active_menu': 'jadwal',
    })


@login_required(login_url='login')
def jadwal_edit_view(request, pk):
    """Redirect old single-edit URL to group edit."""
    jadwal = get_object_or_404(JadwalBel, pk=pk)
    return redirect('jadwal_group_edit', nama=quote(jadwal.nama))


@login_required(login_url='login')
def jadwal_group_edit_view(request, nama):
    """Edit all schedules in a group (same nama) — multi-day × multi-time like create."""
    nama = unquote(nama)
    group_qs = JadwalBel.objects.filter(nama=nama).select_related('musik')
    if not group_qs.exists():
        messages.error(request, f'Grup jadwal "{nama}" tidak ditemukan.')
        return redirect('jadwal_list')

    musik_list = Musik.objects.all()
    hari_dict = dict(JadwalBel.HARI_CHOICES)

    # Current group state
    first = group_qs.first()
    existing_hari = sorted(set(j.hari for j in group_qs), key=lambda h: HARI_ORDER.get(h, 99))
    existing_jam = sorted(set(j.jam.strftime('%H:%M') for j in group_qs))
    existing_aktif = all(j.aktif for j in group_qs)

    if request.method == 'POST':
        new_nama = request.POST.get('nama', '').strip()
        hari_list = request.POST.getlist('hari')
        jam_list = request.POST.getlist('jam')
        musik_id = request.POST.get('musik', '').strip()
        aktif = request.POST.get('aktif') == 'on'

        # Deduplicate & sort
        hari_list = list(dict.fromkeys(hari_list))
        jam_list = sorted(set(jam_list))

        errors = []
        if not new_nama:
            errors.append('Nama jadwal tidak boleh kosong.')
        if not hari_list:
            errors.append('Pilih setidaknya satu hari.')
        else:
            for h in hari_list:
                if h not in hari_dict:
                    errors.append(f'Hari "{h}" tidak valid.')
                    break
        if not jam_list:
            errors.append('Tambahkan setidaknya satu waktu bel.')
        else:
            for j in jam_list:
                try:
                    datetime.strptime(j, '%H:%M')
                except ValueError:
                    errors.append(f'Format waktu "{j}" tidak valid. Gunakan HH:MM.')
                    break

        # Validate duplicate day+time against existing schedules
        if not errors:
            existing_same_time = (
                JadwalBel.objects
                .filter(hari__in=hari_list, jam__in=jam_list)
                .order_by('hari', 'jam')
            )
            for jadwal in existing_same_time:
                errors.append(
                    f'Jadwal pada {jadwal.get_hari_display()} {jadwal.jam.strftime("%H:%M")} '
                    f'sudah ada ("{jadwal.nama}"). Pilih hari atau jam lain.'
                )

        musik_obj = None
        if musik_id:
            try:
                musik_obj = Musik.objects.get(pk=int(musik_id))
            except (Musik.DoesNotExist, ValueError):
                errors.append('Musik yang dipilih tidak ditemukan.')

        # Collect current group PKs (to exclude from conflict check)
        current_pks = list(group_qs.values_list('pk', flat=True))

        # Conflict validation for new combinations
        if not errors and aktif:
            errors.extend(
                _validate_schedule_conflicts(
                    hari_list,
                    jam_list,
                    musik_obj,
                    exclude_pks=current_pks,
                )
            )

        form_data = {
            'nama': new_nama,
            'hari_list': hari_list,
            'jam_list': jam_list,
            'musik': musik_id,
            'aktif': 'on' if aktif else '',
        }

        if errors:
            # Deduplicate errors
            seen = set()
            unique_errors = []
            for e in errors:
                if e not in seen:
                    seen.add(e)
                    unique_errors.append(e)
            for error in unique_errors:
                messages.error(request, error)
            return render(request, 'dashboard/jadwal_edit_form.html', {
                'form_data': form_data,
                'musik_list': musik_list,
                'hari_choices': JadwalBel.HARI_CHOICES,
                'active_menu': 'jadwal',
                'group_nama': nama,
            })

        # Delete old schedules and recreate
        group_qs.delete()
        created = 0
        for h in hari_list:
            for j in jam_list:
                JadwalBel.objects.create(
                    nama=new_nama,
                    hari=h,
                    jam=j,
                    musik=musik_obj,
                    aktif=aktif,
                )
                created += 1

        messages.success(request, f'{created} jadwal "{new_nama}" berhasil diperbarui.')
        return redirect('jadwal_list')

    # Pre-fill form with group data
    form_data = {
        'nama': nama,
        'hari_list': existing_hari,
        'jam_list': existing_jam,
        'musik': str(first.musik_id) if first.musik_id else '',
        'aktif': 'on' if existing_aktif else '',
    }

    return render(request, 'dashboard/jadwal_edit_form.html', {
        'form_data': form_data,
        'musik_list': musik_list,
        'hari_choices': JadwalBel.HARI_CHOICES,
        'active_menu': 'jadwal',
        'group_nama': nama,
    })


@login_required(login_url='login')
def jadwal_delete_view(request, pk):
    """Delete a bell schedule."""
    jadwal = get_object_or_404(JadwalBel, pk=pk)
    if request.method == 'POST':
        nama = jadwal.nama
        jadwal.delete()
        messages.success(request, f'Jadwal "{nama}" berhasil dihapus.')
    return redirect('jadwal_list')


@login_required(login_url='login')
def jadwal_group_delete_view(request, nama):
    """Delete all schedules in a group."""
    nama = unquote(nama)
    group_qs = JadwalBel.objects.filter(nama=nama)
    if request.method == 'POST':
        count = group_qs.count()
        group_qs.delete()
        messages.success(request, f'{count} jadwal "{nama}" berhasil dihapus.')
    return redirect('jadwal_list')


@login_required(login_url='login')
def jadwal_toggle_view(request, pk):
    """Toggle active status of a schedule."""
    jadwal = get_object_or_404(JadwalBel, pk=pk)
    if request.method == 'POST':
        jadwal.aktif = not jadwal.aktif
        jadwal.save()
        status = 'diaktifkan' if jadwal.aktif else 'dinonaktifkan'
        messages.success(request, f'Jadwal "{jadwal.nama}" berhasil {status}.')
    return redirect('jadwal_list')


@login_required(login_url='login')
def jadwal_group_toggle_view(request, nama):
    """Toggle active status of all schedules in a group."""
    nama = unquote(nama)
    group_qs = JadwalBel.objects.filter(nama=nama)
    if request.method == 'POST' and group_qs.exists():
        # If any is active, deactivate all; otherwise activate all
        any_active = group_qs.filter(aktif=True).exists()
        new_status = not any_active
        group_qs.update(aktif=new_status)
        status = 'diaktifkan' if new_status else 'dinonaktifkan'
        messages.success(request, f'Grup jadwal "{nama}" berhasil {status}.')
    return redirect('jadwal_list')


# ================================================================
#  Pengecualian (Exception / Exclusion) Views
# ================================================================

@login_required(login_url='login')
def pengecualian_list_view(request):
    """List all schedule exceptions."""
    from django.utils import timezone as tz
    today = tz.localtime(tz.now()).date()

    pengecualian_list = (
        Pengecualian.objects
        .select_related('jadwal', 'jadwal__musik')
        .all()
    )

    # Separate upcoming/today vs past
    upcoming = [p for p in pengecualian_list if p.tanggal >= today]
    past = [p for p in pengecualian_list if p.tanggal < today]

    return render(request, 'dashboard/pengecualian.html', {
        'upcoming': upcoming,
        'past': past,
        'today': today,
        'active_menu': 'pengecualian',
    })


@login_required(login_url='login')
def pengecualian_create_view(request):
    """Create schedule exceptions — pick a date and select which bells to silence."""
    from django.utils import timezone as tz
    today = tz.localtime(tz.now()).date()

    if request.method == 'POST':
        tanggal_str = request.POST.get('tanggal', '').strip()
        alasan = request.POST.get('alasan', '').strip()
        jadwal_ids = request.POST.getlist('jadwal')

        # Validate date
        if not tanggal_str:
            messages.error(request, 'Tanggal wajib diisi.')
            return redirect('pengecualian_create')

        try:
            tanggal = datetime.strptime(tanggal_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Format tanggal tidak valid.')
            return redirect('pengecualian_create')

        # Validate jadwal selection
        if not jadwal_ids:
            messages.error(request, 'Pilih setidaknya satu jadwal bel.')
            # Re-render with preserved data
            hari_key = WEEKDAY_MAP.get(tanggal.weekday(), '')
            jadwal_list = (
                JadwalBel.objects
                .filter(aktif=True, hari=hari_key)
                .select_related('musik')
                .order_by('jam')
            )
            return render(request, 'dashboard/pengecualian_form.html', {
                'jadwal_list': jadwal_list,
                'form_data': {
                    'tanggal': tanggal_str,
                    'alasan': alasan,
                    'jadwal_ids': jadwal_ids,
                    'hari_label': dict(JadwalBel.HARI_CHOICES).get(hari_key, ''),
                },
                'active_menu': 'pengecualian',
            })

        # Determine day of week for the selected date
        hari_key = WEEKDAY_MAP.get(tanggal.weekday(), '')

        created = 0
        skipped = 0
        for jid in jadwal_ids:
            try:
                jadwal = JadwalBel.objects.get(pk=int(jid), aktif=True, hari=hari_key)
                _, was_created = Pengecualian.objects.get_or_create(
                    tanggal=tanggal,
                    jadwal=jadwal,
                    defaults={'alasan': alasan},
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1
            except (JadwalBel.DoesNotExist, ValueError):
                continue

        if created > 0:
            messages.success(request, f'{created} pengecualian berhasil ditambahkan untuk {tanggal.strftime("%d/%m/%Y")}.')
        if skipped > 0:
            messages.info(request, f'{skipped} pengecualian sudah ada sebelumnya (dilewati).')
        if created == 0 and skipped == 0:
            messages.error(request, 'Tidak ada pengecualian yang ditambahkan.')

        return redirect('pengecualian_list')

    # GET — show empty form
    return render(request, 'dashboard/pengecualian_form.html', {
        'jadwal_list': [],
        'form_data': {},
        'active_menu': 'pengecualian',
    })


@login_required(login_url='login')
def pengecualian_jadwal_api(request):
    """
    AJAX endpoint: given a date, return the active schedules for that day of week.
    """
    tanggal_str = request.GET.get('tanggal', '')
    if not tanggal_str:
        return JsonResponse({'jadwal': []})

    try:
        tanggal = datetime.strptime(tanggal_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'jadwal': []})

    hari_key = WEEKDAY_MAP.get(tanggal.weekday(), '')
    hari_label = dict(JadwalBel.HARI_CHOICES).get(hari_key, '')

    jadwal_qs = (
        JadwalBel.objects
        .filter(aktif=True, hari=hari_key)
        .select_related('musik')
        .order_by('jam')
    )

    # Check which are already excluded on that date
    existing_exclusions = set(
        Pengecualian.objects
        .filter(tanggal=tanggal)
        .values_list('jadwal_id', flat=True)
    )

    jadwal_data = []
    for j in jadwal_qs:
        jadwal_data.append({
            'id': j.pk,
            'nama': j.nama,
            'jam': j.jam.strftime('%H:%M'),
            'musik': j.musik.nama if j.musik else '— Tanpa musik',
            'already_excluded': j.pk in existing_exclusions,
        })

    # Build group info for group-level selection
    groups = OrderedDict()
    for item in jadwal_data:
        if item['nama'] not in groups:
            groups[item['nama']] = {'ids': [], 'count': 0, 'all_excluded': True}
        groups[item['nama']]['ids'].append(item['id'])
        groups[item['nama']]['count'] += 1
        if not item['already_excluded']:
            groups[item['nama']]['all_excluded'] = False

    groups_data = []
    for gname, ginfo in groups.items():
        groups_data.append({
            'nama': gname,
            'ids': ginfo['ids'],
            'count': ginfo['count'],
            'all_excluded': ginfo['all_excluded'],
        })

    return JsonResponse({
        'hari': hari_label,
        'hari_key': hari_key,
        'jadwal': jadwal_data,
        'groups': groups_data,
    })


@login_required(login_url='login')
def pengecualian_delete_view(request, pk):
    """Delete a schedule exception."""
    pengecualian = get_object_or_404(Pengecualian, pk=pk)
    if request.method == 'POST':
        tanggal = pengecualian.tanggal.strftime('%d/%m/%Y')
        nama = pengecualian.jadwal.nama
        pengecualian.delete()
        messages.success(request, f'Pengecualian "{nama}" pada {tanggal} berhasil dihapus.')
    return redirect('pengecualian_list')


# ================================================================
#  Audio Playback Controls (test / stop)
# ================================================================

@login_required(login_url='login')
def musik_test_play_view(request, pk):
    """Play a music file for testing through the server's audio output (AJAX)."""
    musik = get_object_or_404(Musik, pk=pk)
    if request.method == 'POST':
        from dashboard.scheduler import is_playing
        if is_playing():
            return JsonResponse({
                'status': 'error',
                'message': 'Tidak bisa memutar — ada audio yang sedang diputar. Hentikan dulu.',
            }, status=409)
        if musik.file:
            file_path = os.path.join(settings.MEDIA_ROOT, str(musik.file))
            try:
                from dashboard.scheduler import play_audio
                play_audio(file_path, name=musik.nama)
                return JsonResponse({
                    'status': 'ok',
                    'message': f'Memutar "{musik.nama}" di server...',
                })
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Gagal memutar: {e}',
                }, status=500)
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'File audio tidak tersedia.',
            }, status=404)
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


@login_required(login_url='login')
def musik_stop_play_view(request):
    """Stop any currently playing audio on the server (AJAX)."""
    if request.method == 'POST':
        try:
            from dashboard.scheduler import stop_audio
            stop_audio()
            return JsonResponse({'status': 'ok', 'message': 'Pemutaran dihentikan.'})
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Gagal menghentikan: {e}',
            }, status=500)
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


@login_required(login_url='login')
def playback_status_api(request):
    """JSON endpoint returning current audio playback status."""
    from dashboard.scheduler import get_playback_status
    return JsonResponse(get_playback_status())

